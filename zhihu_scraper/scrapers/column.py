"""Zhihu Column Scraper.
Enumerates and archives all articles belonging to a Zhihu column.
"""

from __future__ import annotations

import logging
import re
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
        m = re.search(r"zhihu\.com/column/([^/?#]+)", cleaned)
        if m:
            return m.group(1)
        return cleaned.split("?")[0].strip("/")

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
        """List all article summaries inside a column."""
        slug = self.extract_column_id(column_id)
        url = f"https://www.zhihu.com/api/v4/columns/{slug}/items"
        items = []
        for raw in self.client.paginate(url, limit=20, max_items=max_items):
            # Column items can be articles or pins
            art = raw.get("article", raw)
            items.append({
                "type": "article",
                "id": str(art.get("id")),
                "title": art.get("title", "未命名文章"),
                "url": f"https://zhuanlan.zhihu.com/p/{art.get('id')}",
                "created_at": art.get("created", 0),
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
