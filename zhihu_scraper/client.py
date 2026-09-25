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

# 知乎的「自动化挑战」cookie。
#
# `BEC` 与 `__zse_ck` 是知乎在判定「这次访问像机器人」之后种下的一次性风控凭证，
# 它们和种下它们那一刻的浏览器指纹 + 出口 IP 绑死。把这种 cookie 从一个人肉
# 浏览器里导出、再拿到服务器上重放，等于当场自曝：
#
#   * 带 `__zse_ck` 的请求 → 知乎直接回 403，响应体是 `zh-zse-ck` 挑战页
#     （HTML，不是 JSON）或 `need_login/unhuman` 跳转；
#   * 即使同一个 cookie 串里的 `z_c0` 完全有效，也照样被拒 —— 风控只看
#     `__zse_ck`，不看你的登录态有没有过期。
#
# 业务侧看到的现象就是「检索到 0 条」：每个 list_* 接口都吃 403 → 返回 {} →
# paginate 一页都吐不出来 → 文章 0 / 问答 0 / 专栏 0，而主页计数却显示几百篇。
#
# 实测（2026-09-25，真实用户 cookie，服务器 IP）：
#   完整 cookie              → 6 个接口全 403(zse)
#   完整 cookie − __zse_ck   → 6 个接口全 200  ← 单个 cookie 决定成败
#   只留 z_c0                → 6 个接口全 200
#
# browser.py 的 _clear_managed_challenge_cookies() 早已清掉这两个名字；这里把
# requests 直连这条路径补齐，两条取数通道口径保持一致。
MANAGED_CHALLENGE_COOKIES = ("BEC", "__zse_ck")

# 知乎的「打太快了」信号。响应是 HTTP 403，但 body 是 JSON 而不是挑战页：
#   {"error":{"message":"请求参数异常，请升级客户端后重试。","code":10003}}
# 它不是权限问题、也不是 cookie 问题 —— 退避几秒重试就能恢复。实测（2026-09-25）：
# 0.5s 间隔连打 20 页全 200；停 5 秒后再打，第 5 页就开始 10003。
# 也就是一个滚动窗口里大约 25 个请求后触发。244 篇文章 = 13 页分页 + profile +
# columns + pins + answers + 动态，轻松越线 —— 不处理就会「爬一半被掐」，
# 用户看到条数每次都不一样，或者干脆是 0。
RATE_LIMIT_ERROR_CODE = 10003

# 撞到 10003 之后的退避节奏（秒）。三段递增：先试探性地等 3 秒，不够就拉到 8 秒，
# 最后 20 秒。实测一次退避后就能恢复，所以正常路径只会多花 3 秒。
RATE_LIMIT_BACKOFF = (3, 8, 20)


def _looks_like_rate_limit(resp: "requests.Response") -> bool:
    """Whether a 403 is actually Zhihu's rolling-window rate limit (code 10003)."""
    if resp.status_code != 403:
        return False
    try:
        body = resp.json()
    except Exception:
        return False
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        try:
            return int(err.get("code") or 0) == RATE_LIMIT_ERROR_CODE
        except (TypeError, ValueError):
            return False
    return False


def is_challenge_cookie(name: str) -> bool:
    """Whether a cookie name is one of Zhihu's short-lived automation-challenge cookies."""
    n = (name or "").strip().lower()
    if not n:
        return False
    if n in ("bec", "__zse_ck", "_zse_ck"):
        return True
    return n.endswith("zse_ck")


def strip_challenge_cookies(cookie: str) -> str:
    """Drop Zhihu's short-lived automation-challenge cookies from a Cookie header.

    Safe to call on any cookie string; returns the input unchanged when there is
    nothing to strip. Never raises — a malformed fragment is simply kept as-is so
    a bad cookie can still be reported upstream instead of vanishing silently.
    """
    if not cookie:
        return cookie
    kept = []
    for item in cookie.split(";"):
        item = item.strip()
        if not item:
            continue
        name = item.split("=", 1)[0].strip()
        if is_challenge_cookie(name):
            continue
        kept.append(item)
    return "; ".join(kept)


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
        self.cookie = strip_challenge_cookies(cookie)
        self.user_agent = user_agent
        self.session = requests.Session()

        # 最近一次 get_json 看到的 HTTP 状态码（0 = 还没发过请求）。
        # 上游用它区分「接口真的没数据」和「接口被风控拦了」。
        self.last_status = 0
        # 最近一次请求是否撞上知乎的滚动窗口限流（code 10003）。
        # paginate 用它动态放慢后续翻页节奏，避免一路撞墙。
        self.last_rate_limited = False
        # 本次会话是否「曾经」撞过限流。最后一次请求可能已经恢复，所以
        # last_rate_limited 会翻回 False —— 要判断「这轮结果可不可信」得看这个
        # 只增不减的累计标记。
        self.rate_limited_seen = False

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
        """Dynamically update session cookie (challenge cookies are stripped)."""
        self.cookie = strip_challenge_cookies(cookie)
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
            self.last_status = resp.status_code
            self.last_rate_limited = False

            # ---- 第一优先：频率超限（403 + code 10003）→ 退避重试 ----
            # 这一条必须在「403 = 风控挑战」之前判断：两者都是 403，但一个是
            # 「等会儿再来」、一个是「这个身份被盯上了」，处理方式完全不同。
            if _looks_like_rate_limit(resp):
                self.last_rate_limited = True
                self.rate_limited_seen = True
                for attempt, wait in enumerate(RATE_LIMIT_BACKOFF, start=1):
                    logger.warning(
                        "GET %s hit Zhihu rate limit (code %d); backing off %ds (retry %d/%d)",
                        url, RATE_LIMIT_ERROR_CODE, wait, attempt, len(RATE_LIMIT_BACKOFF),
                    )
                    time.sleep(wait)
                    resp = self.get(url, params=params, timeout=timeout)
                    self.last_status = resp.status_code
                    if not _looks_like_rate_limit(resp):
                        break
                if _looks_like_rate_limit(resp):
                    logger.error(
                        "GET %s still rate limited after %d backoffs; returning empty",
                        url, len(RATE_LIMIT_BACKOFF),
                    )
                    return {}

            if resp.status_code == 403:
                # 403 在知乎这儿几乎从不是「cookie 过期」，而是风控挑战：响应体
                # 是 `zh-zse-ck` 挑战页或 need_login/unhuman 跳转。cookie 已经过
                # strip_challenge_cookies 清洗，再 403 就说明这个出口 / 身份被风控
                # 盯上了 —— 匿名重试一次，匿名请求反而常常能过。
                challenge = ("zh-zse-ck" in resp.text) or ("unhuman" in resp.text)
                logger.warning(
                    "GET %s returned HTTP 403%s; retrying anonymously",
                    url,
                    " (Zhihu automation challenge / zh-zse-ck)" if challenge else "",
                )
                clean_headers = {
                    k: v for k, v in self.session.headers.items()
                    if k.lower() not in ("cookie", "x-xsrftoken")
                }
                try:
                    clean_resp = requests.get(
                        url, params=params, headers=clean_headers, timeout=timeout
                    )
                    if clean_resp.status_code == 200:
                        self.last_status = 200
                        return clean_resp.json()
                except Exception:
                    pass
                logger.warning("GET %s still HTTP 403 after anonymous retry", url)
                return {}

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
        page_delay = delay
        while current_url:
            data = self.get_json(current_url, params=params if current_url == base_url else None)
            items = data.get("data", [])

            if self.last_rate_limited:
                # 撞过限流就把后续翻页节奏放慢，别一路撞墙 —— 撞一次就至少
                # 1 秒一页，最多 6 秒一页。慢总比「爬一半被掐」强。
                page_delay = min(max(page_delay * 2.0, 1.0), 6.0)

            if not items:
                # 空页有两种可能：
                #   1) 真的翻到底了（paging.is_end = true，data 是 []）；
                #   2) 这一页被风控 / 限流掐了 —— get_json 放弃后返回 {}。
                # 后者如果直接 break 就是「静默截断」，用户看到的条数每次都不一样
                # 甚至直接是 0。所以先给一次补救机会，再决定收工。
                if not data and self.last_status != 200:
                    logger.warning(
                        "pagination page came back empty with HTTP %s; retrying once: %s",
                        self.last_status, current_url,
                    )
                    time.sleep(max(page_delay, 1.5) * 2)
                    data = self.get_json(
                        current_url, params=params if current_url == base_url else None
                    )
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

            if page_delay:
                time.sleep(page_delay)
