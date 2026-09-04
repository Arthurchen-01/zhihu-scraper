"""Zhihu Question & Answer Scraper.
Scrapes question details, answer full text, author metadata, and voteups.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..client import ZhihuClient, safe_name, html_to_markdown

logger = logging.getLogger("zhihu_scraper.scrapers.answer")


class AnswerScraper:
    """Scrapes Zhihu answers and parent questions."""

    def __init__(self, client: ZhihuClient):
        self.client = client

    @staticmethod
    def extract_answer_id(url_or_id: str) -> str:
        """Extract answer ID from string or URL."""
        cleaned = url_or_id.strip()
        m = re.search(r"zhihu\.com/question/\d+/answer/(\d+)", cleaned)
        if m:
            return m.group(1)
        m2 = re.search(r"/answer/(\d+)", cleaned)
        if m2:
            return m2.group(1)
        m3 = re.search(r"\b(\d{8,15})\b", cleaned)
        if m3:
            return m3.group(1)
        return cleaned.split("?")[0].strip("/")

    def get_answer(self, answer_id: str) -> Dict[str, Any]:
        """Fetch answer metadata and content via API."""
        clean_id = self.extract_answer_id(answer_id)
        api_url = f"https://api.zhihu.com/answers/{clean_id}?include=content,question,author,created_time,updated_time,voteup_count,comment_count"
        data = self.client.get_json(api_url)
        if not data or "id" not in data:
            v4_url = f"https://www.zhihu.com/api/v4/answers/{clean_id}?include=content,question,author,created_time,updated_time,voteup_count,comment_count"
            data = self.client.get_json(v4_url)
        return data

    def scrape(self, answer_id: str, save_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Download answer, format markdown, and optionally save to disk."""
        data = self.get_answer(answer_id)
        if not data or "id" not in data:
            logger.warning("Answer %s not found or deleted.", answer_id)
            return {}

        question = data.get("question", {})
        q_title = question.get("title", f"问题_{question.get('id', '')}")
        content_html = data.get("content", "")
        content_md = html_to_markdown(content_html)
        author = data.get("author", {})
        created_time = data.get("created_time", 0)
        updated_time = data.get("updated_time", 0)

        created_str = datetime.fromtimestamp(created_time, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_time else ""
        updated_str = datetime.fromtimestamp(updated_time, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if updated_time else ""

        result = {
            "type": "answer",
            "id": str(data.get("id")),
            "question_id": str(question.get("id", "")),
            "title": q_title,
            "url": f"https://www.zhihu.com/question/{question.get('id', '')}/answer/{data.get('id')}",
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
            fname = f"问答_{safe_name(q_title)}_{result['id']}.md"
            file_path = save_dir / fname
            
            md_doc = f"# 问答：{q_title}\n\n"
            md_doc += f"> **回答者**: [{result['author_name']}]({result['author_url']})\n"
            md_doc += f"> **原始链接**: {result['url']}\n"
            md_doc += f"> **发布时间**: {result['created_at']} | **赞同数**: {result['voteup_count']} | **评论数**: {result['comment_count']}\n\n"
            md_doc += "---\n\n"
            md_doc += content_md + "\n"

            file_path.write_text(md_doc, encoding="utf-8")
            result["file_path"] = str(file_path)

        return result
