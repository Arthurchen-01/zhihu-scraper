"""
contracts.py - Unified result contracts for zhihu-scraper CLI and TUI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.scraper_contracts import CreatorProfileSummary, PaginationStats, ScrapedItem


@dataclass(frozen=True)
class SavedContentRecord:
    item: ScrapedItem
    folder: Path
    markdown_path: Path

    @classmethod
    def from_legacy_dict(cls, raw: Dict) -> SavedContentRecord:
        return cls(
            item=ScrapedItem.from_dict(raw["item"]),
            folder=Path(raw["folder"]),
            markdown_path=Path(raw["markdown_path"]),
        )

    def to_legacy_dict(self) -> Dict:
        return {
            "item": self.item.to_dict(),
            "folder": self.folder,
            "markdown_path": self.markdown_path,
        }


@dataclass(frozen=True)
class SaveRunResult:
    source_url: str
    content_root: Path
    records: Tuple[SavedContentRecord, ...]
    collection_id: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return not self.records

    @property
    def saved_count(self) -> int:
        return len(self.records)

    @property
    def markdown_paths(self) -> Tuple[str, ...]:
        return tuple(str(record.markdown_path) for record in self.records)

    def to_legacy_records(self) -> List[Dict]:
        return [record.to_legacy_dict() for record in self.records]


class SavePipelineError(RuntimeError):
    """Typed save-pipeline failure with partial archive context."""

    def __init__(
        self,
        message: str,
        *,
        partial_result: SaveRunResult,
        failed_item: ScrapedItem,
        failed_markdown_path: Path,
    ) -> None:
        super().__init__(message)
        self.partial_result = partial_result
        self.failed_item = failed_item
        self.failed_markdown_path = failed_markdown_path

    @property
    def saved_count(self) -> int:
        return self.partial_result.saved_count


@dataclass(frozen=True)
class CreatorSaveResult:
    creator: CreatorProfileSummary
    save_result: SaveRunResult
    answers: PaginationStats
    articles: PaginationStats


@dataclass(frozen=True)
class UrlTaskResult:
    url: str
    success: bool
    save_result: Optional[SaveRunResult] = None
    partial_save_result: Optional[SaveRunResult] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class BatchWorkflowResult:
    items: Tuple[UrlTaskResult, ...]

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.items if item.success)

    @property
    def failed_count(self) -> int:
        return self.total_count - self.success_count

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0


@dataclass(frozen=True)
class CreatorWorkflowResult:
    creator: str
    result: Optional[CreatorSaveResult]

    @property
    def success(self) -> bool:
        return self.result is not None


@dataclass(frozen=True)
class MonitorWorkflowResult:
    collection_id: str
    discovered_count: int
    batch: BatchWorkflowResult
    pointer_advanced: bool
    unsupported_count: int = 0
    next_pointer: Optional[str] = None

    @property
    def has_new_items(self) -> bool:
        return self.discovered_count > 0

    @property
    def has_new_activity(self) -> bool:
        return self.discovered_count + self.unsupported_count > 0
