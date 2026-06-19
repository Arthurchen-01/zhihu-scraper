"""High-level public API for embedding zhihu-scraper in other apps.

The functions in this module intentionally return typed contracts instead of
printing UI output. They can be used by CLIs, desktop shells, web backends, or
mobile bridges that need the same archive logic without depending on the TUI.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from cli.contracts import BatchWorkflowResult, CreatorWorkflowResult, MonitorWorkflowResult, UrlTaskResult
from cli.workflow_service import build_scrape_config_for_url, get_workflow_service


def _silent_printer(*_args, **_kwargs) -> None:
    """Drop workflow progress messages for embedding callers."""


@dataclass(frozen=True)
class ArchiveOptions:
    """Options shared by public archive entrypoints."""

    output_dir: str | Path = Path("data")
    question_limit: int | None = None
    question_start: int = 0
    download_images: bool = True
    headless: bool = True
    stop_on_error: bool = True
    collection_id: str | None = None
    silent: bool = True

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)


@dataclass(frozen=True)
class CreatorArchiveOptions:
    """Options for archiving a Zhihu creator profile."""

    output_dir: str | Path = Path("data")
    answer_limit: int = 10
    article_limit: int = 5
    download_images: bool = True
    silent: bool = True

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)


@dataclass(frozen=True)
class MonitorOptions:
    """Options for collection monitoring through the public API."""

    output_dir: str | Path = Path("data")
    concurrency: int = 4
    download_images: bool = True
    headless: bool = True
    silent: bool = True

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)


def _service(*, silent: bool):
    printer = _silent_printer if silent else None
    return get_workflow_service(printer=printer or print)


async def archive_url(url: str, options: ArchiveOptions | None = None) -> UrlTaskResult:
    """Archive a single Zhihu URL and return a typed result contract."""
    resolved = options or ArchiveOptions()
    scrape_config = build_scrape_config_for_url(
        url,
        question_limit=resolved.question_limit,
        question_start=resolved.question_start,
    )
    return await _service(silent=resolved.silent).run_single_fetch(
        url=url,
        output_dir=resolved.output_path,
        scrape_config=scrape_config,
        download_images=resolved.download_images,
        headless=resolved.headless,
        collection_id=resolved.collection_id,
    )


async def archive_urls(
    urls: Sequence[str],
    options: ArchiveOptions | None = None,
) -> BatchWorkflowResult:
    """Archive multiple URLs sequentially with the same stable contracts as the CLI."""
    resolved = options or ArchiveOptions()
    return await _service(silent=resolved.silent).run_fetch_urls(
        urls=tuple(urls),
        output_dir=resolved.output_path,
        limit=resolved.question_limit,
        download_images=resolved.download_images,
        headless=resolved.headless,
        stop_on_error=resolved.stop_on_error,
        collection_id=resolved.collection_id,
    )


async def archive_creator(
    creator: str,
    options: CreatorArchiveOptions | None = None,
) -> CreatorWorkflowResult:
    """Archive answers/articles from a creator profile or URL token."""
    resolved = options or CreatorArchiveOptions()
    return await _service(silent=resolved.silent).run_creator(
        creator=creator,
        output_dir=resolved.output_path,
        answer_limit=resolved.answer_limit,
        article_limit=resolved.article_limit,
        download_images=resolved.download_images,
    )


async def monitor_collection(
    collection_id: str,
    options: MonitorOptions | None = None,
) -> MonitorWorkflowResult:
    """Run one collection monitor pass and archive supported new items."""
    resolved = options or MonitorOptions()
    return await _service(silent=resolved.silent).run_monitor(
        collection_id=collection_id,
        output_dir=resolved.output_path,
        concurrency=resolved.concurrency,
        download_images=resolved.download_images,
        headless=resolved.headless,
    )


def archive_url_sync(url: str, options: ArchiveOptions | None = None) -> UrlTaskResult:
    """Synchronous wrapper for scripts and simple desktop/mobile bridges."""
    return asyncio.run(archive_url(url, options))


def archive_urls_sync(
    urls: Sequence[str],
    options: ArchiveOptions | None = None,
) -> BatchWorkflowResult:
    """Synchronous wrapper for archiving multiple URLs."""
    return asyncio.run(archive_urls(urls, options))


def archive_creator_sync(
    creator: str,
    options: CreatorArchiveOptions | None = None,
) -> CreatorWorkflowResult:
    """Synchronous wrapper for creator archiving."""
    return asyncio.run(archive_creator(creator, options))


def monitor_collection_sync(
    collection_id: str,
    options: MonitorOptions | None = None,
) -> MonitorWorkflowResult:
    """Synchronous wrapper for collection monitoring."""
    return asyncio.run(monitor_collection(collection_id, options))


__all__ = [
    "ArchiveOptions",
    "CreatorArchiveOptions",
    "MonitorOptions",
    "archive_creator",
    "archive_creator_sync",
    "archive_url",
    "archive_url_sync",
    "archive_urls",
    "archive_urls_sync",
    "monitor_collection",
    "monitor_collection_sync",
]
