"""Local archive interface for normalized Zhihu content."""

from __future__ import annotations

import html
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .domain import Article


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

        markdown_path.write_text(self._render_markdown(article), encoding="utf-8")
        html_path.write_text(self._render_html(article), encoding="utf-8")
        self._save_article(database_path, article)

        return ArchiveReceipt(
            entry_directory=entry_directory,
            markdown_path=markdown_path,
            html_path=html_path,
            database_path=database_path,
        )

    @staticmethod
    def _render_markdown(article: Article) -> str:
        metadata = [
            f"# {article.title}",
            "",
            f"> 作者：{article.author.name}",
            f"> 知乎原文：[{article.source_url}]({article.source_url})",
        ]
        if article.published_at is not None:
            metadata.append(f"> 发布时间：{article.published_at.date().isoformat()}")

        paragraphs = [block.text for block in article.blocks]
        return "\n".join([*metadata, "", *paragraphs, ""])

    @staticmethod
    def _render_html(article: Article) -> str:
        title = html.escape(article.title)
        author = html.escape(article.author.name)
        source_url = html.escape(article.source_url, quote=True)
        published_at = ""
        if article.published_at is not None:
            date = html.escape(article.published_at.date().isoformat())
            published_at = f"\n      <p>发布时间：{date}</p>"
        paragraphs = "\n".join(
            f"      <p>{html.escape(block.text)}</p>" for block in article.blocks
        )
        return (
            "<!doctype html>\n"
            '<html lang="zh-CN">\n'
            "  <head>\n"
            '    <meta charset="utf-8">\n'
            f"    <title>{title}</title>\n"
            "  </head>\n"
            "  <body>\n"
            "    <article>\n"
            f"      <h1>{title}</h1>\n"
            f"      <p>作者：{author}</p>{published_at}\n"
            f'      <p><a href="{source_url}">知乎原文</a></p>\n'
            f"{paragraphs}\n"
            "    </article>\n"
            "  </body>\n"
            "</html>\n"
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
                    "\n\n".join(block.text for block in article.blocks),
                ),
            )
