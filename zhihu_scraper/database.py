"""SQLite repository for normalized archive entities and deterministic relations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

from .domain import (
    Answer,
    ArchiveTarget,
    Article,
    Author,
    Block,
    Column,
    ColumnArchive,
    Comment,
    CommentThread,
    ListBlock,
    MediaAsset,
    MediaBlock,
    Question,
    QuestionArchive,
    Quote,
    Video,
)
from .render import content_plain_text


_SCHEMA = """
CREATE TABLE IF NOT EXISTS contents (
    content_key TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    zhihu_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    author_id TEXT,
    author_name TEXT,
    published_at TEXT,
    updated_at TEXT,
    body_text TEXT NOT NULL,
    archived_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS contents_type_id
ON contents(type, zhihu_id);

CREATE TABLE IF NOT EXISTS authors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT
);

CREATE TABLE IF NOT EXISTS columns (
    token TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    description TEXT NOT NULL,
    author_id TEXT,
    item_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS relations (
    subject_key TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_key TEXT NOT NULL,
    source_url TEXT NOT NULL,
    PRIMARY KEY (subject_key, predicate, object_key)
);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT NOT NULL,
    content_key TEXT NOT NULL,
    parent_id TEXT,
    depth INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    author_id TEXT,
    author_name TEXT,
    created_at TEXT,
    like_count INTEGER NOT NULL,
    body_text TEXT NOT NULL,
    replies_complete INTEGER NOT NULL,
    PRIMARY KEY (content_key, id)
);

CREATE TABLE IF NOT EXISTS comment_fetches (
    content_key TEXT PRIMARY KEY,
    source_order TEXT NOT NULL,
    roots_complete INTEGER NOT NULL,
    root_limit INTEGER NOT NULL,
    reply_limit INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS media (
    content_key TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    archive_path TEXT,
    mime_type TEXT,
    width INTEGER,
    height INTEGER,
    bitrate INTEGER,
    size_bytes INTEGER,
    PRIMARY KEY (content_key, asset_id, source_url)
);
"""


class ArchiveDatabase:
    """Idempotently persist one normalized archive target."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def save(
        self,
        target: ArchiveTarget,
        *,
        media_paths: Mapping[str, str] | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.executescript(_SCHEMA)
            if isinstance(target, Article):
                self._save_article(connection, target, media_paths=media_paths or {})
            elif isinstance(target, Answer):
                self._save_answer(connection, target, media_paths=media_paths or {})
            elif isinstance(target, QuestionArchive):
                self._save_question_archive(
                    connection,
                    target,
                    media_paths=media_paths or {},
                )
            elif isinstance(target, ColumnArchive):
                self._save_column_archive(
                    connection,
                    target,
                    media_paths=media_paths or {},
                )
            elif isinstance(target, Video):
                self._save_video(connection, target, media_paths=media_paths or {})
            else:
                raise TypeError(f"unsupported archive target: {type(target).__name__}")

    def _save_article(
        self,
        connection: sqlite3.Connection,
        article: Article,
        *,
        media_paths: Mapping[str, str],
    ) -> None:
        key = f"article:{article.id}"
        self._save_content(
            connection,
            key=key,
            content_type="article",
            zhihu_id=article.id,
            title=article.title,
            source_url=article.source_url,
            author=article.author,
            published_at=article.published_at,
            updated_at=article.updated_at,
            blocks=article.blocks,
        )
        for column in article.columns:
            connection.execute(
                """
                INSERT INTO columns (
                    token, title, source_url, description, author_id, item_count
                ) VALUES (?, ?, ?, '', NULL, 0)
                ON CONFLICT(token) DO UPDATE SET
                    title = excluded.title,
                    source_url = excluded.source_url
                """,
                (column.token, column.title, column.url),
            )
            self._save_relation(
                connection,
                key,
                "included_in",
                f"column:{column.token}",
                article.source_url,
            )
        self._replace_media(
            connection,
            key,
            article.source_url,
            article.blocks,
            media_paths=media_paths,
        )
        self._replace_comments(connection, key, article.source_url, article.comments)

    def _save_answer(
        self,
        connection: sqlite3.Connection,
        answer: Answer,
        *,
        media_paths: Mapping[str, str],
    ) -> None:
        key = f"answer:{answer.id}"
        self._save_content(
            connection,
            key=key,
            content_type="answer",
            zhihu_id=answer.id,
            title=answer.title,
            source_url=answer.source_url,
            author=answer.author,
            published_at=answer.published_at,
            updated_at=answer.updated_at,
            blocks=answer.blocks,
        )
        self._save_relation(
            connection,
            key,
            "answers",
            f"question:{answer.question.id}",
            answer.source_url,
        )
        self._replace_media(
            connection,
            key,
            answer.source_url,
            answer.blocks,
            media_paths=media_paths,
        )
        self._replace_comments(connection, key, answer.source_url, answer.comments)

    def _save_question_archive(
        self,
        connection: sqlite3.Connection,
        archive: QuestionArchive,
        *,
        media_paths: Mapping[str, str],
    ) -> None:
        self._save_question(
            connection,
            archive.question,
            archive.archived_at,
            media_paths=media_paths,
        )
        for answer in archive.answers:
            self._save_answer(connection, answer, media_paths=media_paths)

    def _save_question(
        self,
        connection: sqlite3.Connection,
        question: Question,
        archived_at: datetime | None = None,
        *,
        media_paths: Mapping[str, str],
    ) -> None:
        self._save_content(
            connection,
            key=f"question:{question.id}",
            content_type="question",
            zhihu_id=question.id,
            title=question.title,
            source_url=question.source_url,
            author=question.author,
            published_at=question.created_at,
            updated_at=question.updated_at,
            blocks=question.detail,
            archived_at=archived_at,
        )
        self._replace_media(
            connection,
            f"question:{question.id}",
            question.source_url,
            question.detail,
            media_paths=media_paths,
        )

    def _save_column_archive(
        self,
        connection: sqlite3.Connection,
        archive: ColumnArchive,
        *,
        media_paths: Mapping[str, str],
    ) -> None:
        column = archive.column
        self._save_column(connection, column)
        for article in archive.articles:
            self._save_article(connection, article, media_paths=media_paths)
            self._save_relation(
                connection,
                f"article:{article.id}",
                "archived_from",
                f"column:{column.token}",
                column.source_url,
            )

    def _save_column(
        self,
        connection: sqlite3.Connection,
        column: Column,
    ) -> None:
        self._save_author(connection, column.author)
        connection.execute(
            """
            INSERT INTO columns (
                token, title, source_url, description, author_id, item_count
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                title = excluded.title,
                source_url = excluded.source_url,
                description = excluded.description,
                author_id = excluded.author_id,
                item_count = excluded.item_count
            """,
            (
                column.token,
                column.title,
                column.source_url,
                column.description,
                column.author.id if column.author else None,
                column.item_count,
            ),
        )

    def _save_video(
        self,
        connection: sqlite3.Connection,
        video: Video,
        *,
        media_paths: Mapping[str, str],
    ) -> None:
        key = f"video:{video.id}"
        self._save_content(
            connection,
            key=key,
            content_type="video",
            zhihu_id=video.id,
            title=video.title,
            source_url=video.source_url,
            author=video.author,
            published_at=video.published_at,
            updated_at=video.updated_at,
            blocks=video.description,
        )
        self._replace_media_assets(
            connection,
            key,
            video.source_url,
            (video.asset,),
            media_paths=media_paths,
        )
        self._replace_comments(connection, key, video.source_url, video.comments)

    def _save_content(
        self,
        connection: sqlite3.Connection,
        *,
        key: str,
        content_type: str,
        zhihu_id: str,
        title: str,
        source_url: str,
        author: Author | None,
        published_at: datetime | None,
        updated_at: datetime | None,
        blocks: Sequence[Block],
        archived_at: datetime | None = None,
    ) -> None:
        self._save_author(connection, author)
        connection.execute(
            """
            INSERT INTO contents (
                content_key, type, zhihu_id, title, source_url,
                author_id, author_name, published_at, updated_at,
                body_text, archived_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(content_key) DO UPDATE SET
                title = excluded.title,
                source_url = excluded.source_url,
                author_id = excluded.author_id,
                author_name = excluded.author_name,
                published_at = excluded.published_at,
                updated_at = excluded.updated_at,
                body_text = excluded.body_text,
                archived_at = excluded.archived_at
            """,
            (
                key,
                content_type,
                zhihu_id,
                title,
                source_url,
                author.id if author else None,
                author.name if author else None,
                _isoformat(published_at),
                _isoformat(updated_at),
                content_plain_text(blocks),
                _isoformat(archived_at or datetime.now(timezone.utc)),
            ),
        )
        if author and author.id:
            self._save_relation(
                connection,
                key,
                "authored_by",
                f"author:{author.id}",
                source_url,
            )

    @staticmethod
    def _save_author(
        connection: sqlite3.Connection,
        author: Author | None,
    ) -> None:
        if not author or not author.id:
            return
        connection.execute(
            """
            INSERT INTO authors (id, name, url) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                url = COALESCE(excluded.url, authors.url)
            """,
            (author.id, author.name, author.url),
        )

    @staticmethod
    def _save_relation(
        connection: sqlite3.Connection,
        subject_key: str,
        predicate: str,
        object_key: str,
        source_url: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO relations (
                subject_key, predicate, object_key, source_url
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(subject_key, predicate, object_key) DO UPDATE SET
                source_url = excluded.source_url
            """,
            (subject_key, predicate, object_key, source_url),
        )

    def _replace_media(
        self,
        connection: sqlite3.Connection,
        content_key: str,
        source_url: str,
        blocks: Sequence[Block],
        *,
        media_paths: Mapping[str, str],
    ) -> None:
        self._replace_media_assets(
            connection,
            content_key,
            source_url,
            tuple(_walk_media(blocks)),
            media_paths=media_paths,
        )

    def _replace_media_assets(
        self,
        connection: sqlite3.Connection,
        content_key: str,
        source_url: str,
        assets: Sequence[MediaAsset],
        *,
        media_paths: Mapping[str, str],
    ) -> None:
        connection.execute("DELETE FROM media WHERE content_key = ?", (content_key,))
        for ordinal, asset in enumerate(assets):
            for rendition in asset.renditions:
                connection.execute(
                    """
                    INSERT INTO media (
                        content_key, asset_id, kind, ordinal, source_url,
                        archive_path, mime_type, width, height, bitrate, size_bytes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        content_key,
                        asset.id,
                        asset.kind.value,
                        ordinal,
                        rendition.source_url,
                        (
                            asset.archive_path
                            or media_paths.get(rendition.source_url)
                            or media_paths.get(asset.id)
                        ),
                        rendition.mime_type,
                        rendition.width,
                        rendition.height,
                        rendition.bitrate,
                        rendition.size_bytes,
                    ),
                )
            self._save_relation(
                connection,
                content_key,
                "contains",
                f"media:{asset.id}",
                source_url,
            )

    def _replace_comments(
        self,
        connection: sqlite3.Connection,
        content_key: str,
        source_url: str,
        thread: CommentThread | None,
    ) -> None:
        if thread is None:
            return
        connection.execute("DELETE FROM comments WHERE content_key = ?", (content_key,))
        connection.execute(
            """
            INSERT INTO comment_fetches (
                content_key, source_order, roots_complete, root_limit, reply_limit
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(content_key) DO UPDATE SET
                source_order = excluded.source_order,
                roots_complete = excluded.roots_complete,
                root_limit = excluded.root_limit,
                reply_limit = excluded.reply_limit
            """,
            (
                content_key,
                thread.order,
                int(thread.roots_complete),
                thread.root_limit,
                thread.reply_limit,
            ),
        )
        for ordinal, comment in enumerate(thread.comments):
            self._save_comment(
                connection,
                content_key=content_key,
                source_url=source_url,
                comment=comment,
                parent_id=None,
                depth=0,
                ordinal=ordinal,
            )

    def _save_comment(
        self,
        connection: sqlite3.Connection,
        *,
        content_key: str,
        source_url: str,
        comment: Comment,
        parent_id: str | None,
        depth: int,
        ordinal: int,
    ) -> None:
        self._save_author(connection, comment.author)
        connection.execute(
            """
            INSERT INTO comments (
                id, content_key, parent_id, depth, ordinal,
                author_id, author_name, created_at, like_count,
                body_text, replies_complete
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                comment.id,
                content_key,
                parent_id,
                depth,
                ordinal,
                comment.author.id if comment.author else None,
                comment.author.name if comment.author else None,
                _isoformat(comment.created_at),
                comment.like_count,
                content_plain_text(comment.blocks),
                int(comment.replies_complete),
            ),
        )
        self._save_relation(
            connection,
            content_key,
            "has_comment",
            f"comment:{comment.id}",
            source_url,
        )
        if parent_id is not None:
            self._save_relation(
                connection,
                f"comment:{comment.id}",
                "replies_to",
                f"comment:{parent_id}",
                source_url,
            )
        for reply_ordinal, reply in enumerate(comment.replies):
            self._save_comment(
                connection,
                content_key=content_key,
                source_url=source_url,
                comment=reply,
                parent_id=comment.id,
                depth=depth + 1,
                ordinal=reply_ordinal,
            )


def _walk_media(blocks: Iterable[Block]) -> Iterable[MediaAsset]:
    for block in blocks:
        if isinstance(block, MediaBlock):
            yield block.asset
        elif isinstance(block, Quote):
            yield from _walk_media(block.blocks)
        elif isinstance(block, ListBlock):
            for item in block.items:
                yield from _walk_media(item)


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
