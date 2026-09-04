from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_name(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[\\/:*?"<>|。\s]+', '_', text)
    text = text.strip("_.")
    if len(text) > max_len:
        text = text[:max_len]
    return text or "untitled"


def strip_html(value: str) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "lxml")
    text = soup.get_text("\n")
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_ts(value: int | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def build_session(cookie: str) -> requests.Session:
    session = requests.Session()
    retries = Retry(total=5, connect=5, read=5, backoff_factor=1.2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=1, pool_maxsize=1)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cookie": cookie.strip(),
            "Referer": "https://www.zhihu.com/",
            "x-requested-with": "fetch",
            "Connection": "close",
        }
    )
    return session


# ── 文章批量获取（列表 API 含 content）─────────────────────

def fetch_articles_with_content(session: requests.Session, person_id: str, pause: float) -> list[dict]:
    """Fetch ALL articles from list API with content included."""
    url = f"https://www.zhihu.com/api/v4/members/{person_id}/articles"
    articles = []
    offset = 0
    page_no = 0

    while True:
        page_no += 1
        params = {
            "include": "data[*].id,title,content,created,updated,excerpt,comment_count,voteup_count,url",
            "offset": offset,
            "limit": 20,
        }
        r = session.get(url, params=params, timeout=40)
        r.raise_for_status()
        data = r.json()
        items = data.get("data") or []
        if not items:
            break
        for item in items:
            articles.append(item)
        paging = data.get("paging") or {}
        print(f"  batch={page_no} fetched={len(items)} total={len(articles)} hint={paging.get('totals')}")
        if paging.get("is_end"):
            break
        next_url = paging.get("next")
        if not next_url:
            break
        offset = int(parse_qs(urlparse(next_url).query).get("offset", [0])[0])
        if pause > 0:
            time.sleep(pause)

    return articles


# ── 回答/想法单条获取 ─────────────────────────────────────

def fetch_answer_content(session: requests.Session, answer_id: str) -> str:
    url = f"https://www.zhihu.com/api/v4/answers/{answer_id}"
    params = {"include": "content"}
    r = session.get(url, params=params, timeout=40)
    r.raise_for_status()
    return r.json().get("content", "") or ""


def fetch_pin_content_from_list(item: dict) -> str:
    """Extract content from pin list data (content is already in the index)."""
    raw = item.get("content", "") or ""
    if isinstance(raw, list):
        parts = []
        for seg in raw:
            if isinstance(seg, dict):
                parts.append(seg.get("content", "") or seg.get("text", "") or "")
            elif isinstance(seg, str):
                parts.append(seg)
        return "".join(parts)
    return str(raw)


# ── 保存单条内容 ──────────────────────────────────────────

def save_item(item: dict, idx: int, total: int, content_type: str, output_root: Path) -> dict | None:
    title = item.get("title") or item.get("question_title") or f"{content_type}_{item.get('id', 'unknown')}"
    item_id = str(item.get("id", ""))
    url = item.get("url", "") or ""
    if url.startswith("/"):
        url = f"https://www.zhihu.com{url}"
    elif "/api/v4/" in url:
        if content_type == "answers":
            url = f"https://www.zhihu.com/answer/{item_id}"
        elif content_type == "articles":
            url = f"https://zhuanlan.zhihu.com/p/{item_id}"

    raw_html = item.get("_content", "")
    content_text = strip_html(raw_html)
    fname = f"{idx:04d}_{safe_name(title)}"

    # Markdown
    md_lines = [f"# {title}\n", f"来源: {url}\n", f"日期: {item.get('created_at', '') or format_ts(item.get('created')) or ''}\n"]
    if item.get("voteup_count") is not None:
        md_lines.append(f"点赞: {item.get('voteup_count', '')}  评论: {item.get('comment_count', '')}\n")
    if item.get("question_title"):
        md_lines.append(f"问题: {item.get('question_title', '')}\n")
    md_lines.append(f"\n---\n\n{content_text}\n")
    (output_root / f"{fname}.md").write_text("\n".join(md_lines), encoding="utf-8")

    # Plain text
    txt_text = f"{title}\n{'=' * len(title)}\n\n{content_text}\n"
    (output_root / f"{fname}.txt").write_text(txt_text, encoding="utf-8")

    return {
        "order": idx, "id": item_id, "title": title, "url": url,
        "created_at": item.get("created_at") or format_ts(item.get("created")),
        "file_md": f"{fname}.md", "file_txt": f"{fname}.txt", "chars": len(content_text),
    }


# ── 主流程：文章 ──────────────────────────────────────────

def download_articles(session: requests.Session, person_id: str, output_root: Path, pause: float, limit: int) -> list[dict]:
    ensure_dir(output_root)
    print("Fetching articles with content via list API...")
    articles = fetch_articles_with_content(session, person_id, pause)
    if limit > 0:
        articles = articles[:limit]
    total = len(articles)
    print(f"Got {total} articles. Saving...")

    index = []
    for idx, item in enumerate(articles, 1):
        try:
            item["_content"] = item.get("content", "") or ""
            entry = save_item(item, idx, total, "articles", output_root)
            if entry:
                index.append(entry)
                print(f"[{idx}/{total}] OK {item.get('title', '')} ({entry['chars']} chars)")
        except Exception as exc:
            print(f"[{idx}/{total}] FAIL {item.get('title', '')} - {exc}")
            index.append({"order": idx, "id": str(item.get("id", "")), "title": item.get("title", ""), "error": str(exc)})

    return index


# ── 主流程：回答 ──────────────────────────────────────────

def download_answers(session: requests.Session, items: list[dict], output_root: Path, pause: float, limit: int) -> list[dict]:
    ensure_dir(output_root)
    if limit > 0:
        items = items[:limit]
    total = len(items)
    print(f"Downloading {total} answers...")

    index = []
    for idx, item in enumerate(items, 1):
        item_id = str(item.get("id", ""))
        title = item.get("question_title", "") or f"answer_{item_id}"
        try:
            content_html = fetch_answer_content(session, item_id)
            item["_content"] = content_html
            entry = save_item(item, idx, total, "answers", output_root)
            if entry:
                index.append(entry)
                print(f"[{idx}/{total}] OK {title} ({entry['chars']} chars)")
        except Exception as exc:
            print(f"[{idx}/{total}] FAIL {title} - {exc}")
            index.append({"order": idx, "id": item_id, "title": title, "error": str(exc)})
        if pause > 0:
            time.sleep(pause)

    return index


# ── 主流程：想法 ──────────────────────────────────────────

def download_pins(items: list[dict], output_root: Path, limit: int) -> list[dict]:
    ensure_dir(output_root)
    if limit > 0:
        items = items[:limit]
    total = len(items)
    print(f"Processing {total} pins (content from index)...")

    index = []
    for idx, item in enumerate(items, 1):
        item_id = str(item.get("id", ""))
        try:
            item["_content"] = fetch_pin_content_from_list(item)
            entry = save_item(item, idx, total, "pins", output_root)
            if entry:
                index.append(entry)
                print(f"[{idx}/{total}] OK pin_{item_id} ({entry['chars']} chars)")
        except Exception as exc:
            print(f"[{idx}/{total}] FAIL pin_{item_id} - {exc}")
            index.append({"order": idx, "id": item_id, "error": str(exc)})

    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Zhihu content (articles/answers/pins) as md+txt.")
    parser.add_argument("--type", required=True, choices=["articles", "answers", "pins"])
    parser.add_argument("--person-id", required=True, help="Zhihu person id")
    parser.add_argument("--index-file", help="Path to *_index.json (needed for answers/pins)")
    parser.add_argument("--cookie", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--pause", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=0, help="Max items (0=all)")
    args = parser.parse_args()

    session = build_session(args.cookie)

    if args.type == "articles":
        output_root = Path(args.output_dir) if args.output_dir else ROOT / "outputs" / args.person_id / "content" / "articles"
        index = download_articles(session, args.person_id, output_root, args.pause, args.limit)

    elif args.type in ("answers", "pins"):
        if not args.index_file:
            print(f"--index-file is required for {args.type}")
            return 1
        index_path = Path(args.index_file)
        items = json.loads(index_path.read_text(encoding="utf-8"))
        output_root = Path(args.output_dir) if args.output_dir else index_path.parent / "content"

        if args.type == "answers":
            index = download_answers(session, items, output_root, args.pause, args.limit)
        else:
            index = download_pins(items, output_root, args.limit)
    else:
        print(f"Unknown type: {args.type}")
        return 1

    # Summary
    summary = {
        "type": args.type, "person_id": args.person_id,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(index),
        "success": sum(1 for i in index if not i.get("error")),
        "failed": sum(1 for i in index if i.get("error")),
    }
    (output_root / "download_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n=== Done ===")
    print(f"Total: {summary['total']}, OK: {summary['success']}, FAIL: {summary['failed']}")
    print(f"Output: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
