"""PDF Document Builder for Zhihu Scraped Assets.
Compiles scraped Markdown/HTML articles, answers, and pins into high-fidelity A4 PDF documents.
Uses Playwright Chromium headless for pixel-perfect typography, cover pages, and table of contents.
"""

from __future__ import annotations

import logging
import re
import time
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import markdown
except ImportError:
    markdown = None

from playwright.sync_api import sync_playwright

logger = logging.getLogger("zhihu_scraper.pdf_builder")

PDF_PRINT_CSS = """
@page {
    size: A4 portrait;
    margin: 20mm 18mm 22mm 18mm;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 9pt;
        color: #64748b;
    }
}

@page :first {
    margin: 0;
    @bottom-center { content: ""; }
}

* {
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "WenQuanYi Micro Hei", sans-serif;
    line-height: 1.75;
    color: #1e293b;
    background: #ffffff;
    margin: 0;
    padding: 0;
    font-size: 11pt;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

/* Cover Page */
.cover-page {
    width: 100vw;
    height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 60px 40px;
    page-break-after: always;
    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
    border-bottom: 6px solid #0ea5e9;
}

.cover-badge {
    display: inline-block;
    padding: 6px 16px;
    background: #0ea5e9;
    color: #ffffff;
    font-size: 11pt;
    font-weight: 600;
    border-radius: 9999px;
    letter-spacing: 1px;
    margin-bottom: 28px;
}

.cover-title {
    font-size: 28pt;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.3;
    margin: 0 0 16px 0;
    max-width: 85%;
}

.cover-subtitle {
    font-size: 14pt;
    color: #475569;
    margin: 0 0 40px 0;
    font-weight: 400;
}

.cover-meta-box {
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 20px 32px;
    margin-top: 20px;
    text-align: left;
    min-width: 360px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.cover-meta-row {
    font-size: 10pt;
    color: #334155;
    margin: 6px 0;
    display: flex;
    justify-content: space-between;
}

.cover-meta-label {
    color: #64748b;
    font-weight: 500;
}

/* Table of Contents */
.toc-page {
    padding-top: 20px;
    page-break-after: always;
}

.toc-title {
    font-size: 18pt;
    font-weight: 700;
    color: #0f172a;
    border-bottom: 2px solid #0ea5e9;
    padding-bottom: 8px;
    margin-bottom: 20px;
}

.toc-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.toc-item {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 10px 0;
    border-bottom: 1px dashed #e2e8f0;
    font-size: 10.5pt;
}

.toc-item-title {
    color: #0284c7;
    text-decoration: none;
    font-weight: 500;
    max-width: 80%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.toc-item-meta {
    color: #64748b;
    font-size: 9pt;
}

/* Chapter */
.chapter {
    page-break-after: always;
    padding-top: 15px;
}

.chapter:last-child {
    page-break-after: auto;
}

.chapter-header {
    border-bottom: 2px solid #0ea5e9;
    padding-bottom: 12px;
    margin-bottom: 16px;
    page-break-inside: avoid;
}

.chapter-title {
    font-size: 18pt;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.35;
    margin: 0 0 10px 0;
}

.chapter-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 9pt;
    color: #64748b;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 6px 12px;
}

.chapter-meta-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.chapter-body {
    font-size: 11pt;
    line-height: 1.8;
    color: #334155;
    word-break: break-word;
}

.chapter-body p {
    margin: 1em 0;
    text-align: justify;
}

.chapter-body blockquote {
    margin: 1.2em 0;
    padding: 10px 18px;
    background: #f1f5f9;
    border-left: 4px solid #0ea5e9;
    border-radius: 0 6px 6px 0;
    color: #475569;
    font-style: italic;
    page-break-inside: avoid;
}

.chapter-body img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1.5em auto;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    page-break-inside: avoid;
}

.chapter-body pre {
    background: #0f172a;
    color: #f8fafc;
    padding: 14px 16px;
    border-radius: 8px;
    overflow-x: auto;
    font-family: "SFMono-Regular", Consolas, Menlo, monospace;
    font-size: 9.5pt;
    line-height: 1.5;
    page-break-inside: avoid;
}

.chapter-body code {
    font-family: "SFMono-Regular", Consolas, Menlo, monospace;
    background: #f1f5f9;
    color: #0f172a;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 9.5pt;
}

.chapter-body pre code {
    background: transparent;
    color: inherit;
    padding: 0;
}

.chapter-body a {
    color: #0284c7;
    text-decoration: underline;
}

.chapter-body hr {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 2em 0;
}
"""


class ZhihuPdfBuilder:
    """Builds clean, professional PDF documents for scraped Zhihu articles and items."""

    def __init__(self, title: str, author: str = "知乎创作者"):
        self.title = title
        self.author = author
        self.chapters: List[Dict[str, Any]] = []
        self.cover_info: Optional[Dict[str, Any]] = None

    def add_cover_page(self, subtitle: str = "", extra_info: Optional[Dict[str, str]] = None):
        """Configure cover page metadata."""
        self.cover_info = {
            "title": self.title,
            "subtitle": subtitle,
            "author": self.author,
            "extra_info": extra_info or {},
        }

    def add_chapter(
        self,
        title: str,
        content: str,
        meta: Optional[Dict[str, Any]] = None,
        is_markdown: bool = True,
    ):
        """Append an article or item chapter."""
        self.chapters.append({
            "title": title or "未命名章节",
            "content": content or "",
            "meta": meta or {},
            "is_markdown": is_markdown,
        })

    def _convert_content_to_html(self, content: str, is_markdown: bool) -> str:
        """Convert Markdown or raw text into safe HTML."""
        if not content:
            return "<p><em>（无正文内容）</em></p>"

        if is_markdown and markdown:
            try:
                return markdown.markdown(
                    content,
                    extensions=["extra", "codehilite", "tables", "toc"],
                )
            except Exception as e:
                logger.warning("Markdown parsing fallback: %s", e)

        # Fallback simple converter
        paragraphs = re.split(r"\n\s*\n", content.strip())
        html_parts = []
        for p in paragraphs:
            p_str = p.strip()
            if not p_str:
                continue
            if p_str.startswith("# "):
                html_parts.append(f"<h2>{escape(p_str[2:].strip())}</h2>")
            elif p_str.startswith("## "):
                html_parts.append(f"<h3>{escape(p_str[3:].strip())}</h3>")
            elif p_str.startswith("> "):
                html_parts.append(f"<blockquote>{escape(p_str[2:].strip())}</blockquote>")
            else:
                html_parts.append(f"<p>{escape(p_str).replace(chr(10), '<br>')}</p>")
        return "\n".join(html_parts)

    def build_html(self) -> str:
        """Render complete HTML document suitable for Playwright PDF printing."""
        parts = [
            "<!DOCTYPE html>",
            "<html lang='zh-CN'>",
            "<head>",
            "<meta charset='utf-8'>",
            f"<title>{escape(self.title)}</title>",
            f"<style>{PDF_PRINT_CSS}</style>",
            "</head>",
            "<body>",
        ]

        # 1. Cover Page
        if self.cover_info:
            parts.append("<div class='cover-page'>")
            parts.append("<div class='cover-badge'>Z-VAULT 精选存证</div>")
            parts.append(f"<h1 class='cover-title'>{escape(self.cover_info['title'])}</h1>")
            if self.cover_info["subtitle"]:
                parts.append(f"<div class='cover-subtitle'>{escape(self.cover_info['subtitle'])}</div>")

            parts.append("<div class='cover-meta-box'>")
            parts.append(
                f"<div class='cover-meta-row'><span class='cover-meta-label'>作者 / 主体</span><span>{escape(self.cover_info['author'])}</span></div>"
            )
            parts.append(
                f"<div class='cover-meta-row'><span class='cover-meta-label'>存证收录</span><span>共 {len(self.chapters)} 篇</span></div>"
            )
            parts.append(
                f"<div class='cover-meta-row'><span class='cover-meta-label'>生成时间</span><span>{time.strftime('%Y-%m-%d %H:%M:%S')}</span></div>"
            )

            for k, v in self.cover_info["extra_info"].items():
                parts.append(
                    f"<div class='cover-meta-row'><span class='cover-meta-label'>{escape(str(k))}</span><span>{escape(str(v))}</span></div>"
                )

            parts.append("</div>")  # end cover-meta-box
            parts.append("</div>")  # end cover-page

        # 2. Table of Contents (if more than 1 chapter)
        if len(self.chapters) > 1:
            parts.append("<div class='toc-page'>")
            parts.append("<h2 class='toc-title'>📑 目录导航 (Table of Contents)</h2>")
            parts.append("<ul class='toc-list'>")
            for idx, ch in enumerate(self.chapters, 1):
                c_title = escape(ch["title"])
                date_str = escape(str(ch["meta"].get("created_at") or ch["meta"].get("created_date") or ""))
                parts.append("<li class='toc-item'>")
                parts.append(f"<span class='toc-item-title'><strong>{idx}.</strong> {c_title}</span>")
                if date_str:
                    parts.append(f"<span class='toc-item-meta'>{date_str}</span>")
                parts.append("</li>")
            parts.append("</ul>")
            parts.append("</div>")  # end toc-page

        # 3. Chapters
        for idx, ch in enumerate(self.chapters, 1):
            ch_title = ch["title"]
            ch_html = self._convert_content_to_html(ch["content"], ch["is_markdown"])
            meta = ch["meta"]

            parts.append("<div class='chapter'>")
            parts.append("<div class='chapter-header'>")
            parts.append(f"<h2 class='chapter-title'>{idx}. {escape(ch_title)}</h2>")

            meta_items = []
            if meta.get("author_name"):
                meta_items.append(f"<span class='chapter-meta-item'>👤 作者: {escape(str(meta['author_name']))}</span>")
            if meta.get("created_at"):
                meta_items.append(f"<span class='chapter-meta-item'>📅 发布时间: {escape(str(meta['created_at']))}</span>")
            if meta.get("voteup_count") is not None:
                meta_items.append(f"<span class='chapter-meta-item'>👍 赞同: {meta['voteup_count']}</span>")
            if meta.get("comment_count") is not None:
                meta_items.append(f"<span class='chapter-meta-item'>💬 评论: {meta['comment_count']}</span>")
            if meta.get("url"):
                meta_items.append(f"<span class='chapter-meta-item'>🔗 <a href='{escape(meta['url'])}' target='_blank'>查看知乎原文</a></span>")

            if meta_items:
                parts.append(f"<div class='chapter-meta'>{''.join(meta_items)}</div>")

            parts.append("</div>")  # end chapter-header
            parts.append(f"<div class='chapter-body'>{ch_html}</div>")
            parts.append("</div>")  # end chapter

        parts.append("</body>")
        parts.append("</html>")
        return "\n".join(parts)

    def save_pdf(self, output_path: str | Path) -> Path:
        """Render and save HTML to PDF using Playwright Chromium Headless."""
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        html_content = self.build_html()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")

            page.pdf(
                path=str(out_file),
                format="A4",
                print_background=True,
                margin={"top": "16mm", "bottom": "18mm", "left": "16mm", "right": "16mm"},
                display_header_footer=True,
                header_template='<div style="font-size:8pt;color:#94a3b8;width:100%;text-align:right;padding-right:16mm;font-family:sans-serif;"><span>Scraper 知乎精选存证</span></div>',
                footer_template='<div style="font-size:8pt;color:#94a3b8;width:100%;text-align:center;font-family:sans-serif;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
            )
            browser.close()

        logger.info("PDF file successfully created at: %s (%d bytes)", out_file, out_file.stat().st_size)
        return out_file
