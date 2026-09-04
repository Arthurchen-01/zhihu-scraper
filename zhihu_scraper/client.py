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
        resp = self.session.get(url, params=params, timeout=timeout)
        return resp

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Dict[str, Any]:
        """Perform GET request and parse JSON response safely."""
        resp = self.get(url, params=params, timeout=timeout)
        if resp.status_code != 200:
            logger.warning("GET %s returned HTTP %d: %s", url, resp.status_code, resp.text[:200])
            return {}
        try:
            return resp.json()
        except Exception as e:
            logger.error("Failed to decode JSON from %s: %s", url, e)
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
        """Generic pagination generator supporting Zhihu standard cursor/offset pagination."""
        params = dict(params or {})
        params.setdefault("limit", limit)
        params.setdefault("offset", 0)

        yielded = 0
        while True:
            data = self.get_json(base_url, params=params)
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

            params["offset"] += len(items)
            if delay:
                time.sleep(delay)
