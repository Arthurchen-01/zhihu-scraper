"""Parse supported Zhihu URLs into normalized archive targets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit


class UnsupportedZhihuUrlError(ValueError):
    """Raised when a URL is not one of the archive targets supported in phase one."""


class TargetKind(StrEnum):
    ARTICLE = "article"
    ANSWER = "answer"
    QUESTION = "question"
    COLUMN = "column"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class ZhihuTarget:
    kind: TargetKind
    content_id: str
    canonical_url: str
    question_id: str | None = None


def route_zhihu_url(raw_url: str) -> ZhihuTarget:
    """Return the supported target described by *raw_url*."""

    value = raw_url.strip()
    if not value:
        raise UnsupportedZhihuUrlError("知乎链接不能为空。")
    try:
        parsed = urlsplit(value)
    except ValueError as error:
        raise UnsupportedZhihuUrlError(f"无法解析知乎链接：{raw_url}") from error
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsupportedZhihuUrlError("请输入包含 http:// 或 https:// 的完整知乎链接。")
    host = parsed.hostname
    official_hosts = {
        "zhihu.com",
        "www.zhihu.com",
        "zhuanlan.zhihu.com",
        "www.zhuanlan.zhihu.com",
    }
    if host not in official_hosts:
        received_host = host or "缺少域名"
        raise UnsupportedZhihuUrlError(f"仅支持知乎官方域名，当前域名为 {received_host}。")
    article_match = re.fullmatch(r"/p/(\d+)/?", parsed.path)
    if host in {"zhuanlan.zhihu.com", "www.zhuanlan.zhihu.com"} and article_match:
        article_id = article_match.group(1)
        return ZhihuTarget(
            kind=TargetKind.ARTICLE,
            content_id=article_id,
            canonical_url=f"https://zhuanlan.zhihu.com/p/{article_id}",
        )
    if host in {"zhihu.com", "www.zhihu.com"}:
        full_answer_match = re.fullmatch(
            r"/question/(\d+)/answer/(\d+)/?",
            parsed.path,
        )
        if full_answer_match:
            question_id, answer_id = full_answer_match.groups()
            return ZhihuTarget(
                kind=TargetKind.ANSWER,
                content_id=answer_id,
                question_id=question_id,
                canonical_url=(f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}"),
            )
        short_answer_match = re.fullmatch(r"/answer/(\d+)/?", parsed.path)
        if short_answer_match:
            answer_id = short_answer_match.group(1)
            return ZhihuTarget(
                kind=TargetKind.ANSWER,
                content_id=answer_id,
                canonical_url=f"https://www.zhihu.com/answer/{answer_id}",
            )
        question_match = re.fullmatch(r"/question/(\d+)/?", parsed.path)
        if question_match:
            question_id = question_match.group(1)
            return ZhihuTarget(
                kind=TargetKind.QUESTION,
                content_id=question_id,
                question_id=question_id,
                canonical_url=f"https://www.zhihu.com/question/{question_id}",
            )
        column_match = re.fullmatch(
            r"/column/([A-Za-z0-9_-]+)/?",
            parsed.path,
        )
        if column_match:
            column_token = column_match.group(1)
            return ZhihuTarget(
                kind=TargetKind.COLUMN,
                content_id=column_token,
                canonical_url=f"https://www.zhihu.com/column/{column_token}",
            )
        video_match = re.fullmatch(r"/zvideo/(\d+)/?", parsed.path)
        if video_match:
            video_id = video_match.group(1)
            return ZhihuTarget(
                kind=TargetKind.VIDEO,
                content_id=video_id,
                canonical_url=f"https://www.zhihu.com/zvideo/{video_id}",
            )
        unsupported_sections = (
            ("/people/", "作者主页"),
            ("/collection/", "收藏夹"),
            ("/search", "搜索结果"),
            ("/pin/", "想法"),
            ("/market/", "盐选内容"),
            ("/xen/market/", "盐选内容"),
            ("/vip/", "盐选内容"),
            ("/salt/", "盐选内容"),
        )
        for prefix, label in unsupported_sections:
            if parsed.path.startswith(prefix):
                raise UnsupportedZhihuUrlError(f"{label}暂不支持：{raw_url}")
    raise UnsupportedZhihuUrlError(
        f"当前阶段仅支持知乎文章、回答、问题、专栏和独立视频链接：{raw_url}"
    )
