"""
save_pipeline.py - Local archive save orchestration (v3.0 Core)

Extracts output naming, Markdown persistence, image downloading, and SQLite
writing into a decoupled core service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from .contracts import SavePipelineError, SaveRunResult, SavedContentRecord
from core.converter import ZhihuConverter
from core.db import ZhihuDatabase
from core.media_downloader import MediaDownloader
from core.scraper import ZhihuDownloader
from core.scraper_contracts import ScrapedItem, to_scraped_items
from core.utils import sanitize_filename
from core.protocols import EventSink, ProgressEvent, noop_event_sink


@dataclass(frozen=True)
class SavePipelineSettings:
    """Runtime knobs required by the local archive save pipeline."""

    folder_template: str
    images_subdir: str
    image_concurrency: int
    image_timeout: int


def build_output_folder_name(
    item_date: str,
    title: str,
    author: str,
    item_key: str,
    *,
    folder_template: Optional[str] = None,
) -> str:
    """
    Render output directory name from a configured template and stable suffix.
    根据配置模板生成输出目录名，并附加稳定唯一后缀。
    """
    template = folder_template or "[{date}] {title}"
    try:
        rendered = template.format(date=item_date, title=title, author=author)
    except KeyError:
        rendered = f"[{item_date}] {title}"

    rendered = sanitize_filename(rendered, max_length=100, shell_safe=True)
    safe_item_key = sanitize_filename(item_key, max_length=80, shell_safe=True)
    return f"{rendered}--{safe_item_key}"


def resolve_entries_output_dir(base_dir: Path) -> Path:
    """Resolve the content root for local archive outputs."""
    if base_dir.name == "entries":
        return base_dir
    return base_dir / "entries"


async def fetch_and_save(
    *,
    url: str,
    output_dir: Path,
    scrape_config: Dict[str, Any],
    settings: SavePipelineSettings,
    download_images: bool = True,
    headless: bool = True,
    event_sink: EventSink = noop_event_sink,
) -> list[dict[str, Any]]:
    """
    Execute scraping and save the result to local files and SQLite.
    执行抓取，并保存到本地文件和 SQLite。
    """
    result = await fetch_and_save_result(
        url=url,
        output_dir=output_dir,
        scrape_config=scrape_config,
        settings=settings,
        download_images=download_images,
        headless=headless,
        event_sink=event_sink,
    )
    return result.to_legacy_records()


async def fetch_and_save_result(
    *,
    url: str,
    output_dir: Path,
    scrape_config: Dict[str, Any],
    settings: SavePipelineSettings,
    download_images: bool = True,
    headless: bool = True,
    event_sink: EventSink = noop_event_sink,
) -> SaveRunResult:
    """
    Execute scraping and return a typed save result contract.
    执行抓取，并返回类型化保存结果契约。
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    downloader = ZhihuDownloader(url)
    fetch_kwargs = dict(scrape_config)
    fetch_kwargs["headless"] = headless
    fetch_result = await downloader.fetch_result(**fetch_kwargs)

    if fetch_result.is_empty:
        event_sink(
            ProgressEvent(
                type="save.warning",
                severity="warning",
                message="No content obtained / 未获取到内容",
            )
        )
        return SaveRunResult(
            source_url=url,
            content_root=resolve_entries_output_dir(output_dir),
            records=(),
            collection_id=None,
        )

    return await save_items_result(
        items=fetch_result.items,
        content_root=resolve_entries_output_dir(output_dir),
        db_root=output_dir,
        settings=settings,
        download_images=download_images,
        source_url_fallback=url,
        collection_id=None,
        event_sink=event_sink,
    )


async def save_items(
    *,
    items: Sequence[ScrapedItem] | Sequence[dict[str, Any]],
    content_root: Path,
    db_root: Path,
    settings: SavePipelineSettings,
    download_images: bool,
    source_url_fallback: str,
    collection_id: Optional[str] = None,
    event_sink: EventSink = noop_event_sink,
) -> list[dict[str, Any]]:
    """
    Save normalized content items to Markdown, images, and SQLite.
    将标准化内容保存到 Markdown、图片目录和 SQLite。
    """
    result = await save_items_result(
        items=items,
        content_root=content_root,
        db_root=db_root,
        settings=settings,
        download_images=download_images,
        source_url_fallback=source_url_fallback,
        collection_id=collection_id,
        event_sink=event_sink,
    )
    return result.to_legacy_records()


async def save_items_result(
    *,
    items: Sequence[ScrapedItem] | Sequence[dict[str, Any]],
    content_root: Path,
    db_root: Path,
    settings: SavePipelineSettings,
    download_images: bool,
    source_url_fallback: str,
    collection_id: Optional[str] = None,
    event_sink: EventSink = noop_event_sink,
) -> SaveRunResult:
    """
    Save normalized content items to Markdown, images, and SQLite.
    将标准化内容保存到 Markdown、图片目录和 SQLite。
    """
    content_root.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    typed_items = _coerce_scraped_items(items)

    db = ZhihuDatabase(str(db_root / "zhihu.db"))
    saved_records: list[SavedContentRecord] = []
    try:
        for item in typed_items:
            title = sanitize_filename(item.title)
            author = sanitize_filename(item.author)
            item_date = item.date or today
            source_url = item.url or source_url_fallback
            item_key = sanitize_filename(
                f"{item.type or 'item'}-{item.id or 'unknown'}",
                max_length=80,
            )

            folder_name = build_output_folder_name(
                item_date,
                title,
                author,
                item_key,
                folder_template=settings.folder_template,
            )
            folder = content_root / folder_name
            folder.mkdir(parents=True, exist_ok=True)

            img_map: Dict[str, str] = {}
            if download_images:
                img_urls = ZhihuConverter.extract_image_urls(item.html)
                if img_urls:
                    event_sink(
                        ProgressEvent(
                            type="media.download.started",
                            message=(
                                f"   📥 Downloading {len(img_urls)} images..."
                                f" / 下载 {len(img_urls)} 张图片..."
                            ),
                            current=0,
                            total=len(img_urls),
                        )
                    )
                    img_map = await MediaDownloader.download_images(
                        img_urls,
                        folder / settings.images_subdir,
                        concurrency=settings.image_concurrency,
                        timeout=settings.image_timeout,
                        relative_prefix=settings.images_subdir,
                    )

            converter = ZhihuConverter(img_map=img_map)
            md = converter.convert(item.html)

            header = (
                f"# {item.title}\n\n"
                f"> **Author / 作者**: {item.author}  \n"
                f"> **Source / 来源**: [{source_url}]({source_url})  \n"
                f"> **Date / 日期**: {item_date}\n\n"
                "---\n\n"
            )

            out_path = folder / "index.md"
            full_md = header + md
            out_path.write_text(full_md, encoding="utf-8")

            db_saved = db.save_article(item.to_dict(), full_md, collection_id=collection_id)
            if not db_saved:
                partial_result = SaveRunResult(
                    source_url=source_url_fallback,
                    content_root=content_root,
                    records=tuple(saved_records),
                    collection_id=collection_id,
                )
                raise SavePipelineError(
                    (
                        f"SQLite save failed after writing Markdown for {item.type}:{item.id}; "
                        f"{partial_result.saved_count} item(s) were already archived to disk"
                    ),
                    partial_result=partial_result,
                    failed_item=item,
                    failed_markdown_path=out_path,
                )
            saved_records.append(
                SavedContentRecord(
                    item=item,
                    folder=folder,
                    markdown_path=out_path,
                )
            )

            event_sink(
                ProgressEvent(
                    type="save.item.success",
                    message=f"Saved / 保存: {author} - {title[:25]}...",
                    payload={
                        "author": author,
                        "title": title,
                        "markdown_path": str(out_path),
                        "folder": str(folder),
                    },
                )
            )
    finally:
        db.close()

    return SaveRunResult(
        source_url=source_url_fallback,
        content_root=content_root,
        records=tuple(saved_records),
        collection_id=collection_id,
    )


def _coerce_scraped_items(
    items: Sequence[ScrapedItem] | Sequence[dict[str, Any]],
) -> Tuple[ScrapedItem, ...]:
    if not items:
        return ()
    first = items[0]
    if isinstance(first, ScrapedItem):
        return tuple(items)  # type: ignore[arg-type]
    return to_scraped_items(items)  # type: ignore[arg-type]
