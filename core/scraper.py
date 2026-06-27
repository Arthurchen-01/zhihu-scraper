"""
scraper.py - Zhihu Page Scraping & Image Download Module (v3.0 Pure Protocol Engine API Version)

Disclaimer:
This project is for academic research and learning purposes only.
Please comply with Zhihu's terms of service and robots.txt.

zhihu-scraper integrates a pure protocol-layer network client that directly fetches from the v4 API.
Anti-blocking core relies on:
1. curl_cffi simulates real browser TLS fingerprints (chrome110/edge)
2. Load one primary Cookie file from .local/cookies.json
3. Intelligent fallback to Playwright headless browser (only for heavily protected routes like Columns)

Core scraping strategy:
- Default to curl_cffi pure protocol API mode (lightweight, fast, no browser required)
- When API encounters 403/blocking, automatically fall back to Playwright browser rendering

================================================================================
scraper.py — 知乎页面抓取 & 图片下载模块 (v3.0 纯协议引擎 API 版)

免责声明：
本项目仅供学术研究和学习交流使用，请勿用于任何商业用途。
使用者应遵守知乎的相关服务协议和 robots.txt 协议。

集成纯协议层网络客户端，直接基于 v4 API 抓取。
防封核心依赖于：
1. curl_cffi 模拟真实浏览器 TLS 指纹 (chrome110/edge)
2. 从 .local/cookies.json 加载一份主 Cookie
3. 智能降级回退到 Playwright 无头浏览器 (仅专栏等强风控路由)

核心抓取策略：
- 默认使用 curl_cffi 纯协议 API 模式 (轻量、快速、无需浏览器)
- 当 API 遭遇 403/风控拦截时，自动降级启动 Playwright 浏览器渲染
================================================================================
"""

import asyncio
from typing import Union, List, Optional, Dict, Any, Callable
import httpx
from pathlib import Path
import re
import hashlib
from random import uniform

from .config_runtime import get_logger
from .humanizer import get_humanizer
from .api_client import ZhihuAPIClient
from .scraper_contracts import PageFetchResult, PaginationStats, to_scraped_items
from .scraper_payloads import (
    build_answer_item,
    build_article_item,
    build_question_answer_item,
)

class ZhihuDownloader:
    """
    Chinese: 从知乎文章/回答页面直接抓取 API 数据并下载图片到本地。
    English: Downloads API data from Zhihu articles/answers and saves images locally.
    """

    def __init__(self, url: str) -> None:
        # Initialize URL and detect page type
        # 初始化 URL 并检测页面类型
        self.url = url.split("?")[0]
        self.page_type = self._detect_type()
        self.api_client = ZhihuAPIClient()
        self.log = get_logger()

    def _detect_type(self) -> str:
        """
        Detect page type from URL
        Detect: article (zhuanlan), answer, or question page
        从 URL 检测页面类型：专栏、回答或问题页面
        """
        if "zhuanlan.zhihu.com" in self.url:
            return "article"
        if "/answer/" in self.url:
            return "answer"
        if "/question/" in self.url:
            return "question"
        return "article"

    def has_valid_cookies(self) -> bool:
        """
        Check if valid cookies exist (for CLI compatibility)
        检查是否有有效 Cookie (兼容 CLI 调用)
        """
        return bool(self.api_client._cookies_dict)

    async def fetch_page(self, **kwargs) -> Union[dict, List[dict]]:
        """Backward-compatible fetch entrypoint returning legacy dict/list payloads."""
        return (await self.fetch_result(**kwargs)).to_legacy_payload()

    async def fetch_result(self, **kwargs) -> PageFetchResult:
        """
        Typed fetch entrypoint returning a stable result contract.
        返回稳定结果契约的抓取入口。
        """
        humanizer = get_humanizer()

        self.log.info("start_fetching", url=self.url, page_type=self.page_type)
        access_mode = "协议模式" if self.page_type == "article" else "API 模式"
        print(f"🌍 访问 [{access_mode}]: {self.url}")

        # 模拟部分延时，以避免瞬时高频请求
        await humanizer.page_load()

        headless = kwargs.pop("headless", True)

        if self.page_type == "article":
            raw_items = [await self._extract_article(headless=headless)]
            pagination = None
        elif self.page_type == "question":
            question_result = await self._extract_question_result(**kwargs)
            raw_items = question_result["items"]
            pagination = PaginationStats.from_dict(question_result["stats"])
        else:
            raw_items = [await self._extract_answer()]
            pagination = None

        return PageFetchResult(
            source_url=self.url,
            page_type=self.page_type,
            items=to_scraped_items(raw_items),
            pagination=pagination,
        )

    async def _extract_article(self, *, headless: bool = True) -> dict:
        """提取专栏文章数据。

        流程说明：
        1. 尝试协议层 HTML 直取，并解析 `js-initialData`
        2. 首轮失败时用同一份主 Cookie 重试一次
        3. 若仍失败，再自动降级到 Playwright 浏览器渲染
        """
        # 从 URL 提取 Article ID
        # e.g., https://zhuanlan.zhihu.com/p/123456
        match = re.search(r"p/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从专栏 URL 提取 ID: {self.url}")

        article_id = match.group(1)
        try:
            print("📰 专栏阶段 1/3: 协议层 HTML 直取")
            data = self.api_client.get_article(article_id)
        except Exception as protocol_error:
            self.log.warning("article_protocol_failed", article_id=article_id, error=str(protocol_error))
            print(f"⚠️ 协议路径未能提取专栏 ({protocol_error})")
            print("🔁 已尝试 HTML 直取，并使用主 Cookie 重试一次")
            print("🔄 专栏阶段 3/3: 正在启动 Playwright 无头浏览器智能降级回退机制...")

            # Fallback 策略：使用 Playwright 渲染页面
            from .browser_fallback import extract_zhuanlan_html
            from .cookie_manager import cookie_manager

            # 使用现有 session 的 cookies
            session_cookies = cookie_manager.get_current_session()
            try:
                data = await extract_zhuanlan_html(article_id, session_cookies, headless=headless)
            except Exception as fallback_error:
                raise Exception(
                    f"专栏文章 {article_id} 协议抓取失败: {protocol_error}; "
                    f"浏览器回退失败: {fallback_error}"
                ) from fallback_error

            if not data:
                raise Exception(
                    f"专栏文章 {article_id} 协议抓取失败: {protocol_error}; "
                    "浏览器回退未返回内容，请手工检查 URL 或刷新 z_c0 / d_c0。"
                )

        return build_article_item(url=self.url, article_id=article_id, data=data)

    async def _extract_answer(self) -> dict:
        """提取单个回答数据。"""
        # https://www.zhihu.com/question/298203515/answer/2008258573281562692
        match = re.search(r"answer/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从回答 URL 提取 ID: {self.url}")

        answer_id = match.group(1)
        try:
            data = self.api_client.get_answer(answer_id)
        except Exception as e:
            raise Exception(f"回答 {answer_id} API 抓取失败: {e}")

        return build_answer_item(url=self.url, answer_id=answer_id, data=data)

    async def _extract_question(self, start: int = 0, limit: int = 3, **kwargs) -> List[dict]:
        """Backward-compatible question extractor returning only item payloads."""
        return (await self._extract_question_result(start=start, limit=limit, **kwargs))["items"]

    async def _extract_question_result(self, start: int = 0, limit: int = 3, **kwargs) -> Dict[str, Any]:
        """提取问题下的多个回答。

        利用 API 分页直接获取，支持一次获取多页回答。

        Args:
            start: 起始偏移量 (默认 0)
            limit: 获取回答数量 (默认 3)
        """
        match = re.search(r"question/(\d+)", self.url)
        if not match:
             raise Exception(f"无法从问题 URL 提取 ID: {self.url}")

        question_id = match.group(1)
        target_limit = max(1, limit)
        current_offset = max(0, start)
        page_size = 20
        humanizer = get_humanizer()

        print(f"🎯 目标: API 分页抓取问题 {question_id} 的前 {target_limit} 个回答 (从第 {current_offset} 条开始)")

        results: List[dict] = []
        page_index = 0
        reached_end = False
        stopped_early = False

        while len(results) < target_limit:
            current_page_size = min(page_size, target_limit - len(results))

            try:
                page = self.api_client.get_question_answers_page(
                    question_id,
                    limit=current_page_size,
                    offset=current_offset,
                )
            except Exception as e:
                message = f"问题 {question_id} 第 {page_index + 1} 页回答列表 API 抓取失败: {e}"
                if results:
                    print(f"⚠️ {message}")
                    print(f"🛑 为降低风险，本次提前停止，保留已抓到的 {len(results)} 个回答。")
                    stopped_early = True
                    break
                raise Exception(message)

            answers_data = page.get("data", [])
            if not answers_data:
                reached_end = True
                break

            for data in answers_data:
                results.append(build_question_answer_item(question_id=question_id, data=data))

            page_index += 1
            current_offset += len(answers_data)
            print(f"📄 第 {page_index} 页完成，本页 {len(answers_data)} 条，累计 {len(results)}/{target_limit} 条。")

            if len(results) >= target_limit:
                if page.get("paging", {}).get("is_end", len(answers_data) < current_page_size):
                    reached_end = True
                break

            if page.get("paging", {}).get("is_end", len(answers_data) < current_page_size):
                reached_end = True
                break

            if humanizer.config.enabled:
                if page_index % 3 == 0:
                    delay = uniform(15.0, 30.0)
                    print(f"⏸️ 已连续抓取 {page_index} 页，额外休息 {delay:.1f} 秒后继续...")
                else:
                    min_delay = max(3.0, humanizer.config.min_delay)
                    max_delay = max(min_delay, humanizer.config.max_delay, 8.0)
                    delay = uniform(min_delay, max_delay)
                    print(f"⏳ 等待 {delay:.1f} 秒后抓取下一页...")
                await asyncio.sleep(delay)

        print(f"✅ 成功命中 {len(results)} 个回答。")
        return {
            "items": results,
            "stats": {
                "requested_limit": target_limit,
                "saved_count": len(results),
                "pages_fetched": page_index,
                "last_offset": current_offset,
                "reached_end": reached_end,
                "stopped_early": stopped_early,
            },
        }
