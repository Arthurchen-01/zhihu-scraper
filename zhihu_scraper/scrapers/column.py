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
from .answer import AnswerScraper

logger = logging.getLogger("zhihu_scraper.scrapers.column")


class ColumnScraper:
    """Scrapes Zhihu columns and their child articles."""

    def __init__(self, client: ZhihuClient):
        self.client = client
        self.article_scraper = ArticleScraper(client)
        self.answer_scraper = AnswerScraper(client)

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
        return data or {}

    def list_column_articles(self, column_id: str, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all articles and curated entries inside a column with formatted datetime and timestamp.
        Uses resilient endpoints (v4/articles and api.zhihu.com/articles + api.zhihu.com/items).
        """
        slug = self.extract_column_id(column_id)
        items_dict: Dict[str, Dict[str, Any]] = {}
        fetch_limit = None if (max_items is None or max_items <= 0) else max_items

        # 1. Primary: Query v4 articles endpoint (paginates completely without 403)
        url_v4 = f"https://www.zhihu.com/api/v4/columns/{slug}/articles"
        try:
            for art in self.client.paginate(url_v4, limit=20, max_items=fetch_limit):
                aid = str(art.get("id", ""))
                if not aid:
                    continue
                created_ts = int(art.get("created") or art.get("created_time") or 0)
                updated_ts = int(art.get("updated") or art.get("updated_time") or 0)
                created_str = datetime.fromtimestamp(created_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_ts else ""
                created_date = created_str[:10] if created_str else ""
                title = art.get("title", f"文章_{aid}")

                items_dict[aid] = {
                    "type": "article",
                    "id": aid,
                    "title": title,
                    "raw_title": title,
                    "url": f"https://zhuanlan.zhihu.com/p/{aid}",
                    "created_at": created_str,
                    "created_date": created_date,
                    "created_timestamp": created_ts,
                    "updated_timestamp": updated_ts,
                    "voteup_count": art.get("voteup_count", 0),
                    "comment_count": art.get("comment_count", 0),
                    "excerpt": art.get("excerpt", "")
                }
        except Exception as e:
            logger.warning("Error fetching articles from v4 endpoint: %s", e)

        # 1b. Fallback: If v4 articles returned empty, try api.zhihu.com/columns/{slug}/articles
        if not items_dict:
            url_api_art = f"https://api.zhihu.com/columns/{slug}/articles"
            try:
                for art in self.client.paginate(url_api_art, limit=20, max_items=fetch_limit):
                    aid = str(art.get("id", ""))
                    if not aid:
                        continue
                    created_ts = int(art.get("created") or art.get("created_time") or 0)
                    updated_ts = int(art.get("updated") or art.get("updated_time") or 0)
                    created_str = datetime.fromtimestamp(created_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_ts else ""
                    created_date = created_str[:10] if created_str else ""
                    title = art.get("title", f"文章_{aid}")

                    items_dict[aid] = {
                        "type": "article",
                        "id": aid,
                        "title": title,
                        "raw_title": title,
                        "url": f"https://zhuanlan.zhihu.com/p/{aid}",
                        "created_at": created_str,
                        "created_date": created_date,
                        "created_timestamp": created_ts,
                        "updated_timestamp": updated_ts,
                        "voteup_count": art.get("voteup_count", 0),
                        "comment_count": art.get("comment_count", 0),
                        "excerpt": art.get("excerpt", "")
                    }
            except Exception as e:
                logger.warning("Error fetching articles from api.zhihu.com: %s", e)

        # 2. Curated Items (picks up any answers or pins curated into the column)
        url_items = f"https://api.zhihu.com/columns/{slug}/items?limit=20&offset=0"
        try:
            items_data = self.client.get_json(url_items)
            if items_data and "data" in items_data:
                for raw in items_data["data"]:
                    raw_id = str(raw.get("id", ""))
                    if not raw_id or raw_id in items_dict:
                        continue
                    item_type = raw.get("type", "article")
                    created_ts = int(raw.get("created_time") or raw.get("created") or 0)
                    created_str = datetime.fromtimestamp(created_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_ts else ""
                    created_date = created_str[:10] if created_str else ""

                    if item_type == "answer":
                        q = raw.get("question", {})
                        q_title = q.get("title", "知乎问答")
                        title = f"[回答] {q_title}"
                        raw_title = q_title
                        q_id = q.get("id", "")
                        url = f"https://www.zhihu.com/question/{q_id}/answer/{raw_id}" if q_id else f"https://www.zhihu.com/answer/{raw_id}"
                    elif item_type == "pin":
                        pin_title = raw.get("excerpt_title") or "知乎想法"
                        title = f"[想法] {pin_title}"
                        raw_title = pin_title
                        url = f"https://www.zhihu.com/pin/{raw_id}"
                    else:
                        title = raw.get("title", f"文章_{raw_id}")
                        raw_title = title
                        url = f"https://zhuanlan.zhihu.com/p/{raw_id}"

                    items_dict[raw_id] = {
                        "type": item_type,
                        "id": raw_id,
                        "title": title,
                        "raw_title": raw_title,
                        "url": url,
                        "created_at": created_str,
                        "created_date": created_date,
                        "created_timestamp": created_ts,
                        "updated_timestamp": created_ts,
                        "voteup_count": raw.get("voteup_count", 0),
                        "comment_count": raw.get("comment_count", 0),
                        "excerpt": raw.get("excerpt", "")
                    }
        except Exception as e:
            logger.debug("Optional column items check finished: %s", e)

        # Sort newest first
        sorted_items = sorted(items_dict.values(), key=lambda x: x.get("created_timestamp", 0), reverse=True)
        if fetch_limit and fetch_limit > 0:
            sorted_items = sorted_items[:fetch_limit]
        return sorted_items

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
            itype = item.get("type", "article")
            if on_progress:
                on_progress(idx, total, f"正在抓取专栏条目: 《{item['title']}》")

            try:
                if itype == "answer":
                    res = self.answer_scraper.scrape(art_id, save_dir=col_dir)
                else:
                    res = self.article_scraper.scrape(art_id, save_dir=col_dir)
                if res:
                    results.append(res)
            except Exception as e:
                logger.error("Error scraping column item %s: %s", art_id, e)

        return results
