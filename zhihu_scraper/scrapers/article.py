"""Zhihu Article Scraper.
Scrapes full text, metadata, images, and raw HTML/Markdown of Zhihu Zhuanlan articles.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..client import ZhihuClient, safe_name, html_to_markdown

logger = logging.getLogger("zhihu_scraper.scrapers.article")


class ArticleScraper:
    """Scrapes Zhihu Zhuanlan articles."""

    def __init__(self, client: ZhihuClient):
        self.client = client

    @staticmethod
    def extract_article_id(url_or_id: str) -> str:
        """Extract article ID from string or URL."""
        cleaned = url_or_id.strip()
        m = re.search(r"zhuanlan\.zhihu\.com/p/(\d+)", cleaned)
        if m:
            return m.group(1)
        m2 = re.search(r"\b(\d{15,20})\b", cleaned)
        if m2:
            return m2.group(1)
        return cleaned.split("?")[0].strip("/")

    def get_article(self, article_id: str) -> Dict[str, Any]:
        """Fetch article JSON metadata and content via Web SSR or API."""
        clean_id = self.extract_article_id(article_id)

        # 1. Primary: Web Page SSR via js-initialData (Bypasses API 403 blocks)
        page_url = f"https://zhuanlan.zhihu.com/p/{clean_id}"
        html = self.client.get_html(page_url)
        if html:
            m = re.search(r'<script\s+id="js-initialData"\s+type="text/json">(.*?)</script>', html, re.DOTALL)
            if m:
                try:
                    init_data = json.loads(m.group(1))
                    articles = init_data.get("initialState", {}).get("entities", {}).get("articles", {})
                    if clean_id in articles:
                        art = articles[clean_id]
                        author = art.get("author", {})
                        return {
                            "id": str(art.get("id", clean_id)),
                            "title": art.get("title", f"文章_{clean_id}"),
                            "content": art.get("content", ""),
                            "author": {
                                "name": author.get("name", ""),
                                "url_token": author.get("urlToken") or author.get("url_token", ""),
                                "avatar_url": author.get("avatarUrl", "")
                            },
                            "created": art.get("created", 0),
                            "updated": art.get("updated", 0),
                            "voteup_count": art.get("voteupCount", art.get("voteup_count", 0)),
                            "comment_count": art.get("commentCount", art.get("comment_count", 0))
                        }
                except Exception as e:
                    logger.warning("Failed to parse js-initialData for article %s: %s", clean_id, e)

        # 2. Fallback: Official REST API
        api_url = f"https://api.zhihu.com/articles/{clean_id}"
        data = self.client.get_json(api_url)
        if not data or "id" not in data:
            v4_url = f"https://www.zhihu.com/api/v4/articles/{clean_id}"
            data = self.client.get_json(v4_url)
        return data or {}

    def scrape(self, article_id: str, save_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Download article metadata, format markdown, and optionally save to disk."""
        data = self.get_article(article_id)
        if not data or "id" not in data:
            logger.warning("Article %s not found or deleted.", article_id)
            return {}

        title = data.get("title", f"文章_{article_id}")
        content_html = data.get("content", "")
        content_md = html_to_markdown(content_html)
        author = data.get("author", {})
        created_time = data.get("created", 0)
        updated_time = data.get("updated", 0)

        created_str = datetime.fromtimestamp(created_time, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_time else ""
        updated_str = datetime.fromtimestamp(updated_time, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if updated_time else ""

        result = {
            "type": "article",
            "id": str(data.get("id")),
            "title": title,
            "url": f"https://zhuanlan.zhihu.com/p/{data.get('id')}",
            "author_name": author.get("name", "未知"),
            "author_token": author.get("url_token", ""),
            "author_url": f"https://www.zhihu.com/people/{author.get('url_token', '')}",
            "created_at": created_str,
            "updated_at": updated_str,
            "voteup_count": data.get("voteup_count", 0),
            "comment_count": data.get("comment_count", 0),
            "html": content_html,
            "markdown": content_md
        }

        if save_dir:
            save_dir.mkdir(parents=True, exist_ok=True)
            fname = f"{safe_name(title)}_{result['id']}.md"
            file_path = save_dir / fname
            
            md_doc = f"# {title}\n\n"
            md_doc += f"> **作者**: [{result['author_name']}]({result['author_url']})\n"
            md_doc += f"> **原始链接**: {result['url']}\n"
            md_doc += f"> **发布时间**: {result['created_at']} | **点赞数**: {result['voteup_count']} | **评论数**: {result['comment_count']}\n\n"
            md_doc += "---\n\n"
            md_doc += content_md + "\n"

            file_path.write_text(md_doc, encoding="utf-8")
            result["file_path"] = str(file_path)

        return result
