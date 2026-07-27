"""Archive normalized media assets behind one small, target-level interface."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from urllib.parse import unquote, urlsplit

from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    Block,
    ColumnArchive,
    Comment,
    CommentThread,
    ListBlock,
    MediaAsset,
    MediaBlock,
    MediaKind,
    MediaRendition,
    QuestionArchive,
    Quote,
    Video,
)
from .media import MediaDownloadReceipt, download_media

AssetDownloader = Callable[[str, Path], MediaDownloadReceipt]


@dataclass(frozen=True, slots=True)
class AssetArchiveReceipt:
    """Downloaded files and the URL aliases renderers can replace."""

    source_paths: Mapping[str, str]
    downloads: tuple[MediaDownloadReceipt, ...]


def archive_assets(
    target: ArchiveTarget,
    media_directory: Path,
    *,
    downloader: AssetDownloader = download_media,
) -> AssetArchiveReceipt:
    """Download every unique media asset reachable from ``target``.

    Images and animations preserve the normalizer's first (original) rendition.
    Videos select the largest rendition with known dimensions.  Exact ties and
    renditions without dimensions retain source order, keeping selection stable.
    """

    media_directory = Path(media_directory)
    assets = tuple(_unique_assets(_target_assets(target)))
    downloadable = tuple(
        (asset, rendition)
        for asset in assets
        if (rendition := _select_rendition(asset)) is not None
    )
    if not downloadable:
        return AssetArchiveReceipt(MappingProxyType({}), ())

    media_directory.mkdir(parents=True, exist_ok=True)
    source_paths: dict[str, str] = {}
    downloads: list[MediaDownloadReceipt] = []
    selected_sources: dict[str, str] = {}

    for asset, selected in downloadable:
        existing_path = selected_sources.get(selected.source_url)
        if existing_path is None:
            filename = _archive_filename(asset, selected)
            destination = media_directory / filename
            receipt = downloader(selected.source_url, destination)
            relative_path = PurePosixPath(media_directory.name, filename).as_posix()
            selected_sources[selected.source_url] = relative_path
            downloads.append(receipt)
        else:
            relative_path = existing_path

        # Every rendition identifies the same logical asset.  Mapping all aliases
        # lets renderers replace whichever rendition appeared in the source.
        for rendition in asset.renditions:
            if rendition.source_url:
                source_paths[rendition.source_url] = relative_path

    return AssetArchiveReceipt(
        source_paths=MappingProxyType(source_paths),
        downloads=tuple(downloads),
    )


def _target_assets(target: ArchiveTarget) -> Iterator[MediaAsset]:
    if isinstance(target, Article):
        yield from _article_assets(target)
        return
    if isinstance(target, Answer):
        yield from _answer_assets(target)
        return
    if isinstance(target, QuestionArchive):
        yield from _blocks_assets(target.question.detail)
        for answer in target.answers:
            yield from _answer_assets(answer)
        return
    if isinstance(target, ColumnArchive):
        for article in target.articles:
            yield from _article_assets(article)
        return
    if isinstance(target, Video):
        yield target.asset
        yield from _blocks_assets(target.description)
        yield from _thread_assets(target.comments)
        if target.cover_url:
            yield _remote_image(
                asset_id=f"zvideo-{target.id}-cover",
                source_url=target.cover_url,
                alt_text=target.title,
            )
        return
    raise TypeError(f"unsupported archive target: {type(target).__name__}")


def _article_assets(article: Article) -> Iterator[MediaAsset]:
    yield from _blocks_assets(article.blocks)
    yield from _thread_assets(article.comments)
    if article.cover_url:
        yield _remote_image(
            asset_id=f"article-{article.id}-cover",
            source_url=article.cover_url,
            alt_text=article.title,
        )


def _answer_assets(answer: Answer) -> Iterator[MediaAsset]:
    yield from _blocks_assets(answer.blocks)
    yield from _thread_assets(answer.comments)


def _blocks_assets(blocks: Iterable[Block]) -> Iterator[MediaAsset]:
    for block in blocks:
        if isinstance(block, MediaBlock):
            yield block.asset
        elif isinstance(block, Quote):
            yield from _blocks_assets(block.blocks)
        elif isinstance(block, ListBlock):
            for item in block.items:
                yield from _blocks_assets(item)


def _thread_assets(thread: CommentThread | None) -> Iterator[MediaAsset]:
    if thread is None:
        return
    for comment in thread.comments:
        yield from _comment_assets(comment)


def _comment_assets(comment: Comment) -> Iterator[MediaAsset]:
    yield from _blocks_assets(comment.blocks)
    for reply in comment.replies:
        yield from _comment_assets(reply)


def _unique_assets(assets: Iterable[MediaAsset]) -> Iterator[MediaAsset]:
    seen: set[str] = set()
    for asset in assets:
        if asset.id in seen:
            continue
        seen.add(asset.id)
        yield asset


def _select_rendition(asset: MediaAsset) -> MediaRendition | None:
    available = tuple(rendition for rendition in asset.renditions if rendition.source_url.strip())
    if not available:
        return None
    if asset.kind is not MediaKind.VIDEO:
        return available[0]
    return max(available, key=_video_resolution)


def _video_resolution(rendition: MediaRendition) -> int:
    width = rendition.width
    height = rendition.height
    if width is None or height is None or width <= 0 or height <= 0:
        return -1
    return width * height


def _remote_image(*, asset_id: str, source_url: str, alt_text: str) -> MediaAsset:
    return MediaAsset(
        id=asset_id,
        kind=MediaKind.IMAGE,
        renditions=(MediaRendition(source_url=source_url),),
        alt_text=alt_text,
    )


_MIME_EXTENSIONS: Mapping[str, str] = {
    "image/avif": ".avif",
    "image/bmp": ".bmp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "video/mp2t": ".ts",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-m4v": ".m4v",
    "video/x-matroska": ".mkv",
}
_IMAGE_EXTENSIONS = frozenset(
    {".avif", ".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
)
_ANIMATION_EXTENSIONS = frozenset({".gif", ".png", ".webp"})
_VIDEO_EXTENSIONS = frozenset({".m4v", ".mkv", ".mov", ".mp4", ".ts", ".webm"})
_SAFE_STEM = re.compile(r"[^a-z0-9._-]+")


def _archive_filename(asset: MediaAsset, rendition: MediaRendition) -> str:
    stem = _SAFE_STEM.sub("-", asset.id.casefold()).strip("._-")[:48]
    if not stem:
        stem = asset.kind.value
    digest = hashlib.sha256(
        f"{asset.kind.value}\0{asset.id}\0{rendition.source_url}".encode()
    ).hexdigest()[:10]
    return f"{stem}-{digest}{_extension(asset.kind, rendition)}"


def _extension(kind: MediaKind, rendition: MediaRendition) -> str:
    allowed = _allowed_extensions(kind)
    mime_type = (rendition.mime_type or "").partition(";")[0].strip().casefold()
    mime_extension = _MIME_EXTENSIONS.get(mime_type)
    if mime_extension is not None and mime_extension in allowed:
        return mime_extension

    path_suffix = PurePosixPath(unquote(urlsplit(rendition.source_url).path)).suffix.casefold()
    if path_suffix == ".jpeg":
        path_suffix = ".jpg"
    if path_suffix in allowed:
        return path_suffix

    if kind is MediaKind.VIDEO:
        return ".mp4"
    if kind is MediaKind.ANIMATION:
        return ".gif"
    return ".jpg"


def _allowed_extensions(kind: MediaKind) -> Collection[str]:
    if kind is MediaKind.VIDEO:
        return _VIDEO_EXTENSIONS
    if kind is MediaKind.ANIMATION:
        return _ANIMATION_EXTENSIONS
    return _IMAGE_EXTENSIONS
