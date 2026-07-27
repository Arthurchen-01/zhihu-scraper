"""Filesystem archive sink for every normalized Zhihu target."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .assets import AssetArchiveReceipt, archive_assets
from .database import ArchiveDatabase
from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    ColumnArchive,
    ColumnRef,
    QuestionArchive,
    Video,
)
from .filenames import safe_filename
from .media import MediaDownloadReceipt, download_media
from .render import (
    ColumnRenderContext,
    HtmlRenderer,
    MarkdownRenderer,
    RenderNavigationItem,
)
from .settings import ArchiveSettings

MediaDownloader = Callable[[str, Path], MediaDownloadReceipt]


@dataclass(frozen=True, slots=True)
class ArchiveReceipt:
    entry_directory: Path
    markdown_path: Path | None
    html_path: Path | None
    database_path: Path | None
    child_markdown_paths: tuple[Path, ...] = ()
    child_html_paths: tuple[Path, ...] = ()
    media_downloads: tuple[MediaDownloadReceipt, ...] = ()


class LocalArchive:
    """Write readable files and one root SQLite database without legacy layout."""

    def __init__(
        self,
        root: Path,
        *,
        markdown: bool = True,
        html: bool = True,
        sqlite: bool = True,
        media_download: bool = True,
        downloader: MediaDownloader = download_media,
    ) -> None:
        if not any((markdown, html, sqlite)):
            raise ValueError("至少启用 Markdown、HTML 或 SQLite 中的一种输出。")
        self._root = Path(root)
        self._markdown = markdown
        self._html = html
        self._sqlite = sqlite
        self._media_download = media_download
        self._downloader = downloader

    @classmethod
    def from_settings(
        cls,
        settings: ArchiveSettings,
        *,
        downloader: MediaDownloader = download_media,
    ) -> LocalArchive:
        if settings.pdf:
            raise NotImplementedError("PDF 输出仍是待办功能，请先保持 pdf = false。")
        return cls(
            settings.output_dir,
            markdown=settings.markdown,
            html=settings.html,
            sqlite=settings.sqlite,
            media_download=settings.media_download,
            downloader=downloader,
        )

    def archive(self, target: ArchiveTarget) -> ArchiveReceipt:
        self._root.mkdir(parents=True, exist_ok=True)
        if isinstance(target, ColumnArchive):
            return self._archive_column(target)
        return self._archive_standalone(target)

    def _archive_standalone(self, target: ArchiveTarget) -> ArchiveReceipt:
        title = target.title
        filename = safe_filename(title)
        entry_directory = self._entry_directory(
            title=title,
            target_type=_target_type(target),
            target_id=target.id,
            source_url=target.source_url,
        )
        entry_directory.mkdir(parents=True, exist_ok=True)

        assets = self._archive_media(target, entry_directory)
        markdown_path = entry_directory / f"{filename}.md" if self._markdown else None
        html_path = entry_directory / f"{filename}.html" if self._html else None

        if markdown_path is not None:
            _atomic_write_text(
                markdown_path,
                MarkdownRenderer().render(
                    target,
                    media_paths=assets.source_paths,
                ),
            )
        if html_path is not None:
            _atomic_write_text(
                html_path,
                HtmlRenderer().render(
                    target,
                    media_paths=assets.source_paths,
                ),
            )
            self._write_html_assets(entry_directory / "assets")

        database_path = self._save_database(
            target,
            media_paths=assets.source_paths,
        )
        return ArchiveReceipt(
            entry_directory=entry_directory,
            markdown_path=markdown_path,
            html_path=html_path,
            database_path=database_path,
            media_downloads=assets.downloads,
        )

    def _archive_column(self, archive: ColumnArchive) -> ArchiveReceipt:
        column = archive.column
        column_filename = safe_filename(column.title)
        entry_directory = self._entry_directory(
            title=column.title,
            target_type="column",
            target_id=column.token,
            source_url=column.source_url,
        )
        entry_directory.mkdir(parents=True, exist_ok=True)
        assets = self._archive_media(archive, entry_directory)

        article_names = _unique_article_names(archive.articles)
        directory_entries = {
            article.id: RenderNavigationItem(
                title=article.title,
                markdown_href=f"内容/{name}.md" if self._markdown else "",
                html_href=f"内容/{name}.html" if self._html else "",
            )
            for article, name in zip(archive.articles, article_names, strict=True)
        }
        markdown_path = entry_directory / f"{column_filename}.md" if self._markdown else None
        html_path = entry_directory / f"{column_filename}.html" if self._html else None
        markdown_renderer = MarkdownRenderer()
        html_renderer = HtmlRenderer()
        if markdown_path is not None:
            _atomic_write_text(
                markdown_path,
                markdown_renderer.render(
                    archive,
                    directory_entries=directory_entries,
                ),
            )
        if html_path is not None:
            _atomic_write_text(
                html_path,
                html_renderer.render(
                    archive,
                    directory_entries=directory_entries,
                ),
            )
            self._write_html_assets(entry_directory / "assets")

        child_markdown_paths: list[Path] = []
        child_html_paths: list[Path] = []
        if archive.articles and (self._markdown or self._html):
            content_directory = entry_directory / "内容"
            content_directory.mkdir(exist_ok=True)
            child_media_paths = {
                source_url: f"../{relative_path}"
                for source_url, relative_path in assets.source_paths.items()
            }
            column_ref = ColumnRef(
                token=column.token,
                title=column.title,
                url=column.source_url,
            )
            directory_item = RenderNavigationItem(
                title=column.title,
                markdown_href=f"../{column_filename}.md" if self._markdown else "",
                html_href=f"../{column_filename}.html" if self._html else "",
            )
            for index, (article, name) in enumerate(
                zip(archive.articles, article_names, strict=True)
            ):
                previous_item = (
                    _article_navigation(
                        archive.articles[index - 1],
                        article_names[index - 1],
                        markdown=self._markdown,
                        html=self._html,
                    )
                    if index > 0
                    else None
                )
                next_item = (
                    _article_navigation(
                        archive.articles[index + 1],
                        article_names[index + 1],
                        markdown=self._markdown,
                        html=self._html,
                    )
                    if index + 1 < len(archive.articles)
                    else None
                )
                context = ColumnRenderContext(
                    column=column_ref,
                    directory=directory_item,
                    previous=previous_item,
                    next=next_item,
                )
                if self._markdown:
                    article_markdown = content_directory / f"{name}.md"
                    _atomic_write_text(
                        article_markdown,
                        markdown_renderer.render(
                            article,
                            media_paths=child_media_paths,
                            column_context=context,
                        ),
                    )
                    child_markdown_paths.append(article_markdown)
                if self._html:
                    article_html = content_directory / f"{name}.html"
                    _atomic_write_text(
                        article_html,
                        html_renderer.render(
                            article,
                            media_paths=child_media_paths,
                            column_context=context,
                        ),
                    )
                    child_html_paths.append(article_html)

        database_path = self._save_database(
            archive,
            media_paths=assets.source_paths,
        )
        return ArchiveReceipt(
            entry_directory=entry_directory,
            markdown_path=markdown_path,
            html_path=html_path,
            database_path=database_path,
            child_markdown_paths=tuple(child_markdown_paths),
            child_html_paths=tuple(child_html_paths),
            media_downloads=assets.downloads,
        )

    def _archive_media(
        self,
        target: ArchiveTarget,
        entry_directory: Path,
    ) -> AssetArchiveReceipt:
        if not self._media_download:
            return AssetArchiveReceipt(source_paths={}, downloads=())
        return archive_assets(
            target,
            entry_directory / "media",
            downloader=self._downloader,
        )

    def _write_html_assets(self, assets_directory: Path) -> None:
        assets_directory.mkdir(exist_ok=True)
        for filename, content in HtmlRenderer.assets().items():
            _atomic_write_text(assets_directory / filename, content)

    def _save_database(
        self,
        target: ArchiveTarget,
        *,
        media_paths: Mapping[str, str],
    ) -> Path | None:
        if not self._sqlite:
            return None
        path = self._root / "zhihu.db"
        ArchiveDatabase(path).save(target, media_paths=media_paths)
        return path

    def _entry_directory(
        self,
        *,
        title: str,
        target_type: str,
        target_id: str,
        source_url: str,
    ) -> Path:
        base = self._root / safe_filename(title)
        if not base.exists() or _directory_belongs_to(base, source_url):
            return base
        suffix = safe_filename(f"{title}--{target_type}-{target_id}")
        return self._root / suffix


def _unique_article_names(articles: tuple[Article, ...]) -> tuple[str, ...]:
    used: set[str] = set()
    names: list[str] = []
    for article in articles:
        base = safe_filename(article.title)
        name = base
        if name.casefold() in used:
            name = safe_filename(f"{article.title}--article-{article.id}")
        counter = 2
        while name.casefold() in used:
            name = safe_filename(f"{article.title}--article-{article.id}-{counter}")
            counter += 1
        used.add(name.casefold())
        names.append(name)
    return tuple(names)


def _article_navigation(
    article: Article,
    filename: str,
    *,
    markdown: bool,
    html: bool,
) -> RenderNavigationItem:
    return RenderNavigationItem(
        title=article.title,
        markdown_href=f"{filename}.md" if markdown else "",
        html_href=f"{filename}.html" if html else "",
    )


def _target_type(target: ArchiveTarget) -> str:
    if isinstance(target, Article):
        return "article"
    if isinstance(target, Answer):
        return "answer"
    if isinstance(target, QuestionArchive):
        return "question"
    if isinstance(target, Video):
        return "video"
    if isinstance(target, ColumnArchive):
        return "column"
    raise TypeError(f"unsupported archive target: {type(target).__name__}")


def _directory_belongs_to(directory: Path, source_url: str) -> bool:
    for suffix in ("*.md", "*.html"):
        for document in directory.glob(suffix):
            try:
                prefix = document.read_text(encoding="utf-8")[:16_384]
            except (OSError, UnicodeError):
                continue
            if source_url in prefix:
                return True
    return False


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise
