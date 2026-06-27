"""High-level public API for embedding zhihu-scraper in other apps."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from cli.contracts import BatchWorkflowResult, UrlTaskResult
from cli.workflow_service import build_scrape_config_for_url, get_workflow_service
from core.config_runtime import get_config, resolve_project_path


def _silent_printer(*_args, **_kwargs) -> None:
    """Drop workflow progress messages for embedding callers."""


def _resolve_output_path(value: str | Path | None) -> Path:
    configured = get_config().local.output_dir if value is None else value
    path = Path(configured)
    return path if path.is_absolute() else resolve_project_path(path)


@dataclass(frozen=True)
class ArchiveOptions:
    """Options shared by public archive entrypoints."""

    output_dir: str | Path | None = None
    question_limit: int | None = None
    question_start: int = 0
    download_images: bool = True
    headless: bool = True
    stop_on_error: bool = True
    silent: bool = True

    @property
    def output_path(self) -> Path:
        return _resolve_output_path(self.output_dir)


def _service(*, silent: bool):
    printer = _silent_printer if silent else print
    return get_workflow_service(printer=printer)


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
    )


async def archive_urls(
    urls: Sequence[str],
    options: ArchiveOptions | None = None,
) -> BatchWorkflowResult:
    """Archive multiple URLs sequentially with the same contracts as the CLI."""
    resolved = options or ArchiveOptions()
    return await _service(silent=resolved.silent).run_fetch_urls(
        urls=tuple(urls),
        output_dir=resolved.output_path,
        limit=resolved.question_limit,
        download_images=resolved.download_images,
        headless=resolved.headless,
        stop_on_error=resolved.stop_on_error,
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


__all__ = [
    "ArchiveOptions",
    "archive_url",
    "archive_url_sync",
    "archive_urls",
    "archive_urls_sync",
]
