"""
workflow_service.py - Application-service layer for CLI archive workflows.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from random import uniform
from typing import Awaitable, Callable, Optional, Sequence

from rich import print as rprint

from cli.contracts import BatchWorkflowResult, SavePipelineError, SaveRunResult, UrlTaskResult
from core.config_runtime import get_config, get_logger
from core.errors import handle_error
from core.protocols import EventSink, ProgressEvent
from core.save_pipeline import SavePipelineSettings, fetch_and_save_result
from core.structlog_compat import BoundLoggerBase


FetchRunner = Callable[..., Awaitable[SaveRunResult]]
Printer = Callable[[str], None]
ErrorHandler = Callable[[Exception, Optional[BoundLoggerBase]], object]
SleepFn = Callable[[float], Awaitable[None]]
DEFAULT_QUESTION_LIMIT = 3


def make_rich_event_sink(printer: Printer) -> EventSink:
    def sink(event: ProgressEvent) -> None:
        if event.type == "save.warning":
            printer(f"[yellow]⚠️ {event.message}[/yellow]")
        elif event.type == "media.download.started":
            printer(f"   📥 {event.message}")
        elif event.type == "save.item.success":
            author = event.payload.get("author") if event.payload else ""
            title = event.payload.get("title") if event.payload else ""
            markdown_path = event.payload.get("markdown_path") if event.payload else ""
            printer(f"✅ Saved / 保存: [cyan]{author}[/] - {title[:25]}...")
            printer(f"   📁 {markdown_path} & DB / 入库 DB")

    return sink


def is_question_listing_url(url: str) -> bool:
    return "/question/" in url and "/answer/" not in url


def build_scrape_config_for_url(
    url: str,
    *,
    question_limit: Optional[int] = None,
    default_question_limit: Optional[int] = None,
    question_start: int = 0,
) -> dict:
    if not is_question_listing_url(url):
        return {}
    resolved_limit = question_limit if question_limit is not None else default_question_limit
    if resolved_limit is None:
        return {}
    return {"start": question_start, "limit": resolved_limit}


@dataclass(frozen=True)
class WorkflowServiceConfig:
    save_settings: SavePipelineSettings
    printer: Printer = rprint
    logger: Optional[BoundLoggerBase] = None


class ArchiveWorkflowService:
    """Reusable application service for CLI and public API archive workflows."""

    def __init__(
        self,
        config: WorkflowServiceConfig,
        *,
        fetch_runner: FetchRunner = fetch_and_save_result,
        error_handler: ErrorHandler = handle_error,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self._config = config
        self._fetch_runner = fetch_runner
        self._error_handler = error_handler
        self._sleep = sleep

    async def run_fetch_urls(
        self,
        *,
        urls: Sequence[str],
        output_dir: Path,
        limit: Optional[int],
        download_images: bool,
        headless: bool,
        stop_on_error: bool = True,
    ) -> BatchWorkflowResult:
        items: list[UrlTaskResult] = []
        for url in urls:
            result = await self.run_single_fetch(
                url=url,
                output_dir=output_dir,
                scrape_config=build_scrape_config_for_url(url, question_limit=limit),
                download_images=download_images,
                headless=headless,
            )
            items.append(result)
            if stop_on_error and not result.success:
                break
        return BatchWorkflowResult(items=tuple(items))

    async def run_batch(
        self,
        *,
        urls: Sequence[str],
        output_dir: Path,
        concurrency: int,
        download_images: bool,
        headless: bool,
        question_limit: Optional[int] = None,
    ) -> BatchWorkflowResult:
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_one(url: str, index: int) -> UrlTaskResult:
            async with semaphore:
                if index > 0:
                    await self._sleep(uniform(0.5, 2.0) * (index % 3 + 1))
                return await self.run_single_fetch(
                    url=url,
                    output_dir=output_dir,
                    scrape_config=build_scrape_config_for_url(url, question_limit=question_limit),
                    download_images=download_images,
                    headless=headless,
                )

        return BatchWorkflowResult(items=tuple(await asyncio.gather(*(fetch_one(url, idx) for idx, url in enumerate(urls)))))

    async def run_single_fetch(
        self,
        *,
        url: str,
        output_dir: Path,
        scrape_config: dict,
        download_images: bool,
        headless: bool,
    ) -> UrlTaskResult:
        try:
            save_result = await self._fetch_runner(
                url=url,
                output_dir=output_dir,
                scrape_config=scrape_config,
                settings=self._config.save_settings,
                download_images=download_images,
                headless=headless,
                event_sink=make_rich_event_sink(self._config.printer),
            )
            return UrlTaskResult(url=url, success=True, save_result=save_result)
        except SavePipelineError as error:
            self._error_handler(error, self._config.logger)
            return UrlTaskResult(
                url=url,
                success=False,
                partial_save_result=error.partial_result,
                error=str(error),
            )
        except Exception as error:
            self._error_handler(error, self._config.logger)
            return UrlTaskResult(url=url, success=False, error=str(error))


def build_save_pipeline_settings() -> SavePipelineSettings:
    cfg = get_config()
    return SavePipelineSettings(
        folder_template=cfg.output.folder_format or "[{date}] {title}",
        images_subdir=cfg.output.images_subdir or "images",
        image_concurrency=cfg.crawler.images.concurrency,
        image_timeout=cfg.crawler.images.timeout,
    )


def get_workflow_service(
    *,
    printer=rprint,
    logger: Optional[BoundLoggerBase] = None,
) -> ArchiveWorkflowService:
    return ArchiveWorkflowService(
        WorkflowServiceConfig(
            save_settings=build_save_pipeline_settings(),
            printer=printer,
            logger=get_logger() if logger is None else logger,
        )
    )


async def fetch_and_save(
    url: str,
    output_dir: Path,
    scrape_config: dict,
    download_images: bool = True,
    headless: bool = True,
) -> list[dict]:
    result = await fetch_and_save_result_helper(
        url=url,
        output_dir=output_dir,
        scrape_config=scrape_config,
        download_images=download_images,
        headless=headless,
    )
    return result.to_legacy_records()


async def fetch_and_save_result_helper(
    url: str,
    output_dir: Path,
    scrape_config: dict,
    download_images: bool = True,
    headless: bool = True,
):
    result = await get_workflow_service().run_single_fetch(
        url=url,
        output_dir=output_dir,
        scrape_config=scrape_config,
        download_images=download_images,
        headless=headless,
    )
    if not result.success or result.save_result is None:
        raise RuntimeError(result.error or f"Fetch failed for {url}")
    return result.save_result
