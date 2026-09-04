"""
专栏批量下载 - 自动发现并下载作者所有专栏
用法: python download_all_columns.py https://www.zhihu.com/people/xxx
"""

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
OUTPUTS = ROOT / "outputs"

COOKIE = (
    "_xsrf=OZdyXzR4OKptAHauNRqPq67uC0B8CSPf; "
    "__zse_ck=005_sPw4NcmlVB2HCYED76FFywdBuFbRs=HOTRLXLc3QtN96MFdW2zA3k1lici/R5TcOdP=MuiL13dusXgPv2OSjJfwEeB5XDis25mBYcKncmY/GrgAxkGhXbdUcZ/vLL/KA-OUHfzZcfppjWjurwOlR5mgqB0pZvSWInJmOdnoCcWmIGmDB/QUXZuSlR7KaShrwV1bTv7UdGp6fC/UbI5hICjE8M69JB3HVxqk53yDq04DdUIhwp8mSM1ftgA8cfeA1/; "
    "sec_token=de7d25ca546743cef60f2d01d775374e; "
    "_zap=764044ea-0ef9-494a-b038-a724b2993d64; "
    "Hm_lvt_98beee57fd2ef70ccdd5ca52b9740c49=1775967071; "
    "HMACCOUNT=B9BF9DA0CD1AFEAC; "
    "d_c0=lnEUjmUMIByPTkkoIQekzKmMrR3jupQA9b4=|1775967070; "
    "z_c0=2|1:0|10:1775967095|4:z_c0|92:Mi4xaDRrc1JnQUFBQUNXY1JTT1pRd2dIQ1lBQUFCZ0FsVk5kbW5JYWdBSS1vRVZsYUQySTFSdkZqOWJYc21yUjY1T01n|40640757257048c13ce31747f8c39c389d0c695fd9b15b7e1c8db35ac9b60b2c; "
    "Hm_lpvt_98beee57fd2ef70ccdd5ca52b9740c49=1775967123; "
    "BEC=5ee33e0856ed13c879689106c041a08d"
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"


def safe_name(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[\\/:*?"<>|\s]+', '_', text)
    return text[:max_len].strip("_.") or "untitled"


def strip_html(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\n{3,}", "\n\n", unescape(BeautifulSoup(value, "lxml").get_text("\n"))).strip()


def ts_fmt(v):
    return datetime.fromtimestamp(v, tz=timezone.utc).astimezone().isoformat(timespec="seconds") if v else None


def build_session() -> requests.Session:
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=Retry(5, 5, 5, 1.2, [429, 500, 502, 503, 504], ["GET"]),
                                     pool_connections=1, pool_maxsize=1))
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*",
                       "Accept-Language": "zh-CN,zh;q=0.9", "Cookie": COOKIE,
                       "Referer": "https://www.zhihu.com/", "x-requested-with": "fetch", "Connection": "close"})
    return s


def extract_pid(url: str) -> str:
    m = re.search(r"zhihu\.com/people/([^/]+)", url)
    if not m:
        sys.exit(f"无法提取 person-id: {url}")
    return m.group(1)


# ── 发现专栏 ──────────────────────────────────────────────

def discover_columns(session: requests.Session, pid: str) -> list[dict]:
    cols = []
    offset = 0
    while True:
        r = session.get(f"https://www.zhihu.com/api/v4/members/{pid}/column-contributions",
                        params={"include": "column.title,column.intro,column.id,column.image_url,column.articles_count",
                                "offset": offset, "limit": 20}, timeout=30)
        r.raise_for_status()
        data = r.json()
        batch = data.get("data") or []
        if not batch:
            break
        for item in batch:
            c = item.get("column", {})
            cols.append({"id": c.get("id"), "title": c.get("title", "未命名"),
                          "intro": c.get("intro", ""), "articles_count": c.get("articles_count", 0)})
        paging = data.get("paging") or {}
        if paging.get("is_end") or not paging.get("next"):
            break
        offset = int(parse_qs(urlparse(paging["next"]).query).get("offset", [0])[0])
    return cols


# ── 下载单个专栏 ──────────────────────────────────────────

def download_column(session: requests.Session, col: dict, out: Path, pause: float) -> dict:
    col_id = col["id"]
    col_title = col["title"]
    # 用安全文件夹名
    folder = safe_name(f"{col_title}_{col_id}")
    col_dir = out / folder
    col_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  专栏: {col_title} (hint={col.get('articles_count', '?')}篇)")

    # 获取文章列表
    articles = []
    offset = 0
    while True:
        r = session.get(f"https://www.zhihu.com/api/v4/columns/{col_id}/items",
                        params={"include": "data[*].id,title,url,created,updated,excerpt,comment_count,voteup_count,content",
                                "offset": offset, "limit": 20}, timeout=40)
        r.raise_for_status()
        data = r.json()
        batch = data.get("data") or []
        if not batch:
            break
        articles.extend(batch)
        paging = data.get("paging") or {}
        if paging.get("is_end"):
            break
        nxt = paging.get("next")
        if not nxt:
            break
        offset = int(parse_qs(urlparse(nxt).query).get("offset", [0])[0])
        time.sleep(pause)

    print(f"    获取 {len(articles)} 篇文章，开始下载正文...")

    index = []
    ok, fail = 0, 0
    for idx, art in enumerate(articles, 1):
        title = art.get("title") or "无标题"
        aid = str(art.get("id", ""))
        url = art.get("url") or f"https://zhuanlan.zhihu.com/p/{aid}"
        content_html = art.get("content", "") or ""
        text = strip_html(content_html)
        fname = f"{idx:03d}_{safe_name(title)}"

        md = f"# {title}\n\n来源: {url}\n日期: {ts_fmt(art.get('created')) or ''}\n"
        if art.get("voteup_count") is not None:
            md += f"点赞: {art['voteup_count']}  评论: {art.get('comment_count', '')}\n"
        md += f"\n---\n\n{text}\n"
        (col_dir / f"{fname}.md").write_text(md, encoding="utf-8")
        (col_dir / f"{fname}.txt").write_text(f"{title}\n{'=' * len(title)}\n\n{text}\n", encoding="utf-8")

        index.append({"order": idx, "id": aid, "title": title, "url": url,
                       "created_at": ts_fmt(art.get("created")), "chars": len(text),
                       "file": f"{fname}.md"})
        ok += 1
        if idx % 20 == 0 or idx == len(articles):
            print(f"    [{idx}/{len(articles)}]")

    (col_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"    完成: {ok}篇, 失败{fail}篇 -> {col_dir}")
    return {"column_id": col_id, "title": col_title, "total": len(articles), "ok": ok, "fail": fail}


# ── 主入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="下载作者所有专栏")
    parser.add_argument("url", help="知乎作者主页链接")
    parser.add_argument("--pause", type=float, default=0.6)
    args = parser.parse_args()

    pid = extract_pid(args.url)
    out = OUTPUTS / pid / "columns"
    out.mkdir(parents=True, exist_ok=True)
    session = build_session()

    print(f"=== 发现专栏: {pid} ===")
    cols = discover_columns(session, pid)
    if not cols:
        print("该作者没有专栏。")
        return

    for c in cols:
        print(f"  - {c['title']} ({c.get('articles_count', '?')}篇)  ID: {c['id']}")
    print(f"\n共 {len(cols)} 个专栏，开始下载...\n")

    results = []
    for i, col in enumerate(cols, 1):
        print(f"[{i}/{len(cols)}] {col['title']}")
        r = download_column(session, col, out, args.pause)
        results.append(r)

    summary = {"person_id": pid, "saved_at": datetime.now().isoformat(timespec="seconds"),
                "columns": results, "total_columns": len(results),
                "total_articles": sum(r["ok"] for r in results)}
    (out / "columns_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"作者: {pid}")
    print(f"专栏: {len(results)} 个  文章: {summary['total_articles']} 篇")
    print(f"输出: {out}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
