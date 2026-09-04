"""Zhihu Comment Tree Scraper.
Crawls all root and nested child comments for articles, answers, and pins into structured tree data.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..client import ZhihuClient, html_to_markdown

logger = logging.getLogger("zhihu_scraper.scrapers.comment")


class CommentScraper:
    """Scrapes multi-level nested comment trees."""

    def __init__(self, client: ZhihuClient):
        self.client = client

    def get_root_comments(self, resource_type: str, resource_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch all root level comments for an article or answer."""
        endpoint_type = "articles" if resource_type == "article" else "answers" if resource_type == "answer" else "pins"
        url = f"https://api.zhihu.com/{endpoint_type}/{resource_id}/root_comments?order_by=score&limit={limit}"
        
        comments = []
        for item in self.client.paginate(url, limit=limit, max_items=200):
            comments.append(item)
        return comments

    def get_child_comments(self, comment_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch nested replies for a specific comment."""
        url = f"https://api.zhihu.com/comments/{comment_id}/child_comments?limit={limit}"
        replies = []
        for item in self.client.paginate(url, limit=limit, max_items=100):
            replies.append(item)
        return replies

    def scrape_comment_tree(self, resource_type: str, resource_id: str, save_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """Fetch complete nested comment tree."""
        root_comments = self.get_root_comments(resource_type, resource_id)
        comment_tree = []

        for c in root_comments:
            c_id = str(c.get("id"))
            author = c.get("author", {}).get("member", {})
            created_time = c.get("created_time", 0)
            created_str = datetime.fromtimestamp(created_time, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_time else ""
            
            node = {
                "id": c_id,
                "author_name": author.get("name", "匿名"),
                "author_token": author.get("url_token", ""),
                "author_url": f"https://www.zhihu.com/people/{author.get('url_token', '')}",
                "content": html_to_markdown(c.get("content", "")),
                "created_at": created_str,
                "vote_count": c.get("vote_count", 0),
                "child_comments_count": c.get("child_comments_count", 0),
                "replies": []
            }

            # Fetch nested child comments if present
            if node["child_comments_count"] > 0:
                child_raw = self.get_child_comments(c_id)
                for cr in child_raw:
                    cr_author = cr.get("author", {}).get("member", {})
                    cr_created = cr.get("created_time", 0)
                    cr_created_str = datetime.fromtimestamp(cr_created, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if cr_created else ""
                    node["replies"].append({
                        "id": str(cr.get("id")),
                        "author_name": cr_author.get("name", "匿名"),
                        "author_token": cr_author.get("url_token", ""),
                        "author_url": f"https://www.zhihu.com/people/{cr_author.get('url_token', '')}",
                        "content": html_to_markdown(cr.get("content", "")),
                        "created_at": cr_created_str,
                        "vote_count": cr.get("vote_count", 0)
                    })

            comment_tree.append(node)

        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(json.dumps(comment_tree, ensure_ascii=False, indent=2), encoding="utf-8")

        return comment_tree
