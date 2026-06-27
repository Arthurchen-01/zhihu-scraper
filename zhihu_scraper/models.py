"""Public data contracts re-exported from existing internal modules."""

from cli.contracts import (
    BatchWorkflowResult,
    UrlTaskResult,
)
from core.contracts import SaveRunResult, SavedContentRecord
from core.scraper_contracts import (
    PageFetchResult,
    PaginationStats,
    ScrapedItem,
    to_scraped_items,
)

__all__ = [
    "BatchWorkflowResult",
    "PageFetchResult",
    "PaginationStats",
    "SaveRunResult",
    "SavedContentRecord",
    "ScrapedItem",
    "UrlTaskResult",
    "to_scraped_items",
]
