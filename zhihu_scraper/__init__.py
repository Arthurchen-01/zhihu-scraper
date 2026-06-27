"""
Public facade package for zhihu-scraper.

This package intentionally re-exports existing implementation objects from
``core`` and ``cli`` without moving code or changing CLI behavior.
"""

from .config import Config, ConfigLoader, build_default_config, get_config, update_config
from .api import (
    ArchiveOptions,
    archive_url,
    archive_url_sync,
    archive_urls,
    archive_urls_sync,
)
from .fetching import ZhihuDownloader
from .markdown import ZhihuConverter
from .models import (
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
    "PageFetchResult",
    "PaginationStats",
    "SavePipelineSettings",
    "SaveRunResult",
    "SavedContentRecord",
    "ScrapedItem",
    "WorkflowServiceConfig",
    "ZhihuConverter",
    "ZhihuDatabase",
    "ZhihuDownloader",
    "archive_url",
    "archive_url_sync",
    "archive_urls",
    "archive_urls_sync",
    "build_default_config",
    "get_config",
    "update_config",
]
