"""Normalized content contracts for the rebuilt archive core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Author:
    id: str
    name: str
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Paragraph:
    text: str


@dataclass(frozen=True, slots=True)
class Article:
    id: str
    title: str
    source_url: str
    author: Author
    published_at: datetime | None
    blocks: tuple[Paragraph, ...]
