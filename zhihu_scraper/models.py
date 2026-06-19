"""Public data contracts re-exported from existing internal modules."""

from cli.contracts import (
    BatchWorkflowResult,
    CreatorSaveResult,
    CreatorWorkflowResult,
    MonitorWorkflowResult,
    SaveRunResult,
    SavedContentRecord,
    UrlTaskResult,
)
from core.scraper_contracts import (
    CreatorFetchResult,
    CreatorProfileSummary,
    PageFetchResult,
    PaginationStats,
    ScrapedItem,
    to_scraped_items,
)

__all__ = [
    "BatchWorkflowResult",
    "CreatorFetchResult",
    "CreatorProfileSummary",
    "CreatorSaveResult",
    "CreatorWorkflowResult",
    "MonitorWorkflowResult",
    "PageFetchResult",
    "PaginationStats",
    "SaveRunResult",
    "SavedContentRecord",
    "ScrapedItem",
    "UrlTaskResult",
    "to_scraped_items",
]
