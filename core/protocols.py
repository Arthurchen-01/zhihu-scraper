"""
protocols.py - Typed extension points for reusable archive services.

These protocols define the stable seams future entrypoints can depend on
without importing CLI presenters or concrete runtime singletons.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, Tuple

from .scraper_contracts import PageFetchResult, ScrapedItem


@dataclass(frozen=True)
class ProgressEvent:
    """Structured progress event emitted by reusable services."""

    type: str
    message: str = ""
    severity: str = "info"
    phase: Optional[str] = None
    current: Optional[int] = None
    total: Optional[int] = None
    payload: Mapping[str, Any] | None = None


EventSink = Callable[[ProgressEvent], None]


def noop_event_sink(_event: ProgressEvent) -> None:
    """Default event sink for library use."""


@dataclass(frozen=True)
class SearchQuery:
    """Typed query request for archive search services."""

    keyword: str
    limit: int = 10
    item_type: Optional[str] = None
    collection_id: Optional[str] = None


@dataclass(frozen=True)
class SearchHit:
    """Typed search result returned by archive search services."""

    content_key: str
    item_id: str
    item_type: str
    title: str
    author: str
    url: str
    created_at: str
    markdown_path: Optional[Path] = None
    collection_id: Optional[str] = None


class Fetcher(Protocol):
    """Fetch one Zhihu URL and return normalized content."""

    async def fetch_result(self, **kwargs: Any) -> PageFetchResult:
        ...


class ArchiveStore(Protocol):
    """Persistence boundary for archived content."""

    def save_item(
        self,
        item: ScrapedItem,
        markdown: str,
        *,
        collection_id: Optional[str] = None,
        markdown_path: Optional[Path] = None,
    ) -> bool:
        ...

    def exists(self, item_id: str, item_type: Optional[str] = None) -> bool:
        ...


class SearchStore(Protocol):
    """Search boundary over archived content."""

    def search(self, query: SearchQuery) -> Tuple[SearchHit, ...]:
        ...


class MediaDownloader(Protocol):
    """Image downloader boundary used by archive services."""

    async def download_images(
        self,
        urls: Sequence[str],
        output_dir: Path,
        **kwargs: Any,
    ) -> dict[str, str]:
        ...


class MarkdownConverter(Protocol):
    """HTML-to-Markdown conversion boundary."""

    def convert(self, html: str) -> str:
        ...
