"""Zhihu Unified HTTP & API Client.
Handles session management, cookie authentication, header rotation, rate-limiting, and error handling.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Generator, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from html import unescape

logger = logging.getLogger("zhihu_scraper.client")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
)


def safe_name(text: str, max_len: int = 80) -> str:
    """Sanitize filename to prevent OS filesystem illegal characters."""
    text = re.sub(r'[\\/:*?"<>|。\s]+', "_", text)
    text = text.strip("_.")
    return text[:max_len] if len(text) > max_len else text or "untitled"


def html_to_markdown(html_content: str) -> str:
    """Convert HTML content into clean markdown text with links and images preserved."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")

    # Replace <a> with markdown links
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text()
        if href and text:
            a.replace_with(f"[{text}]({href})")

    # Replace <img> with markdown images
    for img in soup.find_all("img"):
        src = img.get("data-original") or img.get("data-actualsrc") or img.get("src", "")
        alt = img.get("alt", "")
        if src:
            img.replace_with(f"\n![{alt}]({src})\n")

    # Format code blocks
    for pre in soup.find_all("pre"):
        code = pre.get_text()
        pre.replace_with(f"\n```\n{code}\n```\n")

    text = soup.get_text("\n")
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class ZhihuClient:
    """Unified Zhihu API & Web Client."""

    def __init__(self, cookie: str = "", user_agent: str = DEFAULT_USER_AGENT):
        self.cookie = cookie
        self.user_agent = user_agent
        self.session = requests.Session()
        
        # Configure automatic retries for robust networking
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self._setup_headers()

    def update_cookie(self, cookie: str) -> None:
        """Dynamically update session cookie."""
        self.cookie = cookie
        self._setup_headers()

    def _setup_headers(self) -> None:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.zhihu.com/",
            "Origin": "https://www.zhihu.com"
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
            # Extract _xsrf if present in cookie
            xsrf_match = re.search(r"_xsrf=([^;]+)", self.cookie)
            if xsrf_match:
                headers["x-xsrftoken"] = xsrf_match.group(1).strip()
        self.session.headers.update(headers)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> requests.Response:
        """Perform GET request with headers and error logging."""
        if url.startswith("http://"):
            url = "https://" + url[7:]
        resp = self.session.get(url, params=params, timeout=timeout)
        return resp

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 20) -> Dict[str, Any]:
        """Perform GET request and parse JSON response safely."""
        try:
            resp = self.get(url, params=params, timeout=timeout)
            if resp.status_code == 403 and self.cookie:
                # Self-healing fallback: If stale cookie caused 403, retry cleanly without stale cookie
                logger.info("Request with cookie returned 403 on %s, retrying cleanly without stale cookie...", url)
                clean_headers = {k: v for k, v in self.session.headers.items() if k.lower() not in ["cookie", "x-xsrftoken"]}
                try:
                    clean_resp = requests.get(url, params=params, headers=clean_headers, timeout=timeout)
                    if clean_resp.status_code == 200:
                        self.cookie = ""
                        self._setup_headers()
                        return clean_resp.json()
                except Exception:
                    pass

            if resp.status_code != 200:
                logger.warning("GET %s returned HTTP %d: %s", url, resp.status_code, resp.text[:200])
                return {}
            return resp.json()
        except Exception as e:
            logger.error("Failed to fetch or decode JSON from %s: %s", url, e)
            return {}

    def get_html(self, url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> str:
        """Perform GET request and return raw HTML safely."""
        try:
            resp = self.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            logger.warning("GET HTML %s returned HTTP %d", url, resp.status_code)
            return ""
        except Exception as e:
            logger.error("Failed to fetch HTML from %s: %s", url, e)
            return ""

    def paginate(
        self,
        base_url: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        max_items: Optional[int] = None,
        delay: float = 0.5
    ) -> Generator[Dict[str, Any], None, None]:
        """Generic pagination generator supporting both cursor-based (paging.next) and offset-based pagination."""
        params = dict(params or {})
        params.setdefault("limit", limit)
        if "offset" not in params and "comment_v5" not in base_url:
            params.setdefault("offset", 0)

        current_url = base_url
        if current_url.startswith("http://"):
            current_url = "https://" + current_url[7:]

        yielded = 0
        while current_url:
            data = self.get_json(current_url, params=params if current_url == base_url else None)
            items = data.get("data", [])
            if not items:
                break

            for item in items:
                yield item
                yielded += 1
                if max_items and yielded >= max_items:
                    return

            paging = data.get("paging", {})
            if paging.get("is_end", True):
                break

            next_url = paging.get("next")
            if next_url:
                if next_url.startswith("http://"):
                    next_url = "https://" + next_url[7:]
                if next_url != current_url:
                    current_url = next_url
                else:
                    break
            elif "offset" in params and isinstance(params["offset"], int):
                params["offset"] += len(items)
            else:
                break

            if delay:
                time.sleep(delay)
