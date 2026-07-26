import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.content import parse_rich_text
from zhihu_scraper.domain import Article, Author


class RichContentRenderingTests(unittest.TestCase):
    def test_article_preserves_formulas_code_and_images_in_both_outputs(self):
        article = Article(
            id="11617075708",
            title="包含公式的测试文章",
            source_url="https://zhuanlan.zhihu.com/p/11617075708",
            author=Author(id="author-2", name="公式作者"),
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            blocks=parse_rich_text(
                """
                    <script>window.shouldNotSurvive = true;</script>
                    <h2>推导</h2>
                    <p>行内公式：<span class="ztext-math" data-tex="E=mc^2"></span></p>
                    <p><span class="ztext-math" data-tex="\\[a^2+b^2=c^2\\]"></span></p>
                    <pre><code class="language-python">print("zhihu")</code></pre>
                    <figure>
                      <img
                        data-original="https://pic.example/formula-demo.gif"
                        src="https://pic.example/formula-demo_720w.gif"
                        alt="公式示意图"
                      >
                    </figure>
                    """
            ),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = LocalArchive(Path(temporary_directory)).archive(article)

            markdown = receipt.markdown_path.read_text(encoding="utf-8")
            html = receipt.html_path.read_text(encoding="utf-8")

            self.assertIn("$E=mc^2$", markdown)
            self.assertIn("$$\na^2+b^2=c^2\n$$", markdown)
            self.assertIn('```python\nprint("zhihu")\n```', markdown)
            self.assertIn(
                "![公式示意图](https://pic.example/formula-demo.gif)",
                markdown,
            )

            self.assertIn('data-tex="E=mc^2"', html)
            self.assertIn("a^2+b^2=c^2", html)
            self.assertIn('class="language-python"', html)
            self.assertIn("https://pic.example/formula-demo.gif", html)
            self.assertNotIn("shouldNotSurvive", html)
            self.assertTrue(
                (receipt.entry_directory / "assets" / "archive.css").is_file()
            )


if __name__ == "__main__":
    unittest.main()
