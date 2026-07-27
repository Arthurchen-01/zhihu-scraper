import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.domain import (
    Article,
    Author,
    Column,
    ColumnArchive,
    ColumnRef,
    MediaAsset,
    MediaBlock,
    MediaKind,
    MediaRendition,
    Paragraph,
    Text,
)
from zhihu_scraper.media import MediaDownloadReceipt

NOW = datetime(2026, 7, 26, tzinfo=UTC)
AUTHOR = Author(id="author", name="作者")


class FakeDownloader:
    def __init__(self):
        self.calls = []

    def __call__(self, source_url, destination):
        self.calls.append((source_url, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"media")
        return MediaDownloadReceipt(
            source_url=source_url,
            destination=destination,
            resumed_from=0,
            bytes_total=5,
        )


class LocalArchiveLayoutTests(unittest.TestCase):
    def test_only_whole_columns_create_the_content_directory(self):
        column_ref = ColumnRef(
            token="machinelearningpku",
            title="机器学习",
            url="https://www.zhihu.com/column/machinelearningpku",
        )
        first = Article(
            id="1",
            title="同名:文章",
            source_url="https://zhuanlan.zhihu.com/p/1",
            author=AUTHOR,
            published_at=datetime(2025, 1, 1, tzinfo=UTC),
            blocks=(Paragraph((Text("第一篇正文"),)),),
            columns=(column_ref,),
        )
        second = Article(
            id="2",
            title="同名/文章",
            source_url="https://zhuanlan.zhihu.com/p/2",
            author=AUTHOR,
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            blocks=(Paragraph((Text("第二篇正文"),)),),
            columns=(column_ref,),
        )
        archive = ColumnArchive(
            column=Column(
                token=column_ref.token,
                title=column_ref.title,
                source_url=column_ref.url,
                description="专栏说明",
                author=AUTHOR,
                item_count=81,
            ),
            articles=(first, second),
            archived_at=NOW,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            receipt = LocalArchive(root, media_download=False).archive(archive)

            self.assertEqual(root / "机器学习", receipt.entry_directory)
            self.assertEqual(root / "机器学习" / "机器学习.md", receipt.markdown_path)
            self.assertEqual(root / "机器学习" / "机器学习.html", receipt.html_path)
            self.assertEqual(root / "zhihu.db", receipt.database_path)
            self.assertEqual(2, len(receipt.child_markdown_paths))
            self.assertEqual(2, len(receipt.child_html_paths))
            self.assertTrue(
                all(path.parent.name == "内容" for path in receipt.child_markdown_paths)
            )
            self.assertEqual(
                len({path.name.casefold() for path in receipt.child_markdown_paths}),
                2,
            )
            self.assertTrue((root / "机器学习" / "assets" / "archive.css").is_file())
            self.assertFalse((root / "机器学习" / "media").exists())

            catalog = receipt.markdown_path.read_text(encoding="utf-8")
            first_page = receipt.child_markdown_paths[0].read_text(encoding="utf-8")
            self.assertIn("本栏目共 81 篇", catalog)
            self.assertIn("内容/同名_文章.md", catalog)
            self.assertIn("本次归档自", first_page)
            self.assertIn("查看完整目录", first_page)
            self.assertIn("下一篇", first_page)
            self.assertNotIn("第一篇正文", catalog)

    def test_standalone_article_has_no_content_directory_and_uses_local_media(self):
        source_url = "https://pic.example/original.png"
        article = Article(
            id="3",
            title="单篇文章",
            source_url="https://zhuanlan.zhihu.com/p/3",
            author=AUTHOR,
            published_at=NOW,
            blocks=(
                MediaBlock(
                    MediaAsset(
                        id="image",
                        kind=MediaKind.IMAGE,
                        renditions=(MediaRendition(source_url),),
                        alt_text="图片",
                    )
                ),
            ),
        )
        downloader = FakeDownloader()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            receipt = LocalArchive(root, downloader=downloader).archive(article)

            self.assertFalse((receipt.entry_directory / "内容").exists())
            self.assertEqual(1, len(downloader.calls))
            self.assertTrue((receipt.entry_directory / "media").is_dir())
            markdown = receipt.markdown_path.read_text(encoding="utf-8")
            self.assertIn("](media/", markdown)
            self.assertNotIn(source_url, markdown.split("##", 1)[-1])

    def test_disabled_outputs_do_not_create_empty_media_or_assets_directories(self):
        article = Article(
            id="4",
            title="仅数据库",
            source_url="https://zhuanlan.zhihu.com/p/4",
            author=AUTHOR,
            published_at=None,
            blocks=(Paragraph((Text("正文"),)),),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = LocalArchive(
                Path(temporary_directory),
                markdown=False,
                html=False,
                sqlite=True,
                media_download=False,
            ).archive(article)

            self.assertIsNone(receipt.markdown_path)
            self.assertIsNone(receipt.html_path)
            self.assertTrue(receipt.database_path.is_file())
            self.assertFalse((receipt.entry_directory / "assets").exists())
            self.assertFalse((receipt.entry_directory / "media").exists())
            self.assertFalse((receipt.entry_directory / "内容").exists())


if __name__ == "__main__":
    unittest.main()
