import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from zhihu_scraper.archive import LocalArchive
from zhihu_scraper.content import parse_rich_text
from zhihu_scraper.domain import Article, Author, CodeBlock, CodeSpan, Paragraph, Text
from zhihu_scraper.render import HtmlRenderer, MarkdownRenderer


class RichContentRenderingTests(unittest.TestCase):
    def test_article_preserves_formulas_code_and_images_in_both_outputs(self):
        article = Article(
            id="11617075708",
            title="包含公式的测试文章",
            source_url="https://zhuanlan.zhihu.com/p/11617075708",
            author=Author(id="author-2", name="公式作者"),
            published_at=datetime(2025, 1, 1, tzinfo=UTC),
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
            receipt = LocalArchive(
                Path(temporary_directory),
                html=True,
                media_download=False,
            ).archive(article)

            markdown = receipt.markdown_path.read_text(encoding="utf-8")
            html = receipt.html_path.read_text(encoding="utf-8")

            self.assertIn("$E=mc^2$", markdown)
            self.assertIn("$$\na^2+b^2=c^2\n$$", markdown)
            self.assertIn('```python\nprint("zhihu")\n```', markdown)
            self.assertIn(
                "[远程媒体未下载：公式示意图](https://pic.example/formula-demo.gif)",
                markdown,
            )

            self.assertIn('data-tex="E=mc^2"', html)
            self.assertIn('<math xmlns="http://www.w3.org/1998/Math/MathML"', html)
            self.assertIn("<msup>", html)
            self.assertIn('display="block"', html)
            self.assertIn('data-tex="a^2+b^2=c^2"', html)
            self.assertIn('class="language-python"', html)
            self.assertIn("https://pic.example/formula-demo.gif", html)
            self.assertNotIn('<img src="https://pic.example', html)
            self.assertNotIn("shouldNotSurvive", html)
            self.assertTrue((receipt.entry_directory / "assets" / "archive.css").is_file())

    def test_malformed_formula_falls_back_to_escaped_tex(self):
        article = Article(
            id="malformed-formula",
            title="损坏公式",
            source_url="https://zhuanlan.zhihu.com/p/malformed-formula",
            author=Author(id="author-2", name="公式作者"),
            published_at=None,
            blocks=parse_rich_text(
                '<p><span class="ztext-math" data-tex="\\begin{matrix}&lt;script&gt;"></span></p>'
            ),
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            receipt = LocalArchive(Path(temporary_directory), html=True).archive(article)
            html = receipt.html_path.read_text(encoding="utf-8")

        self.assertIn('data-tex="\\begin{matrix}&lt;script&gt;"', html)
        self.assertIn(">\\begin{matrix}&lt;script&gt;</", html)
        self.assertNotIn("<script>", html)

    def test_table_cells_preserve_links_code_and_mathml(self):
        article = Article(
            id="rich-table",
            title="富文本表格",
            source_url="https://zhuanlan.zhihu.com/p/rich-table",
            author=Author(id=None, name="作者"),
            published_at=None,
            blocks=parse_rich_text(
                """
                <table>
                  <thead><tr><th>类型</th><th>内容</th></tr></thead>
                  <tbody>
                    <tr>
                      <td>公式</td>
                      <td><span class="ztext-math" data-tex="\\frac{a}{b}"></span></td>
                    </tr>
                    <tr>
                      <td><code>x</code></td>
                      <td><a href="https://example.com/docs">文档</a></td>
                    </tr>
                  </tbody>
                </table>
                """
            ),
        )

        markdown = MarkdownRenderer().render(article)
        rendered_html = HtmlRenderer().render(article)

        self.assertIn(r"$\frac{a}{b}$", markdown)
        self.assertIn("[文档](https://example.com/docs)", markdown)
        self.assertIn("<mfrac>", rendered_html)
        self.assertIn('<a href="https://example.com/docs">文档</a>', rendered_html)
        self.assertIn("<code>x</code>", rendered_html)

    def test_markdown_escapes_plain_syntax_and_uses_content_aware_code_fences(self):
        article = Article(
            id="markdown-fences",
            title="Markdown 安全",
            source_url="https://zhuanlan.zhihu.com/p/markdown-fences",
            author=Author(id=None, name="作者"),
            published_at=None,
            blocks=(
                Paragraph(
                    (
                        Text("*不是强调* [不是链接] <unsafe> "),
                        CodeSpan("``嵌套``"),
                        Text("\n# 普通行\n> 普通行\n- 普通行\n1. 普通行"),
                    )
                ),
                CodeBlock("print('```')", language="python"),
            ),
        )

        markdown = MarkdownRenderer().render(article)

        self.assertIn(r"\*不是强调\* \[不是链接\] \<unsafe\>", markdown)
        self.assertIn(r"\# 普通行", markdown)
        self.assertIn(r"\> 普通行", markdown)
        self.assertIn(r"\- 普通行", markdown)
        self.assertIn(r"1\. 普通行", markdown)
        self.assertIn("``` ``嵌套`` ```", markdown)
        self.assertIn("````python\nprint('```')\n````", markdown)


if __name__ == "__main__":
    unittest.main()
