"""Public fetching primitives re-exported from existing core modules."""

from core.api_client import ZhihuAPIClient
from core.browser_fallback import extract_zhuanlan_html
from core.scraper import ZhihuCreatorDownloader, ZhihuDownloader
from core.scraper_payloads import (
    build_answer_item,
    build_article_item,
    build_creator_answer_item,
    build_creator_article_item,
    build_creator_profile_payload,
    build_empty_sync_stats,
    build_question_answer_item,
    format_zhihu_date,
)
from core.utils import detect_url_type, extract_creator_token, extract_id_from_url, extract_urls

__all__ = [
    "ZhihuAPIClient",
    "ZhihuCreatorDownloader",
    "ZhihuDownloader",
    "build_answer_item",
    "build_article_item",
    "build_creator_answer_item",
    "build_creator_article_item",
    "build_creator_profile_payload",
    "build_empty_sync_stats",
    "build_question_answer_item",
    "detect_url_type",
    "extract_creator_token",
    "extract_id_from_url",
    "extract_urls",
    "extract_zhuanlan_html",
    "format_zhihu_date",
]
