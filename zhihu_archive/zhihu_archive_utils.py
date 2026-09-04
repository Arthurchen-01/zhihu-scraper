from __future__ import annotations

import json
import os
import re
from datetime import datetime
from html import unescape
from pathlib import Path

from zhihu_oauth import ZhihuClient

TOKEN_FILE = "token.pkl"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_name(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', '_', value)
    value = value.strip().strip('.')
    return value or 'untitled'


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_client(root: Path, login_if_needed: bool = False) -> ZhihuClient:
    client = ZhihuClient()
    token_path = root / TOKEN_FILE
    if token_path.exists():
        client.load_token(token_path)
    elif login_if_needed:
        client.login_in_terminal()
        client.save_token(token_path)
    return client


def article_payload(article: object) -> dict[str, object]:
    column = getattr(article, 'column', None)
    author = getattr(article, 'author', None)
    content_html = getattr(article, 'content', '')
    return {
        "id": getattr(article, 'id', None),
        "title": getattr(article, 'title', None),
        "excerpt": getattr(article, 'excerpt', None),
        "voteup_count": getattr(article, 'voteup_count', None),
        "comment_count": getattr(article, 'comment_count', None),
        "updated_time": getattr(article, 'updated_time', None),
        "author_id": getattr(author, 'id', None) if author else None,
        "author_name": getattr(author, 'name', None) if author else None,
        "column_id": getattr(column, 'id', None) if column else None,
        "column_title": getattr(column, 'title', None) if column else None,
        "content_html": content_html,
        "content_text": strip_html(content_html),
        "url": f"https://zhuanlan.zhihu.com/p/{getattr(article, 'id', '')}" if getattr(article, 'id', None) else None,
        "archived_at": iso_now(),
    }


def column_payload(column: object) -> dict[str, object]:
    author = getattr(column, 'author', None)
    return {
        "id": getattr(column, 'id', None),
        "title": getattr(column, 'title', None),
        "description": getattr(column, 'description', None),
        "article_count": getattr(column, 'article_count', None),
        "follower_count": getattr(column, 'follower_count', None),
        "updated_time": getattr(column, 'updated_time', None),
        "author_id": getattr(author, 'id', None) if author else None,
        "author_name": getattr(author, 'name', None) if author else None,
        "archived_at": iso_now(),
    }
