"""
Public facade package for zhihu-scraper.

This package intentionally re-exports existing implementation objects from
``core`` and ``cli`` without moving code or changing CLI behavior.
"""

from .config import Config, ConfigLoader, build_default_config, get_config, update_config
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
    "ArchiveWorkflowService",
    "Config",
    "ConfigLoader",
    "CreatorFetchResult",
    "CreatorProfileSummary",
    "CreatorSaveResult",
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
    "build_default_config",
    "get_config",
    "update_config",
]
