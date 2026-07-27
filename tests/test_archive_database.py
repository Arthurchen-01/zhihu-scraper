import sqlite3
import tempfile
import unittest
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

            with sqlite3.connect(database_path) as connection:
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
            detail=(Paragraph((Text("问题详情"),)),),
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
            blocks=(Paragraph((Text("回答正文"),)),),
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

            with sqlite3.connect(database_path) as connection:
                content_types = connection.execute(
                    "SELECT type FROM contents ORDER BY type"
                ).fetchall()
                relation = connection.execute(
                    """
                    SELECT subject_key, predicate, object_key FROM relations
                    WHERE predicate = 'answers'
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


if __name__ == "__main__":
    unittest.main()
