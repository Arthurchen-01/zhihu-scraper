"""EPUB E-Book Builder for Zhihu Scraped Assets.
Compiles scraped Markdown/HTML articles, answers, and pins into standard, beautifully styled EPUB books.
Compatible with Apple Books, WeChat Read, Kindle, Calibre, and mobile e-readers.
"""

from __future__ import annotations

import logging
import re
import uuid
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

import ebooklib
from ebooklib import epub

logger = logging.getLogger("zhihu_scraper.epub_builder")

BOOK_CSS = """
@namespace epub "http://www.idpf.org/2007/ops";
body {
    font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    line-height: 1.75;
    color: #2d3748;
    background-color: #fafafa;
    padding: 1em 1.2em;
    margin: 0;
}
h1.book-title {
    text-align: center;
    font-size: 1.8em;
    color: #1a202c;
    margin-top: 2em;
    margin-bottom: 0.5em;
}
.book-meta {
    text-align: center;
    color: #718096;
    font-size: 0.9em;
    margin-bottom: 2em;
}
h1.chapter-title {
    font-size: 1.4em;
    color: #0369a1;
    border-bottom: 2px solid #0284c7;
    padding-bottom: 0.3em;
    margin-top: 1em;
    margin-bottom: 0.6em;
}
.article-meta {
    background: #edf2f7;
    border-left: 4px solid #0284c7;
    padding: 8px 12px;
    font-size: 0.85em;
    color: #4a5568;
    margin-bottom: 1.5em;
    border-radius: 4px;
}
.article-meta p {
    margin: 4px 0;
}
p {
    margin-top: 0.8em;
    margin-bottom: 0.8em;
    text-align: justify;
    word-break: break-word;
}
blockquote {
    border-left: 4px solid #cbd5e1;
    background: #f1f5f9;
    padding: 8px 16px;
    margin: 1em 0;
    color: #64748b;
    font-style: italic;
}
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
    border-radius: 6px;
}
pre, code {
    font-family: "SFMono-Regular", Consolas, Menlo, monospace;
    background-color: #e2e8f0;
    border-radius: 4px;
}
code {
    padding: 2px 5px;
    font-size: 0.9em;
}
pre {
    padding: 12px;
    overflow-x: auto;
    font-size: 0.85em;
}
a {
    color: #0284c7;
    text-decoration: none;
}
hr {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 2em 0;
}
"""


def markdown_to_html_simple(md_text: str) -> str:
    """Convert clean markdown to XHTML compatible paragraphs, links, and headings."""
    lines = md_text.splitlines()
    html_lines = []
    in_code = False
    in_quote = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                html_lines.append("</pre>")
                in_code = False
            else:
                html_lines.append("<pre><code>")
                in_code = True
            continue

        if in_code:
            html_lines.append(escape(line))
            continue

        if not stripped:
            if in_quote:
                html_lines.append("</blockquote>")
                in_quote = False
            continue

        if stripped.startswith(">"):
            if not in_quote:
                html_lines.append("<blockquote>")
                in_quote = True
            q_text = escape(stripped.lstrip("> ").strip())
            html_lines.append(f"<p>{q_text}</p>")
            continue
        elif in_quote:
            html_lines.append("</blockquote>")
            in_quote = False

        if stripped.startswith("### "):
            html_lines.append(f"<h3>{escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            html_lines.append(f"<h1>{escape(stripped[2:])}</h1>")
        else:
            txt = escape(stripped)
            txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\g<1></strong>", txt)
            txt = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", r'<a href="\g<2>">\g<1></a>', txt)
            txt = re.sub(r"!\[(.*?)\]\((https?://[^\s)]+)\)", r'<img alt="\g<1>" src="\g<2>" />', txt)
            html_lines.append(f"<p>{txt}</p>")

    if in_code:
        html_lines.append("</code></pre>")
    if in_quote:
        html_lines.append("</blockquote>")

    return "\n".join(html_lines)


class ZhihuEpubBuilder:
    """Builds standard EPUB files from Zhihu scraped content."""

    def __init__(self, title: str = "知乎精选存证文集", author: str = "知乎创作者"):
        self.title = title
        self.author = author
        self.book = epub.EpubBook()
        self.book.set_identifier(str(uuid.uuid4()))
        self.book.set_title(self.title)
        self.book.set_language("zh-CN")
        self.book.add_author(self.author)

        self.css_item = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=BOOK_CSS.encode("utf-8")
        )
        self.book.add_item(self.css_item)

        self.chapters: List[epub.EpubHtml] = []
        self.toc_links: List[epub.Link] = []

    def add_cover_page(self, subtitle: str = "", extra_info: Optional[Dict[str, str]] = None) -> None:
        meta_html = ""
        if extra_info:
            meta_items = "".join(f"<p><strong>{escape(k)}:</strong> {escape(str(v))}</p>" for k, v in extra_info.items())
            meta_html = f"<div class='article-meta'>{meta_items}</div>"

        cover_content = f"""
        <div style="text-align: center; padding-top: 3em;">
            <h1 class="book-title">{escape(self.title)}</h1>
            <p class="book-meta">作者：{escape(self.author)} {f" | {escape(subtitle)}" if subtitle else ""}</p>
            <hr />
            {meta_html}
            <p style="color: #94a3b8; font-size: 0.85em; margin-top: 4em;">由 知乎创作者存证与电子书引擎 自动编排生成</p>
        </div>
        """
        cover = epub.EpubHtml(title="封面与简介", file_name="cover.xhtml", lang="zh-CN")
        cover.content = f"<html><head><title>封面</title><link rel='stylesheet' href='style/nav.css' type='text/css'/></head><body>{cover_content}</body></html>"
        cover.add_item(self.css_item)
        self.book.add_item(cover)
        self.chapters.append(cover)
        self.toc_links.append(epub.Link("cover.xhtml", "封面与简介", "cover"))

    def add_article_chapter(
        self,
        index: int,
        title: str,
        content_markdown: str,
        created_at: str = "",
        url: str = "",
        voteup_count: int = 0,
        comment_count: int = 0,
        item_type: str = "文章"
    ) -> None:
        file_name = f"chapter_{index:04d}.xhtml"
        clean_title = title.strip() or f"第{index}篇"

        meta_lines = []
        if created_at:
            meta_lines.append(f"<p>📅 <strong>发布时间：</strong>{escape(created_at)}</p>")
        if url:
            meta_lines.append(f"<p>🔗 <strong>知乎原链：</strong><a href='{escape(url)}'>{escape(url)}</a></p>")
        if voteup_count or comment_count:
            meta_lines.append(f"<p>📊 <strong>互动数据：</strong>👍 赞同 {voteup_count} | 💬 评论 {comment_count}</p>")
        if item_type:
            meta_lines.append(f"<p>🏷️ <strong>内容类型：</strong>{escape(item_type)}</p>")

        meta_box = f"<div class='article-meta'>{''.join(meta_lines)}</div>" if meta_lines else ""
        body_html = markdown_to_html_simple(content_markdown)

        chapter_html = f"""<html>
<head>
    <title>{escape(clean_title)}</title>
    <link rel="stylesheet" href="style/nav.css" type="text/css"/>
</head>
<body>
    <h1 class="chapter-title">[{escape(item_type)}] {escape(clean_title)}</h1>
    {meta_box}
    <div class="article-body">
        {body_html}
    </div>
</body>
</html>"""

        chapter = epub.EpubHtml(title=clean_title, file_name=file_name, lang="zh-CN")
        chapter.content = chapter_html
        chapter.add_item(self.css_item)

        self.book.add_item(chapter)
        self.chapters.append(chapter)
        self.toc_links.append(epub.Link(file_name, clean_title, f"chap_{index}"))

    def build(self, output_path: str | Path) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.book.toc = tuple(self.toc_links)
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())
        self.book.spine = ["nav"] + self.chapters
        epub.write_epub(str(out), self.book, {})
        logger.info("Successfully wrote EPUB (%d chapters) to %s", len(self.chapters), out)
        return out
