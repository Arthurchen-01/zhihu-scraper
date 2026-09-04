"""Zhihu API Client with retry, rate-limiting, and comprehensive endpoints.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
)


def safe_filename(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[\\/:*?"<>|。\s\n\r]+', '_', text)
    text = text.strip("_. ")
    return text[:max_len] if len(text) > max_len else text or "untitled"


def strip_html_tags(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "lxml")
    text = unescape(soup.get_text("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_timestamp(ts: int | float | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


class ZhihuClient:
    def __init__(self, cookie: str, pause_seconds: float = 0.5):
        self.cookie = cookie.strip()
        self.pause = pause_seconds
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        s = requests.Session()
        retries = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=1.2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=5, pool_maxsize=10)
        s.mount("https://", adapter)
        s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cookie": self.cookie,
            "Referer": "https://www.zhihu.com/",
            "x-requested-with": "fetch",
            "Connection": "keep-alive",
        })
        return s

    def _get_json(self, url: str, params: dict | None = None, timeout: int = 30) -> dict[str, Any]:
        time.sleep(self.pause)
        r = self.session.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()

    # ── 1. 搜索接口 ──────────────────────────────────────────
    def search(self, query: str, search_type: str = "general", offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """Search Zhihu content. search_type: general | article | answer"""
        url = "https://www.zhihu.com/api/v4/search_v3"
        params = {
            "t": search_type,
            "q": query,
            "correction": 1,
            "offset": offset,
            "limit": limit,
            "search_hash_id": "",
            "vertical_info": "",
        }
        return self._get_json(url, params=params)

    # ── 2. 回答详情与评论 ────────────────────────────────────
    def get_answer(self, answer_id: str | int) -> dict[str, Any]:
        url = f"https://www.zhihu.com/api/v4/answers/{answer_id}"
        params = {"include": "content,excerpt,voteup_count,comment_count,created_time,updated_time,author,question"}
        return self._get_json(url, params=params)

    def get_question_answers(self, question_id: str | int, offset: int = 0, limit: int = 20, sort_by: str = "default") -> dict[str, Any]:
        url = f"https://www.zhihu.com/api/v4/questions/{question_id}/answers"
        params = {
            "include": "data[*].id,content,excerpt,voteup_count,comment_count,created_time,updated_time,author",
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
        }
        return self._get_json(url, params=params)

    # ── 3. 文章详情 ──────────────────────────────────────────
    def get_article(self, article_id: str | int) -> dict[str, Any]:
        url = f"https://www.zhihu.com/api/v4/articles/{article_id}"
        return self._get_json(url)

    # ── 4. 评论区 (知乎 v5 协议) ──────────────────────────────
    def get_root_comments(self, target_type: str, target_id: str | int, offset: str = "", limit: int = 20) -> dict[str, Any]:
        """target_type: 'answers' or 'articles'"""
        url = f"https://www.zhihu.com/api/v4/comment_v5/{target_type}/{target_id}/root_comment"
        params = {"limit": limit, "offset": offset}
        return self._get_json(url, params=params)

    def get_child_comments(self, root_comment_id: str | int, offset: str = "", limit: int = 20) -> dict[str, Any]:
        url = f"https://www.zhihu.com/api/v4/comment_v5/comment/{root_comment_id}/child_comment"
        params = {"limit": limit, "offset": offset}
        return self._get_json(url, params=params)

    def fetch_all_comments_for_target(self, target_type: str, target_id: str | int, max_roots: int = 50) -> list[dict[str, Any]]:
        """Fetch all root comments and nested child comments for an answer or article."""
        comments_list: list[dict[str, Any]] = []
        offset = ""
        roots_fetched = 0

        while True:
            try:
                data = self.get_root_comments(target_type, target_id, offset=offset, limit=20)
            except Exception as e:
                print(f"      [警告] 抓取评论失败 ({target_type}/{target_id}): {e}")
                break

            items = data.get("data") or []
            if not items:
                break

            for root in items:
                root_author = root.get("author") or {}
                root_id = str(root.get("id"))
                root_content = strip_html_tags(root.get("content"))
                child_count = root.get("child_comment_count", 0)

                comment_entry = {
                    "id": root_id,
                    "target_type": target_type,
                    "target_id": str(target_id),
                    "is_child": False,
                    "root_id": root_id,
                    "author_name": root_author.get("name", "匿名用户"),
                    "author_id": str(root_author.get("id", "")),
                    "author_token": root_author.get("url_token", ""),
                    "author_url": f"https://www.zhihu.com/people/{root_author.get('url_token')}" if root_author.get('url_token') else "",
                    "content": root_content,
                    "created_at": format_timestamp(root.get("created_time")),
                    "voteup_count": root.get("voteup_count", 0),
                    "child_count": child_count,
                    "raw_json": root,
                }
                comments_list.append(comment_entry)
                roots_fetched += 1

                # 抓取楼中楼 (Child Comments)
                if child_count > 0:
                    child_offset = ""
                    while True:
                        try:
                            c_data = self.get_child_comments(root_id, offset=child_offset, limit=20)
                        except Exception:
                            break
                        child_items = c_data.get("data") or []
                        if not child_items:
                            break
                        for child in child_items:
                            c_author = child.get("author") or {}
                            c_content = strip_html_tags(child.get("content"))
                            reply_to_author = child.get("reply_to_author") or {}
                            comments_list.append({
                                "id": str(child.get("id")),
                                "target_type": target_type,
                                "target_id": str(target_id),
                                "is_child": True,
                                "root_id": root_id,
                                "reply_to": reply_to_author.get("name", ""),
                                "author_name": c_author.get("name", "匿名用户"),
                                "author_id": str(c_author.get("id", "")),
                                "author_token": c_author.get("url_token", ""),
                                "author_url": f"https://www.zhihu.com/people/{c_author.get('url_token')}" if c_author.get('url_token') else "",
                                "content": c_content,
                                "created_at": format_timestamp(child.get("created_time")),
                                "voteup_count": child.get("voteup_count", 0),
                                "child_count": 0,
                                "raw_json": child,
                            })

                        paging = c_data.get("paging") or {}
                        if paging.get("is_end") or not paging.get("next"):
                            break
                        child_offset = str(parse_qs(urlparse(paging["next"]).query).get("offset", [""])[0])

            paging = data.get("paging") or {}
            if paging.get("is_end") or not paging.get("next") or roots_fetched >= max_roots:
                break
            offset = str(parse_qs(urlparse(paging["next"]).query).get("offset", [""])[0])

        return comments_list

    # ── 5. 用户主页穿透 ──────────────────────────────────────
    def get_user_profile(self, url_token: str) -> dict[str, Any]:
        url = f"https://www.zhihu.com/api/v4/members/{url_token}"
        params = {"include": "headline,description,answer_count,articles_count,pins_count,follower_count,following_count,voteup_count,thanked_count"}
        return self._get_json(url, params=params)

    def fetch_user_all_content(self, url_token: str, max_items_per_type: int = 100) -> dict[str, list[dict[str, Any]]]:
        """Fetch all answers, articles, and pins of a user for cross-investigation."""
        results: dict[str, list[dict[str, Any]]] = {"answers": [], "articles": [], "pins": []}

        # 1. Answers
        offset = 0
        while len(results["answers"]) < max_items_per_type:
            try:
                data = self._get_json(
                    f"https://www.zhihu.com/api/v4/members/{url_token}/answers",
                    params={"include": "data[*].id,content,excerpt,created_time,updated_time,url,question.id,question.title,comment_count,voteup_count",
                            "offset": offset, "limit": 20}
                )
            except Exception:
                break
            batch = data.get("data") or []
            if not batch:
                break
            for a in batch:
                q = a.get("question") or {}
                results["answers"].append({
                    "id": str(a.get("id")),
                    "type": "answer",
                    "title": q.get("title", ""),
                    "question_id": str(q.get("id", "")),
                    "url": f"https://www.zhihu.com/answer/{a.get('id')}",
                    "content": strip_html_tags(a.get("content") or a.get("excerpt", "")),
                    "created_at": format_timestamp(a.get("created_time")),
                    "voteup_count": a.get("voteup_count", 0),
                })
            paging = data.get("paging") or {}
            if paging.get("is_end") or not paging.get("next"):
                break
            offset = int(parse_qs(urlparse(paging["next"]).query).get("offset", [0])[0])

        # 2. Articles
        offset = 0
        while len(results["articles"]) < max_items_per_type:
            try:
                data = self._get_json(
                    f"https://www.zhihu.com/api/v4/members/{url_token}/articles",
                    params={"include": "data[*].id,title,content,excerpt,created,updated,comment_count,voteup_count,url",
                            "offset": offset, "limit": 20}
                )
            except Exception:
                break
            batch = data.get("data") or []
            if not batch:
                break
            for art in batch:
                results["articles"].append({
                    "id": str(art.get("id")),
                    "type": "article",
                    "title": art.get("title", ""),
                    "url": f"https://zhuanlan.zhihu.com/p/{art.get('id')}",
                    "content": strip_html_tags(art.get("content") or art.get("excerpt", "")),
                    "created_at": format_timestamp(art.get("created")),
                    "voteup_count": art.get("voteup_count", 0),
                })
            paging = data.get("paging") or {}
            if paging.get("is_end") or not paging.get("next"):
                break
            offset = int(parse_qs(urlparse(paging["next"]).query).get("offset", [0])[0])

        # 3. Pins (想法)
        offset = 0
        while len(results["pins"]) < max_items_per_type:
            try:
                data = self._get_json(
                    f"https://www.zhihu.com/api/v4/members/{url_token}/pins",
                    params={"include": "data[*].id,content,created,updated,comment_count,like_count",
                            "offset": offset, "limit": 20}
                )
            except Exception:
                break
            batch = data.get("data") or []
            if not batch:
                break
            for pin in batch:
                raw_c = pin.get("content", "")
                if isinstance(raw_c, list):
                    c_text = "".join([seg.get("content", "") or seg.get("text", "") if isinstance(seg, dict) else str(seg) for seg in raw_c])
                else:
                    c_text = str(raw_c)
                results["pins"].append({
                    "id": str(pin.get("id")),
                    "type": "pin",
                    "title": f"想法_{pin.get('id')}",
                    "url": f"https://www.zhihu.com/pin/{pin.get('id')}",
                    "content": strip_html_tags(c_text),
                    "created_at": format_timestamp(pin.get("created")),
                    "voteup_count": pin.get("like_count", 0),
                })
            paging = data.get("paging") or {}
            if paging.get("is_end") or not paging.get("next"):
                break
            offset = int(parse_qs(urlparse(paging["next"]).query).get("offset", [0])[0])

        return results
