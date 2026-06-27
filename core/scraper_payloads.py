"""
scraper_payloads.py - Pure payload normalization helpers for scraper workflows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def format_zhihu_date(timestamp: int) -> str:
    """Convert a Zhihu timestamp into YYYY-MM-DD with a safe today fallback."""
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    return datetime.today().strftime("%Y-%m-%d")


def build_article_item(*, url: str, article_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize article API payload into the internal item shape."""
    author = data.get("author", {}).get("name", "未知作者")
    title = data.get("title", "未知专栏标题")
    html = data.get("content", "")
    title_img = data.get("image_url")
    if title_img:
        html = f'<img src="{title_img}" alt="TitleImage"><br>{html}'

    return {
        "id": article_id,
        "type": "article",
        "url": url,
        "title": title.strip(),
        "author": author.strip(),
        "html": html,
        "date": format_zhihu_date(data.get("created", 0)),
        "upvotes": data.get("voteup_count", 0),
    }


def build_answer_item(*, url: str, answer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize single-answer API payload into the internal item shape."""
    author = data.get("author", {}).get("name", "未知作者")
    title = data.get("question", {}).get("title", "未知问题")

    return {
        "id": answer_id,
        "type": "answer",
        "url": url,
        "title": title.strip(),
        "author": author.strip(),
        "html": data.get("content", ""),
        "date": format_zhihu_date(data.get("created_time", 0)),
        "upvotes": data.get("voteup_count", 0),
    }


def build_question_answer_item(*, question_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one question-page answer into the internal item shape."""
    answer_id = str(data.get("id", ""))
    author = data.get("author", {}).get("name", "未知作者")
    title = data.get("question", {}).get("title", "未知问题")
    return {
        "id": answer_id,
        "type": "answer",
        "url": f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}",
        "title": title.strip(),
        "author": author.strip(),
        "html": data.get("content", ""),
        "date": format_zhihu_date(data.get("created_time", 0)),
        "upvotes": data.get("voteup_count", 0),
    }

