"""Zhihu Column Scraper.
Enumerates and archives all articles belonging to a Zhihu column.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..client import ZhihuClient, safe_name
from .article import ArticleScraper

logger = logging.getLogger("zhihu_scraper.scrapers.column")


class ColumnScraper:
    """Scrapes Zhihu columns and their child articles."""

    def __init__(self, client: ZhihuClient):
        self.client = client
        self.article_scraper = ArticleScraper(client)

    @staticmethod
    def extract_column_id(url_or_id: str) -> str:
        """Extract column ID or slug from URL or raw string."""
        cleaned = url_or_id.strip()
        m_c = re.search(r"(c_\d+)", cleaned)
        if m_c:
            return m_c.group(1)
        m = re.search(r"(?:columns?|zhuanlan\.zhihu\.com)/([^/?#]+)", cleaned)
        if m and m.group(1) not in ["api", "v4"]:
            return m.group(1)
        parts = cleaned.split("?")[0].strip("/").split("/")
        return parts[-1] if parts else cleaned

    def get_column_info(self, column_id: str) -> Dict[str, Any]:
        """Fetch metadata about a column."""
        slug = self.extract_column_id(column_id)
        url = f"https://api.zhihu.com/columns/{slug}"
        data = self.client.get_json(url)
        if not data or "id" not in data:
            url_v4 = f"https://www.zhihu.com/api/v4/columns/{slug}"
            data = self.client.get_json(url_v4)
        return data

    def list_column_articles(self, column_id: str, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all article summaries inside a column with formatted datetime and timestamp."""
        slug = self.extract_column_id(column_id)
        url = f"https://www.zhihu.com/api/v4/columns/{slug}/items"
        items = []
        fetch_limit = None if (max_items is None or max_items <= 0) else max_items
        for raw in self.client.paginate(url, limit=20, max_items=fetch_limit):
            # Column items can be articles or pins
            art = raw.get("article", raw)
            created_ts = int(art.get("created") or art.get("created_time") or 0)
            updated_ts = int(art.get("updated") or art.get("updated_time") or 0)
            created_str = datetime.fromtimestamp(created_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_ts else ""
            created_date = created_str[:10] if created_str else ""

            items.append({
                "type": "article",
                "id": str(art.get("id")),
                "title": art.get("title", "未命名文章"),
                "url": f"https://zhuanlan.zhihu.com/p/{art.get('id')}",
                "created_at": created_str,
                "created_date": created_date,
                "created_timestamp": created_ts,
                "updated_timestamp": updated_ts,
                "voteup_count": art.get("voteup_count", 0),
                "comment_count": art.get("comment_count", 0),
                "excerpt": art.get("excerpt", "")
            })
        return items

    def scrape_all(
        self,
        column_id: str,
        save_dir: Optional[Path] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """Download all articles in the column with real-time progress callbacks."""
        slug = self.extract_column_id(column_id)
        info = self.get_column_info(slug)
        title = info.get("title", slug)
        col_dir = (save_dir / f"column_{safe_name(title)}") if save_dir else None

        articles = self.list_column_articles(slug)
        total = len(articles)
        results = []

        for idx, item in enumerate(articles, 1):
            art_id = item["id"]
            if on_progress:
                on_progress(idx, total, f"正在抓取专栏文章: 《{item['title']}》")

            try:
                res = self.article_scraper.scrape(art_id, save_dir=col_dir)
                if res:
                    results.append(res)
            except Exception as e:
                logger.error("Error scraping article %s: %s", art_id, e)

        return results
