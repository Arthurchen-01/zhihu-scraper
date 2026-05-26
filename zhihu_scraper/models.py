"""Public data contracts re-exported from existing internal modules."""

from cli.contracts import CreatorSaveResult, SaveRunResult, SavedContentRecord
from core.scraper_contracts import (
    CreatorFetchResult,
    CreatorProfileSummary,
    PageFetchResult,
    PaginationStats,
    ScrapedItem,
    to_scraped_items,
)

__all__ = [
    "CreatorFetchResult",
    "CreatorProfileSummary",
    "CreatorSaveResult",
    "PageFetchResult",
    "PaginationStats",
    "SaveRunResult",
    "SavedContentRecord",
    "ScrapedItem",
    "to_scraped_items",
]
