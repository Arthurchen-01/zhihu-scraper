"""
知乎专栏文章批量下载（API + Cookie 方案）

用法:
  python download_column.py --column-url https://www.zhihu.com/column/c_1993097680050747067 --cookie "你的cookie"

输出:
  outputs/column_<slug>/
    ├── 01_文章标题.md
    ├── 01_文章标题.txt
    ├── ...
    └── index.json
"""

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
from bs4 import BeautifulSoup

# Windows 终端 UTF-8
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_name(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|。\s]+', '_', text)
    text = text.strip('_').strip('.')
    return text or 'untitled'


def strip_html(value: str) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, 'lxml')
    text = soup.get_text("\n")
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_ts(value: int | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def build_session(cookie: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": cookie.strip(),
        "Referer": "https://www.zhihu.com/",
        "x-requested-with": "fetch",
    })
    return s


# ── 专栏文章列表 ──────────────────────────────────────────────

def fetch_column_articles(session: requests.Session, column_id: str, limit: int = 20) -> list[dict]:
    articles = []
    offset = 0
    url = f"https://www.zhihu.com/api/v4/columns/{column_id}/items"

    while True:
        params = {
            "include": "data[*].id,title,url,created,updated,excerpt,comment_count,voteup_count,author.name",
            "offset": offset,
            "limit": limit,
        }
        r = session.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        items = data.get("data", [])
        if not items:
            break

        for item in items:
            articles.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "url": item.get("url") or f"https://zhuanlan.zhihu.com/p/{item.get('id')}",
                "excerpt": item.get("excerpt"),
                "created_at": format_ts(item.get("created")),
                "voteup_count": item.get("voteup_count"),
                "comment_count": item.get("comment_count"),
            })

        print(f"  获取了 {len(items)} 篇，累计 {len(articles)} 篇")

        paging = data.get("paging", {})
        if paging.get("is_end"):
            break
        next_url = paging.get("next")
        if not next_url:
            break
        offset = parse_qs(urlparse(next_url).query).get("offset", [None])[0]
        if offset is None:
            break
        offset = int(offset)
        time.sleep(0.5)

    return articles


# ── 单篇文章正文（直接抓页面解析） ────────────────────────────

def fetch_article_content(session: requests.Session, url: str) -> str:
    """直接请求文章页面，从 HTML 中提取正文。"""
    r = session.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'lxml')

    # 知乎文章正文容器
    content_div = (
        soup.find('div', class_='RichText')
        or soup.find('div', attrs={'data-za-detail-view-element': 'RichText'})
        or soup.find('article')
    )
    if content_div:
        return str(content_div)

    # 兜底: 找 Post-RichTextContainer
    content_div = soup.find('div', class_=re.compile(r'RichText|Post-RichText'))
    if content_div:
        return str(content_div)

    return ""


# ── 主流程 ────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="知乎专栏文章批量下载")
    parser.add_argument("--column-url", required=True, help="专栏 URL")
    parser.add_argument("--cookie", required=True, help="知乎 Cookie")
    parser.add_argument("--output", default=None, help="输出目录")
    parser.add_argument("--pause", type=float, default=0.8, help="请求间隔秒数")
    args = parser.parse_args()

    m = re.search(r'/column/(\w+)', args.column_url)
    if not m:
        print(f"错误: 无法从 URL 提取专栏 ID: {args.column_url}")
        return 1
    column_id = m.group(1)

    output_root = Path(args.output) if args.output else ROOT / "outputs" / f"column_{column_id}"
    ensure_dir(output_root)

    session = build_session(args.cookie)

    # 1. 获取文章列表
    print(f"=== 获取专栏文章列表: {column_id} ===")
    articles = fetch_column_articles(session, column_id)
    print(f"\n共 {len(articles)} 篇文章\n")

    if not articles:
        print("未获取到文章。请检查 cookie 和专栏 URL。")
        return 1

    # 2. 逐篇下载正文
    print("=== 下载文章正文 ===")
    index = []

    for idx, art in enumerate(articles, 1):
        try:
            content_html = fetch_article_content(session, art["url"])
            content_text = strip_html(content_html)
            title = art.get("title") or "无标题"

            fname = f"{idx:02d}_{safe_name(title)}"

            # Markdown
            md = (
                f"# {title}\n\n"
                f"来源: {art['url']}\n"
                f"日期: {art.get('created_at', '')}\n"
                f"点赞: {art.get('voteup_count', '')}  评论: {art.get('comment_count', '')}\n\n"
                f"---\n\n"
                f"{content_text}\n"
            )
            (output_root / f"{fname}.md").write_text(md, encoding="utf-8")

            # 纯文本
            txt = f"{title}\n{'=' * len(title)}\n\n{content_text}\n"
            (output_root / f"{fname}.txt").write_text(txt, encoding="utf-8")

            index.append({
                "order": idx,
                "id": art["id"],
                "title": title,
                "url": art["url"],
                "created_at": art.get("created_at"),
                "file_md": f"{fname}.md",
                "file_txt": f"{fname}.txt",
            })
            print(f"[{idx}/{len(articles)}] OK {title}")

        except Exception as exc:
            index.append({"order": idx, "id": art.get("id"), "title": art.get("title"), "error": str(exc)})
            print(f"[{idx}/{len(articles)}] FAIL {art.get('title')} - {exc}")

        time.sleep(args.pause)

    # 3. 写索引
    index_path = output_root / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    saved = sum(1 for i in index if not i.get("error"))
    print(f"\n=== 完成 ===")
    print(f"共 {len(articles)} 篇，成功 {saved} 篇")
    print(f"输出: {output_root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
