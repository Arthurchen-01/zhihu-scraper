"""
Public facade package for zhihu-scraper.

This package intentionally re-exports existing implementation objects from
``core`` and ``cli`` without moving code or changing CLI behavior.
"""

from .config import Config, ConfigLoader, build_default_config, get_config, update_config
from .api import (
    ArchiveOptions,
    CreatorArchiveOptions,
    MonitorOptions,
    archive_creator,
    archive_creator_sync,
    archive_url,
    archive_url_sync,
    archive_urls,
    archive_urls_sync,
    monitor_collection,
    monitor_collection_sync,
)
from .fetching import ZhihuCreatorDownloader, ZhihuDownloader
from .markdown import ZhihuConverter
from .models import (
    CreatorFetchResult,
    CreatorProfileSummary,
    CreatorSaveResult,
    PageFetchResult,
    PaginationStats,
    SaveRunResult,
    SavedContentRecord,
    ScrapedItem,
)
from .services import ArchiveWorkflowService, WorkflowServiceConfig
from .storage import SavePipelineSettings, ZhihuDatabase

__all__ = [
    "ArchiveOptions",
    "ArchiveWorkflowService",
    "Config",
    "ConfigLoader",
    "CreatorArchiveOptions",
    "CreatorFetchResult",
    "CreatorProfileSummary",
    "CreatorSaveResult",
    "MonitorOptions",
    "PageFetchResult",
    "PaginationStats",
    "SavePipelineSettings",
    "SaveRunResult",
    "SavedContentRecord",
    "ScrapedItem",
    "WorkflowServiceConfig",
    "ZhihuConverter",
    "ZhihuCreatorDownloader",
    "ZhihuDatabase",
    "ZhihuDownloader",
    "archive_creator",
    "archive_creator_sync",
    "archive_url",
    "archive_url_sync",
    "archive_urls",
    "archive_urls_sync",
    "build_default_config",
    "get_config",
    "monitor_collection",
    "monitor_collection_sync",
    "update_config",
]
