"""Zhihu Author Scraper & Asset Cataloger.
Scrapes author profile, bio, followers, columns, articles, answers, and pins.
Provides catalog_all_assets() for user inspection and selective checkboxes.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..client import ZhihuClient, safe_name, html_to_markdown

logger = logging.getLogger("zhihu_scraper.scrapers.author")


class AuthorScraper:
    """Scrapes all public assets belonging to a Zhihu user."""

    def __init__(self, client: ZhihuClient):
        self.client = client

    @staticmethod
    def extract_url_token(user_input: str) -> str:
        """Extract url_token from URL, e.g. https://www.zhihu.com/people/shou-qi-hei -> shou-qi-hei."""
        cleaned = user_input.strip()
        if "zhihu.com/people/" in cleaned:
            parsed = urlparse(cleaned)
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] == "people":
                return parts[1]
        # Return as-is if already a token
        return cleaned.split("?")[0].strip("/")

    def get_profile(self, url_token: str) -> Dict[str, Any]:
        """Fetch author full profile info."""
        api_url = f"https://api.zhihu.com/people/{url_token}"
        data = self.client.get_json(api_url)
        if not data or "id" not in data:
            # Fallback to v4 endpoint
            api_v4 = f"https://www.zhihu.com/api/v4/members/{url_token}?include=headline,description,avatar_url,follower_count,voteup_count,thanked_count,articles_count,answers_count,pins_count,columns_count"
            data = self.client.get_json(api_v4)
        return data

    def list_columns(self, url_token: str) -> List[Dict[str, Any]]:
        """List all columns owned or contributed to by this author."""
        url = f"https://www.zhihu.com/api/v4/members/{url_token}/column-contributions"
        columns = []
        for item in self.client.paginate(url, limit=20, max_items=100):
            col = item.get("column", item)
            columns.append({
                "type": "column",
                "id": col.get("id", ""),
                "title": col.get("title", ""),
                "url": col.get("url", f"https://www.zhihu.com/column/{col.get('id', '')}"),
                "description": col.get("description", ""),
                "articles_count": col.get("articles_count", 0),
                "author_name": col.get("author", {}).get("name", "")
            })
        return columns

    def list_articles(self, url_token: str, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all articles published by this author."""
        url = f"https://www.zhihu.com/api/v4/members/{url_token}/articles"
        articles = []
        for item in self.client.paginate(url, limit=20, max_items=max_items):
            articles.append({
                "type": "article",
                "id": str(item.get("id", "")),
                "title": item.get("title", "未命名文章"),
                "url": f"https://zhuanlan.zhihu.com/p/{item.get('id')}",
                "created_at": item.get("created", 0),
                "updated_at": item.get("updated", 0),
                "voteup_count": item.get("voteup_count", 0),
                "comment_count": item.get("comment_count", 0),
                "excerpt": item.get("excerpt", "")
            })
        return articles

    def list_answers(self, url_token: str, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all answers written by this author."""
        url = f"https://www.zhihu.com/api/v4/members/{url_token}/answers?include=question,created_time,updated_time,voteup_count,comment_count,excerpt"
        answers = []
        for item in self.client.paginate(url, limit=20, max_items=max_items):
            q = item.get("question", {})
            q_id = q.get("id", "")
            ans_id = item.get("id", "")
            answers.append({
                "type": "answer",
                "id": str(ans_id),
                "question_id": str(q_id),
                "title": q.get("title", "未命名问答"),
                "url": f"https://www.zhihu.com/question/{q_id}/answer/{ans_id}",
                "created_at": item.get("created_time", 0),
                "updated_at": item.get("updated_time", 0),
                "voteup_count": item.get("voteup_count", 0),
                "comment_count": item.get("comment_count", 0),
                "excerpt": item.get("excerpt", "")
            })
        return answers

    def list_pins(self, url_token: str, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all pins (想法) posted by this author."""
        url = f"https://www.zhihu.com/api/v4/members/{url_token}/pins"
        pins = []
        for item in self.client.paginate(url, limit=20, max_items=max_items):
            pin_id = item.get("id", "")
            content_text = item.get("excerpt_title") or item.get("content", [{}])[0].get("content", "")
            pins.append({
                "type": "pin",
                "id": str(pin_id),
                "title": content_text[:60] if content_text else f"想法_{pin_id}",
                "url": f"https://www.zhihu.com/pin/{pin_id}",
                "created_at": item.get("created", 0),
                "voteup_count": item.get("reaction_count", 0),
                "comment_count": item.get("comment_count", 0),
                "excerpt": content_text
            })
        return pins

    def catalog_all_assets(
        self,
        user_input: str,
        include_articles: bool = True,
        include_answers: bool = True,
        include_pins: bool = True,
        include_columns: bool = True,
        max_per_category: int = 50
    ) -> Dict[str, Any]:
        """One-stop inspection method: resolves profile and returns all categorized assets."""
        token = self.extract_url_token(user_input)
        profile = self.get_profile(token)

        author_name = profile.get("name", token)
        headline = profile.get("headline", "")
        avatar = profile.get("avatar_url", "")
        profile_url = f"https://www.zhihu.com/people/{token}"

        assets = []
        cols = []

        if include_columns:
            try:
                cols = self.list_columns(token)
                assets.extend(cols)
            except Exception as e:
                logger.warning("Error fetching columns: %s", e)

        if include_articles:
            try:
                arts = self.list_articles(token, max_items=max_per_category)
                assets.extend(arts)
            except Exception as e:
                logger.warning("Error fetching articles: %s", e)

        if include_answers:
            try:
                ans = self.list_answers(token, max_items=max_per_category)
                assets.extend(ans)
            except Exception as e:
                logger.warning("Error fetching answers: %s", e)

        if include_pins:
            try:
                pins = self.list_pins(token, max_items=max_per_category)
                assets.extend(pins)
            except Exception as e:
                logger.warning("Error fetching pins: %s", e)

        return {
            "author": {
                "name": author_name,
                "url_token": token,
                "headline": headline,
                "avatar_url": avatar,
                "profile_url": profile_url,
                "articles_count": profile.get("articles_count", 0),
                "answers_count": profile.get("answers_count", 0),
                "pins_count": profile.get("pins_count", 0),
                "columns_count": len(cols) or profile.get("columns_count", 0)
            },
            "columns": cols,
            "total_items": len(assets),
            "items": assets
        }
