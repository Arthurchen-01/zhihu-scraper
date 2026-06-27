"""
scraper_contracts.py - Stable result contracts for scraper flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple


@dataclass(frozen=True)
class ScrapedItem:
    id: str
    type: str
    url: str
    title: str
    author: str
    html: str
    date: str
    upvotes: int = 0

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ScrapedItem":
        return cls(
            id=str(raw.get("id", "")),
            type=raw.get("type", "unknown"),
            url=raw.get("url", ""),
            title=raw.get("title", ""),
            author=raw.get("author", ""),
            html=raw.get("html", ""),
            date=raw.get("date", ""),
            upvotes=raw.get("upvotes", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "url": self.url,
            "title": self.title,
            "author": self.author,
            "html": self.html,
            "date": self.date,
            "upvotes": self.upvotes,
        }
        return payload


@dataclass(frozen=True)
class PaginationStats:
    requested_limit: int
    saved_count: int
    pages_fetched: int
    last_offset: int
    reached_end: bool
    stopped_early: bool

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "PaginationStats":
        return cls(
            requested_limit=raw.get("requested_limit", 0),
            saved_count=raw.get("saved_count", 0),
            pages_fetched=raw.get("pages_fetched", 0),
            last_offset=raw.get("last_offset", 0),
            reached_end=raw.get("reached_end", False),
            stopped_early=raw.get("stopped_early", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_limit": self.requested_limit,
            "saved_count": self.saved_count,
            "pages_fetched": self.pages_fetched,
            "last_offset": self.last_offset,
            "reached_end": self.reached_end,
            "stopped_early": self.stopped_early,
        }


@dataclass(frozen=True)
class PageFetchResult:
    source_url: str
    page_type: str
    items: Tuple[ScrapedItem, ...]
    pagination: Optional[PaginationStats] = None

    @property
    def is_empty(self) -> bool:
        return not self.items

    def to_legacy_payload(self) -> Any:
        payload = [item.to_dict() for item in self.items]
        if self.page_type == "question":
            return payload
        return payload[0] if payload else {}


def to_scraped_items(items: Iterable[Dict[str, Any]]) -> Tuple[ScrapedItem, ...]:
    return tuple(ScrapedItem.from_dict(item) for item in items)
