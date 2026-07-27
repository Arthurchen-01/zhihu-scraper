import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from zhihu_scraper.database import ArchiveDatabase
from zhihu_scraper.domain import (
    Answer,
    Article,
    Author,
    ColumnRef,
    Comment,
    CommentThread,
    MediaAsset,
    MediaBlock,
    MediaKind,
    MediaRendition,
    Paragraph,
    Question,
    QuestionArchive,
    QuestionRef,
    Text,
    Video,
)

NOW = datetime(2026, 7, 26, tzinfo=UTC)


class ArchiveDatabaseTests(unittest.TestCase):
    def test_article_saves_searchable_text_media_comments_and_column_relations(self):
        author = Author(id="writer", name="作者")
        article = Article(
            id="357892158",
            title="数据增强",
            source_url="https://zhuanlan.zhihu.com/p/357892158",
            author=author,
            published_at=NOW,
            blocks=(
                Paragraph((Text("正文关键词"),)),
                MediaBlock(
                    MediaAsset(
                        id="image-1",
                        kind=MediaKind.IMAGE,
                        renditions=(
                            MediaRendition(
                                "https://pic.example/original.png",
                                width=1600,
                                height=900,
                            ),
                        ),
                        archive_path="media/image-1.png",
                    )
                ),
            ),
            columns=(
                ColumnRef(
                    token="machinelearningpku",
                    title="机器学习",
                    url="https://www.zhihu.com/column/machinelearningpku",
                ),
            ),
            comments=CommentThread(
                comments=(
                    Comment(
                        id="comment-1",
                        author=Author(id="reader", name="读者"),
                        blocks=(Paragraph((Text("一级评论"),)),),
                        created_at=NOW,
                        like_count=3,
                        replies=(
                            Comment(
                                id="reply-1",
                                author=None,
                                blocks=(Paragraph((Text("二级回复"),)),),
                                created_at=None,
                                like_count=0,
                                replies_complete=True,
                            ),
                        ),
                        replies_complete=True,
                    ),
                ),
                order="api",
                roots_complete=True,
            ),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "zhihu.db"
            ArchiveDatabase(database_path).save(article)

            with closing(sqlite3.connect(database_path)) as connection:
                content = connection.execute(
                    "SELECT type, body_text FROM contents WHERE content_key = ?",
                    ("article:357892158",),
                ).fetchone()
                relation = connection.execute(
                    """
                    SELECT predicate, object_key FROM relations
                    WHERE subject_key = 'article:357892158'
                      AND predicate = 'included_in'
                    """
                ).fetchone()
                media = connection.execute(
                    """
                    SELECT kind, source_url, archive_path FROM media
                    WHERE content_key = 'article:357892158'
                    """
                ).fetchone()
                comments = connection.execute(
                    """
                    SELECT id, parent_id, body_text FROM comments
                    WHERE content_key = 'article:357892158'
                    ORDER BY depth, ordinal
                    """
                ).fetchall()

        self.assertEqual(("article", "正文关键词"), content)
        self.assertEqual(("included_in", "column:machinelearningpku"), relation)
        self.assertEqual(
            ("image", "https://pic.example/original.png", "media/image-1.png"),
            media,
        )
        self.assertEqual(
            [
                ("comment-1", None, "一级评论"),
                ("reply-1", "comment-1", "二级回复"),
            ],
            comments,
        )

    def test_question_archive_saves_question_answers_and_explicit_relations(self):
        question = Question(
            id="28696373",
            title="如何理解机器学习？",
            source_url="https://www.zhihu.com/question/28696373",
            detail=(
                Paragraph((Text("问题详情"),)),
                MediaBlock(
                    MediaAsset(
                        id="question-image",
                        kind=MediaKind.IMAGE,
                        renditions=(MediaRendition("https://pic.example/question.png"),),
                    )
                ),
            ),
            answer_count=1,
        )
        answer = Answer(
            id="2835848212",
            question=QuestionRef(
                id=question.id,
                title=question.title,
                url=question.source_url,
            ),
            source_url=("https://www.zhihu.com/question/28696373/answer/2835848212"),
            author=Author(id="answerer", name="回答者"),
            published_at=NOW,
            blocks=(
                Paragraph((Text("回答正文"),)),
                MediaBlock(
                    MediaAsset(
                        id="answer-image",
                        kind=MediaKind.IMAGE,
                        renditions=(MediaRendition("https://pic.example/answer.png"),),
                    )
                ),
            ),
        )
        archive = QuestionArchive(
            question=question,
            answers=(answer,),
            archived_at=NOW,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "zhihu.db"
            database = ArchiveDatabase(database_path)
            database.save(archive)
            database.save(archive)

            with closing(sqlite3.connect(database_path)) as connection:
                content_types = connection.execute(
                    "SELECT type FROM contents ORDER BY type"
                ).fetchall()
                relation = connection.execute(
                    """
                    SELECT subject_key, predicate, object_key FROM relations
                    WHERE predicate = 'answers'
                    """
                ).fetchall()
                media = connection.execute(
                    """
                    SELECT content_key, asset_id FROM media
                    ORDER BY content_key, asset_id
                    """
                ).fetchall()

        self.assertEqual([("answer",), ("question",)], content_types)
        self.assertEqual(
            [
                (
                    "answer:2835848212",
                    "answers",
                    "question:28696373",
                )
            ],
            relation,
        )
        self.assertEqual(
            [
                ("answer:2835848212", "answer-image"),
                ("question:28696373", "question-image"),
            ],
            media,
        )

    def test_repeated_media_reference_is_persisted_once(self):
        repeated_asset = MediaAsset(
            id="repeated-image",
            kind=MediaKind.IMAGE,
            renditions=(
                MediaRendition(
                    "https://pic.example/repeated.png",
                    width=1200,
                    height=800,
                ),
            ),
        )
        article = Article(
            id="11617075708",
            title="重复图片",
            source_url="https://zhuanlan.zhihu.com/p/11617075708",
            author=Author(id="writer", name="作者"),
            published_at=NOW,
            blocks=(
                MediaBlock(repeated_asset),
                Paragraph((Text("中间正文"),)),
                MediaBlock(repeated_asset),
            ),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "zhihu.db"
            ArchiveDatabase(database_path).save(article)

            with closing(sqlite3.connect(database_path)) as connection:
                rows = connection.execute(
                    """
                    SELECT asset_id, source_url, ordinal
                    FROM media
                    WHERE content_key = 'article:11617075708'
                    """
                ).fetchall()

        self.assertEqual(
            [("repeated-image", "https://pic.example/repeated.png", 0)],
            rows,
        )

    def test_article_media_rows_include_body_comments_replies_and_cover_ownership(self):
        def asset(asset_id: str) -> MediaAsset:
            return MediaAsset(
                id=asset_id,
                kind=MediaKind.IMAGE,
                renditions=(MediaRendition(f"https://pic.example/{asset_id}.png"),),
            )

        article = Article(
            id="complete-media",
            title="完整媒体",
            source_url="https://zhuanlan.zhihu.com/p/complete-media",
            author=Author(id="writer", name="作者"),
            published_at=NOW,
            blocks=(MediaBlock(asset("body-image")),),
            cover_url="https://pic.example/cover.jpg",
            comments=CommentThread(
                comments=(
                    Comment(
                        id="root-comment",
                        author=None,
                        blocks=(MediaBlock(asset("comment-image")),),
                        created_at=NOW,
                        like_count=0,
                        replies=(
                            Comment(
                                id="reply-comment",
                                author=None,
                                blocks=(MediaBlock(asset("reply-image")),),
                                created_at=NOW,
                                like_count=0,
                            ),
                        ),
                    ),
                ),
                order="api",
            ),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "zhihu.db"
            ArchiveDatabase(database_path).save(
                article,
                media_paths={
                    "https://pic.example/body-image.png": "entry/media/body.png",
                    "https://pic.example/comment-image.png": "entry/media/comment.png",
                    "https://pic.example/reply-image.png": "entry/media/reply.png",
                    "https://pic.example/cover.jpg": "entry/media/cover.jpg",
                },
            )

            with closing(sqlite3.connect(database_path)) as connection:
                media = connection.execute(
                    """
                    SELECT asset_id, archive_path FROM media
                    WHERE content_key = 'article:complete-media'
                    ORDER BY ordinal
                    """
                ).fetchall()
                ownership = connection.execute(
                    """
                    SELECT subject_key, predicate, object_key FROM relations
                    WHERE object_key LIKE 'media:%'
                    ORDER BY object_key
                    """
                ).fetchall()

        self.assertEqual(
            [
                ("body-image", "entry/media/body.png"),
                ("comment-image", "entry/media/comment.png"),
                ("reply-image", "entry/media/reply.png"),
                ("article-complete-media-cover", "entry/media/cover.jpg"),
            ],
            media,
        )
        self.assertEqual(
            [
                (
                    "article:complete-media",
                    "has_cover",
                    "media:article-complete-media-cover",
                ),
                (
                    "article:complete-media",
                    "contains",
                    "media:body-image",
                ),
                (
                    "comment:root-comment",
                    "contains",
                    "media:comment-image",
                ),
                (
                    "comment:reply-comment",
                    "contains",
                    "media:reply-image",
                ),
            ],
            ownership,
        )

    def test_rearchiving_content_removes_stale_media_comment_and_membership_relations(self):
        old_asset = MediaAsset(
            id="old-image",
            kind=MediaKind.IMAGE,
            renditions=(MediaRendition("https://pic.example/old.png"),),
        )
        old = Article(
            id="changing",
            title="会变化的文章",
            source_url="https://zhuanlan.zhihu.com/p/changing",
            author=Author(id="writer", name="作者"),
            published_at=NOW,
            blocks=(MediaBlock(old_asset),),
            columns=(
                ColumnRef(
                    token="old-column",
                    title="旧专栏",
                    url="https://www.zhihu.com/column/old-column",
                ),
            ),
            comments=CommentThread(
                comments=(
                    Comment(
                        id="old-root",
                        author=None,
                        blocks=(Paragraph((Text("旧评论"),)),),
                        created_at=NOW,
                        like_count=0,
                        replies=(
                            Comment(
                                id="old-reply",
                                author=None,
                                blocks=(Paragraph((Text("旧回复"),)),),
                                created_at=NOW,
                                like_count=0,
                            ),
                        ),
                    ),
                ),
                order="api",
            ),
        )
        refreshed = Article(
            id=old.id,
            title=old.title,
            source_url=old.source_url,
            author=old.author,
            published_at=NOW,
            blocks=(Paragraph((Text("新正文，不再含媒体"),)),),
            columns=(),
            comments=CommentThread(
                comments=(),
                order="api",
                roots_complete=True,
            ),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "zhihu.db"
            database = ArchiveDatabase(database_path)
            database.save(old)
            database.save(refreshed)

            with closing(sqlite3.connect(database_path)) as connection:
                media_count = connection.execute(
                    "SELECT COUNT(*) FROM media WHERE content_key = 'article:changing'"
                ).fetchone()
                comment_count = connection.execute(
                    "SELECT COUNT(*) FROM comments WHERE content_key = 'article:changing'"
                ).fetchone()
                fetch_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM comment_fetches
                    WHERE content_key = 'article:changing'
                    """
                ).fetchone()
                relations = connection.execute(
                    """
                    SELECT subject_key, predicate, object_key FROM relations
                    WHERE subject_key IN (
                        'article:changing', 'comment:old-root', 'comment:old-reply'
                    )
                    ORDER BY subject_key, predicate, object_key
                    """
                ).fetchall()

        self.assertEqual((0,), media_count)
        self.assertEqual((0,), comment_count)
        self.assertEqual((1,), fetch_count)
        self.assertEqual(
            [
                (
                    "article:changing",
                    "authored_by",
                    "author:writer",
                )
            ],
            relations,
        )

    def test_rearchive_without_optional_fetches_preserves_comments_and_local_media_path(self):
        source_url = "https://pic.example/preserved.png"
        asset = MediaAsset(
            id="preserved-image",
            kind=MediaKind.IMAGE,
            renditions=(MediaRendition(source_url),),
        )
        initial = Article(
            id="preserved",
            title="保留已抓状态",
            source_url="https://zhuanlan.zhihu.com/p/preserved",
            author=Author(id="writer", name="作者"),
            published_at=NOW,
            blocks=(MediaBlock(asset),),
            comments=CommentThread(
                comments=(
                    Comment(
                        id="preserved-comment",
                        author=Author(id="reader", name="读者"),
                        blocks=(Paragraph((Text("不能被默认重抓删除"),)),),
                        created_at=NOW,
                        like_count=1,
                    ),
                ),
                order="api",
                roots_complete=True,
            ),
        )
        refreshed_without_optional_fetches = Article(
            id=initial.id,
            title=initial.title,
            source_url=initial.source_url,
            author=initial.author,
            published_at=initial.published_at,
            blocks=initial.blocks,
            comments=None,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "zhihu.db"
            database = ArchiveDatabase(database_path)
            database.save(
                initial,
                media_paths={source_url: "保留已抓状态/media/preserved.png"},
            )
            database.save(refreshed_without_optional_fetches)

            with closing(sqlite3.connect(database_path)) as connection:
                comments = connection.execute(
                    """
                    SELECT id, body_text
                    FROM comments
                    WHERE content_key = 'article:preserved'
                    """
                ).fetchall()
                fetch_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM comment_fetches
                    WHERE content_key = 'article:preserved'
                    """
                ).fetchone()
                archive_path = connection.execute(
                    """
                    SELECT archive_path
                    FROM media
                    WHERE content_key = 'article:preserved'
                      AND asset_id = 'preserved-image'
                    """
                ).fetchone()

        self.assertEqual([("preserved-comment", "不能被默认重抓删除")], comments)
        self.assertEqual((1,), fetch_count)
        self.assertEqual(("保留已抓状态/media/preserved.png",), archive_path)

    def test_video_media_rows_include_primary_description_and_cover_roles(self):
        video = Video(
            id="1666569497233207296",
            title="视频",
            source_url="https://www.zhihu.com/zvideo/1666569497233207296",
            author=Author(id="creator", name="创作者"),
            published_at=NOW,
            description=(
                MediaBlock(
                    MediaAsset(
                        id="description-image",
                        kind=MediaKind.IMAGE,
                        renditions=(MediaRendition("https://pic.example/description.jpg"),),
                    )
                ),
            ),
            asset=MediaAsset(
                id="zvideo-1666569497233207296",
                kind=MediaKind.VIDEO,
                renditions=(
                    MediaRendition(
                        "https://video.example/high.mp4",
                        width=1920,
                        height=1080,
                    ),
                ),
            ),
            cover_url="https://pic.example/video-cover.jpg",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "zhihu.db"
            ArchiveDatabase(database_path).save(video)

            with closing(sqlite3.connect(database_path)) as connection:
                media = connection.execute(
                    """
                    SELECT asset_id, kind FROM media
                    WHERE content_key = 'video:1666569497233207296'
                    ORDER BY ordinal
                    """
                ).fetchall()
                ownership = connection.execute(
                    """
                    SELECT predicate, object_key FROM relations
                    WHERE subject_key = 'video:1666569497233207296'
                      AND object_key LIKE 'media:%'
                    ORDER BY predicate, object_key
                    """
                ).fetchall()

        self.assertEqual(
            [
                ("zvideo-1666569497233207296", "video"),
                ("description-image", "image"),
                ("zvideo-1666569497233207296-cover", "image"),
            ],
            media,
        )
        self.assertEqual(
            [
                ("contains", "media:description-image"),
                ("contains", "media:zvideo-1666569497233207296"),
                ("has_cover", "media:zvideo-1666569497233207296-cover"),
            ],
            ownership,
        )


if __name__ == "__main__":
    unittest.main()
