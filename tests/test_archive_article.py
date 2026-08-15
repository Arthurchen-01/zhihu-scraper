import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.domain import Article, Author, Paragraph, Text


class StandaloneArticleArchiveTests(unittest.TestCase):
    def test_archiving_an_article_creates_the_agreed_standalone_bundle(self):
        article = Article(
            id="357892158",
            title="一文归纳AI数据增强之法",
            source_url="https://zhuanlan.zhihu.com/p/357892158",
            author=Author(id="author-1", name="泳鱼"),
            published_at=datetime(2021, 3, 17, tzinfo=UTC),
            blocks=(Paragraph(inlines=(Text("数据、算法、算力是人工智能发展的三要素。"),)),),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            library_root = Path(temporary_directory)

            receipt = LocalArchive(library_root, html=True).archive(article)

            entry_directory = library_root / article.title
            markdown_path = entry_directory / f"{article.title}.md"
            html_path = entry_directory / f"{article.title}.html"

            self.assertEqual(entry_directory, receipt.entry_directory)
            self.assertEqual(markdown_path, receipt.markdown_path)
            self.assertEqual(html_path, receipt.html_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            html = html_path.read_text(encoding="utf-8")
            self.assertIn(article.title, markdown)
            self.assertIn(article.source_url, markdown)
            self.assertIn("数据、算法、算力", markdown)
            self.assertIn(article.title, html)
            self.assertIn(article.source_url, html)
            self.assertIn("数据、算法、算力", html)
            self.assertFalse((library_root / "zhihu.db").exists())
            self.assertFalse((entry_directory / "内容").exists())

    def test_default_archive_writes_markdown_without_html_assets(self):
        article = Article(
            id="default-markdown",
            title="默认 Markdown",
            source_url="https://zhuanlan.zhihu.com/p/default-markdown",
            author=Author(id="author-1", name="泳鱼"),
            published_at=None,
            blocks=(Paragraph(inlines=(Text("正文"),)),),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = LocalArchive(Path(temporary_directory)).archive(article)

            self.assertIsNotNone(receipt.markdown_path)
            self.assertIsNone(receipt.html_path)
            self.assertFalse((receipt.entry_directory / "assets").exists())


if __name__ == "__main__":
    unittest.main()
