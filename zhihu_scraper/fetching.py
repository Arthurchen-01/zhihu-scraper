"""Public fetching primitives re-exported from existing core modules."""

from core.api_client import ZhihuAPIClient
from core.browser_fallback import extract_zhuanlan_html
from core.scraper import ZhihuDownloader
from core.scraper_payloads import (
    build_answer_item,
    build_article_item,
    build_question_answer_item,
    format_zhihu_date,
)
from core.utils import detect_url_type, extract_id_from_url, extract_urls

__all__ = [
    "ZhihuAPIClient",
    "ZhihuDownloader",
    "build_answer_item",
    "build_article_item",
    "build_question_answer_item",
    "detect_url_type",
    "extract_id_from_url",
    "extract_urls",
    "extract_zhuanlan_html",
    "format_zhihu_date",
]
