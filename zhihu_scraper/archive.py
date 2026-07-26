"""Local archive interface for normalized Zhihu content."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .domain import Article
from .render import HtmlRenderer, MarkdownRenderer, content_plain_text


@dataclass(frozen=True, slots=True)
class ArchiveReceipt:
    entry_directory: Path
    markdown_path: Path
    html_path: Path
    database_path: Path


class LocalArchive:
    """Write normalized content into a self-contained local archive library."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def archive(self, article: Article) -> ArchiveReceipt:
        entry_directory = self._root / article.title
        entry_directory.mkdir(parents=True, exist_ok=True)

        markdown_path = entry_directory / f"{article.title}.md"
        html_path = entry_directory / f"{article.title}.html"
        database_path = self._root / "zhihu.db"

        markdown_renderer = MarkdownRenderer()
        html_renderer = HtmlRenderer()
        markdown_path.write_text(markdown_renderer.render(article), encoding="utf-8")
        html_path.write_text(html_renderer.render(article), encoding="utf-8")
        assets_directory = entry_directory / "assets"
        assets_directory.mkdir(exist_ok=True)
        for filename, content in html_renderer.assets().items():
            (assets_directory / filename).write_text(content, encoding="utf-8")
        self._save_article(database_path, article)

        return ArchiveReceipt(
            entry_directory=entry_directory,
            markdown_path=markdown_path,
            html_path=html_path,
            database_path=database_path,
        )

    @staticmethod
    def _save_article(database_path: Path, article: Article) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    author_name TEXT NOT NULL,
                    published_at TEXT,
                    body_text TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO articles (
                    id,
                    title,
                    source_url,
                    author_id,
                    author_name,
                    published_at,
                    body_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    source_url = excluded.source_url,
                    author_id = excluded.author_id,
                    author_name = excluded.author_name,
                    published_at = excluded.published_at,
                    body_text = excluded.body_text
                """,
                (
                    article.id,
                    article.title,
                    article.source_url,
                    article.author.id,
                    article.author.name,
                    article.published_at.isoformat() if article.published_at else None,
                    content_plain_text(article.blocks),
                ),
            )
