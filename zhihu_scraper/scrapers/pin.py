"""Zhihu Pin (想法) Scraper.
Scrapes pin text, uploaded pictures, reaction counts, and author details.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..client import ZhihuClient, safe_name, html_to_markdown

logger = logging.getLogger("zhihu_scraper.scrapers.pin")


class PinScraper:
    """Scrapes Zhihu Pins (想法)."""

    def __init__(self, client: ZhihuClient):
        self.client = client

    @staticmethod
    def extract_pin_id(url_or_id: str) -> str:
        """Extract pin ID from string or URL."""
        cleaned = url_or_id.strip()
        m = re.search(r"zhihu\.com/pin/(\d+)", cleaned)
        if m:
            return m.group(1)
        m2 = re.search(r"\b(\d{15,20})\b", cleaned)
        if m2:
            return m2.group(1)
        return cleaned.split("?")[0].strip("/")

    def get_pin(self, pin_id: str) -> Dict[str, Any]:
        """Fetch pin data via API."""
        clean_id = self.extract_pin_id(pin_id)
        api_url = f"https://api.zhihu.com/pins/{clean_id}"
        data = self.client.get_json(api_url)
        if not data or "id" not in data:
            v4_url = f"https://www.zhihu.com/api/v4/pins/{clean_id}"
            data = self.client.get_json(v4_url)
        return data

    def scrape(self, pin_id: str, save_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Download pin, format markdown, and optionally save to disk."""
        data = self.get_pin(pin_id)
        if not data or "id" not in data:
            logger.warning("Pin %s not found or deleted.", pin_id)
            return {}

        author = data.get("author", {})
        created_time = data.get("created", 0)
        updated_time = data.get("updated", 0)

        created_str = datetime.fromtimestamp(created_time, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_time else ""
        updated_str = datetime.fromtimestamp(updated_time, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if updated_time else ""

        # Extract content segments
        content_items = data.get("content", [])
        text_parts = []
        image_urls = []
        for item in content_items:
            t = item.get("type", "")
            if t == "text":
                text_parts.append(item.get("content", ""))
            elif t == "image":
                url = item.get("original_url") or item.get("url", "")
                if url:
                    image_urls.append(url)

        content_raw = "\n\n".join(text_parts) if text_parts else data.get("excerpt_title", "")
        content_md = html_to_markdown(content_raw)
        for img in image_urls:
            content_md += f"\n\n![]({img})"

        title = (text_parts[0][:40] if text_parts else f"想法_{data.get('id')}")

        result = {
            "type": "pin",
            "id": str(data.get("id")),
            "title": title,
            "url": f"https://www.zhihu.com/pin/{data.get('id')}",
            "author_name": author.get("name", "未知"),
            "author_token": author.get("url_token", ""),
            "author_url": f"https://www.zhihu.com/people/{author.get('url_token', '')}",
            "created_at": created_str,
            "updated_at": updated_str,
            "voteup_count": data.get("reaction_count", 0),
            "comment_count": data.get("comment_count", 0),
            "markdown": content_md
        }

        if save_dir:
            save_dir.mkdir(parents=True, exist_ok=True)
            fname = f"想法_{safe_name(title)}_{result['id']}.md"
            file_path = save_dir / fname
            
            md_doc = f"# 想法：{title}\n\n"
            md_doc += f"> **发布者**: [{result['author_name']}]({result['author_url']})\n"
            md_doc += f"> **原始链接**: {result['url']}\n"
            md_doc += f"> **发布时间**: {result['created_at']} | **点赞数**: {result['voteup_count']} | **评论数**: {result['comment_count']}\n\n"
            md_doc += "---\n\n"
            md_doc += content_md + "\n"

            file_path.write_text(md_doc, encoding="utf-8")
            result["file_path"] = str(file_path)

        return result
