"""Unified result contracts for CLI and public archive workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.contracts import SavePipelineError, SaveRunResult



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

