"""Map Zhihu payloads into stable domain objects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .content import parse_rich_text
from .domain import Article, Author, ColumnRef


class NormalizationError(ValueError):
    """A source payload is missing identity required by the archive."""


def normalize_article(
    payload: Mapping[str, Any],
    *,
    source_url: str | None = None,
) -> Article:
    """Normalize either an article API item or extracted page state."""

    article_id = _required_identifier(payload.get("id"), label="article id")
    canonical_url = source_url or f"https://zhuanlan.zhihu.com/p/{article_id}"
    title = _required_text(payload.get("title"), label="article title")
    raw_content = payload.get("content")
    content = raw_content if isinstance(raw_content, str) else ""

    return Article(
        id=article_id,
        title=title,
        source_url=canonical_url,
        author=_normalize_author(payload.get("author")),
        published_at=_utc_datetime(
            payload.get("created")
            or payload.get("created_time")
            or payload.get("created_at")
        ),
        updated_at=_utc_datetime(
            payload.get("updated")
            or payload.get("updated_time")
            or payload.get("updated_at")
        ),
        blocks=parse_rich_text(content, base_url=canonical_url),
        voteup_count=_nonnegative_int(
            payload.get("voteup_count") or payload.get("vote_count")
        ),
        cover_url=_optional_text(
            payload.get("image_url")
            or payload.get("title_image")
            or payload.get("cover_url")
        ),
        columns=_normalize_columns(payload),
        comments=None,
    )


def _normalize_author(value: object) -> Author:
    payload = value if isinstance(value, Mapping) else {}
    identifier = _optional_text(payload.get("id"))
    name = (
        _optional_text(payload.get("name"))
        or _optional_text(payload.get("headline"))
        or "匿名用户"
    )
    url_token = _optional_text(payload.get("url_token"))
    raw_url = _optional_text(payload.get("url"))
    url: str | None = None
    if url_token:
        url = f"https://www.zhihu.com/people/{url_token}"
    elif raw_url:
        url = (
            f"https://www.zhihu.com{raw_url}"
            if raw_url.startswith("/")
            else raw_url
        )
    return Author(id=identifier, name=name, url=url)


def _normalize_columns(payload: Mapping[str, Any]) -> tuple[ColumnRef, ...]:
    candidates: list[object] = []
    if payload.get("column") is not None:
        candidates.append(payload["column"])
    for key in ("contributions", "columns"):
        value = payload.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            candidates.extend(value)

    columns: list[ColumnRef] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        token = (
            _optional_text(candidate.get("id"))
            or _optional_text(candidate.get("slug"))
            or _column_token_from_url(_optional_text(candidate.get("url")))
        )
        if not token or token in seen:
            continue
        seen.add(token)
        columns.append(
            ColumnRef(
                token=token,
                title=_optional_text(candidate.get("title")) or token,
                url=(
                    _optional_text(candidate.get("url"))
                    or f"https://www.zhihu.com/column/{token}"
                ),
            )
        )
    return tuple(columns)


def _column_token_from_url(url: str | None) -> str | None:
    if not url:
        return None
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[-2] == "column":
        return path_parts[-1]
    return None


def _utc_datetime(value: object) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return datetime.fromtimestamp(int(stripped), tz=timezone.utc)
        try:
            parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
        except ValueError:
            return None
        return (
            parsed.replace(tzinfo=timezone.utc)
            if parsed.tzinfo is None
            else parsed.astimezone(timezone.utc)
        )
    return None


def _required_identifier(value: object, *, label: str) -> str:
    identifier = _optional_text(value)
    if not identifier:
        raise NormalizationError(f"missing {label}")
    return identifier


def _required_text(value: object, *, label: str) -> str:
    text = _optional_text(value)
    if not text:
        raise NormalizationError(f"missing {label}")
    return text


def _optional_text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
