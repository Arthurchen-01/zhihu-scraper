from __future__ import annotations

"""
知乎作者全量归档 - 一键脚本
用法: python archive_author.py https://www.zhihu.com/people/shan-chang-qing-yi
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

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
)


# ── 工具函数 ──────────────────────────────────────────────

def safe_name(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[\\/:*?"<>|。\s]+', '_', text)
    text = text.strip("_.")
    return text[:max_len] if len(text) > max_len else text or "untitled"


def strip_html(value: str) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "lxml")
    text = unescape(soup.get_text("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def ts_fmt(value) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=5, connect=5, read=5, backoff_factor=1.2,
                    status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    s.mount("https://", HTTPAdapter(max_retries=retries, pool_connections=1, pool_maxsize=1))
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cookie": COOKIE,
        "Referer": "https://www.zhihu.com/",
        "x-requested-with": "fetch",
        "Connection": "close",
    })
    return s


def extract_person_id(url: str) -> str:
    m = re.search(r"zhihu\.com/people/([^/]+)", url)
    if not m:
        sys.exit(f"无法从链接提取 person-id: {url}")
    return m.group(1)


# ── 抓目录 ────────────────────────────────────────────────

def fetch_list(session: requests.Session, person_id: str, content_type: str) -> list[dict]:
    """通用列表抓取，返回 items"""
    if content_type == "articles":
        api_url = f"https://www.zhihu.com/api/v4/members/{person_id}/articles"
        include = "data[*].id,title,content,created,updated,excerpt,comment_count,voteup_count,url"
    elif content_type == "answers":
        api_url = f"https://www.zhihu.com/api/v4/members/{person_id}/answers"
        include = "data[*].id,excerpt,excerpt_new,created,updated,url,question.id,question.title,comment_count,voteup_count"
    elif content_type == "pins":
        api_url = f"https://www.zhihu.com/api/v4/members/{person_id}/pins"
        include = "data[*].id,content,created,updated,url,comment_count,like_count,repost_count,excerpt,title"
    else:
        return []

    items = []
    offset = 0
    page = 0
    seen = set()
    while True:
        page += 1
        params = {"include": include, "offset": offset, "limit": 20}
        r = session.get(api_url, params=params, timeout=40)
        r.raise_for_status()
        data = r.json()
        batch = data.get("data") or []
        if not batch:
            break
        for item in batch:
            iid = str(item.get("id", ""))
            if iid and iid not in seen:
                seen.add(iid)
                items.append(item)
        paging = data.get("paging") or {}
        hint = paging.get("totals", "?")
        print(f"  [{content_type}] page={page} batch={len(batch)} total={len(items)} hint={hint}")
        if paging.get("is_end"):
            break
        nxt = paging.get("next")
        if not nxt:
            break
        offset = int(parse_qs(urlparse(nxt).query).get("offset", [0])[0])
        time.sleep(0.5)
    return items


# ── 保存 ──────────────────────────────────────────────────

def save_item(item: dict, idx: int, total: int, content_type: str, out: Path) -> dict:
    title = item.get("title") or item.get("question_title") or f"{content_type}_{item.get('id')}"
    iid = str(item.get("id", ""))
    url = item.get("url", "") or ""
    if url.startswith("/"):
        url = f"https://www.zhihu.com{url}"
    elif "/api/v4/" in url:
        url = f"https://www.zhihu.com/answer/{iid}" if content_type == "answers" else f"https://zhuanlan.zhihu.com/p/{iid}"

    raw = item.get("_content", "")
    text = strip_html(raw)
    fname = f"{idx:04d}_{safe_name(title)}"

    md = f"# {title}\n\n来源: {url}\n日期: {item.get('created_at', '') or ts_fmt(item.get('created')) or ''}\n"
    if item.get("voteup_count") is not None:
        md += f"点赞: {item['voteup_count']}  评论: {item.get('comment_count', '')}\n"
    if item.get("question_title"):
        md += f"问题: {item['question_title']}\n"
    md += f"\n---\n\n{text}\n"
    (out / f"{fname}.md").write_text(md, encoding="utf-8")
    (out / f"{fname}.txt").write_text(f"{title}\n{'=' * len(title)}\n\n{text}\n", encoding="utf-8")

    return {"order": idx, "id": iid, "title": title, "url": url, "chars": len(text)}


def discover_columns(session, pid):
    cols = []
    offset = 0
    while True:
        r = session.get(f"https://www.zhihu.com/api/v4/members/{pid}/column-contributions",
                        params={"include": "column.title,column.intro,column.id,column.articles_count",
                                "offset": offset, "limit": 20}, timeout=30)
        r.raise_for_status()
        data = r.json()
        batch = data.get("data") or []
        if not batch:
            break
        for item in batch:
            c = item.get("column", {})
            cols.append({"id": c.get("id"), "title": c.get("title", ""),
                          "articles_count": c.get("articles_count", 0)})
        paging = data.get("paging") or {}
        if paging.get("is_end") or not paging.get("next"):
            break
        offset = int(parse_qs(urlparse(paging["next"]).query).get("offset", [0])[0])
    return cols


def download_one_column(session, col, out, pause):
    col_id = col["id"]
    col_title = col["title"]
    folder = safe_name(f"{col_title}_{col_id}")
    col_dir = out / folder
    col_dir.mkdir(parents=True, exist_ok=True)

    articles = []
    offset = 0
    while True:
        r = session.get(f"https://www.zhihu.com/api/v4/columns/{col_id}/items",
                        params={"include": "data[*].id,title,url,created,updated,comment_count,voteup_count,content",
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

    index = []
    for idx, art in enumerate(articles, 1):
        title = art.get("title") or "无标题"
        aid = str(art.get("id", ""))
        url = art.get("url") or f"https://zhuanlan.zhihu.com/p/{aid}"
        text = strip_html(art.get("content", "") or "")
        fname = f"{idx:03d}_{safe_name(title)}"
        md = f"# {title}\n\n来源: {url}\n日期: {ts_fmt(art.get('created')) or ''}\n"
        if art.get("voteup_count") is not None:
            md += f"点赞: {art['voteup_count']}  评论: {art.get('comment_count', '')}\n"
        md += f"\n---\n\n{text}\n"
        (col_dir / f"{fname}.md").write_text(md, encoding="utf-8")
        (col_dir / f"{fname}.txt").write_text(f"{title}\n{'=' * len(title)}\n\n{text}\n", encoding="utf-8")
        index.append({"order": idx, "id": aid, "title": title, "url": url, "chars": len(text), "file": f"{fname}.md"})

    (col_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(articles)


# ── 主流程 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="知乎作者全量归档")
    parser.add_argument("url", help="知乎作者主页链接，如 https://www.zhihu.com/people/xxx")
    parser.add_argument("--skip-content", action="store_true", help="只抓目录，不下载正文")
    parser.add_argument("--pause", type=float, default=0.8, help="请求间隔秒数")
    args = parser.parse_args()

    pid = extract_person_id(args.url)
    base = OUTPUTS / pid
    session = build_session()
    now = datetime.now().strftime("%Y%m%d_%H%M")

    print(f"=== 归档作者: {pid} ===\n")

    for ctype, label in [("articles", "文章"), ("answers", "回答"), ("pins", "想法")]:
        print(f"--- 抓取{label}目录 ---")
        items = fetch_list(session, pid, ctype)

        # 保存索引
        idx_dir = base / ctype
        idx_dir.mkdir(parents=True, exist_ok=True)

        ordered = sorted(items, key=lambda x: ((x.get("created") or 0), str(x.get("id", ""))))

        # 统一 URL 格式
        for it in ordered:
            u = it.get("url", "") or ""
            if u.startswith("/"):
                it["url"] = f"https://www.zhihu.com{u}"
            elif "/api/v4/" in u:
                it["url"] = f"https://www.zhihu.com/answer/{it.get('id')}" if ctype == "answers" else f"https://zhuanlan.zhihu.com/p/{it.get('id')}"

        json_path = idx_dir / f"{ctype}_index.json"
        txt_path = idx_dir / f"{ctype}_links.txt"
        json_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
        txt_path.write_text("\n".join(it.get("url", "") for it in ordered if it.get("url")), encoding="utf-8")
        print(f"  索引: {len(ordered)} 条 -> {json_path}\n")

        # 下载正文
        if not args.skip_content:
            content_dir = base / "content" / ctype
            content_dir.mkdir(parents=True, exist_ok=True)
            print(f"--- 下载{label}正文 ({len(ordered)} 条) ---")
            ok, fail = 0, 0
            for idx, it in enumerate(ordered, 1):
                iid = str(it.get("id", ""))
                title = it.get("title") or it.get("question_title") or f"{ctype}_{iid}"
                try:
                    if ctype == "articles":
                        it["_content"] = it.get("content", "") or ""
                    elif ctype == "answers":
                        r = session.get(f"https://www.zhihu.com/api/v4/answers/{iid}", params={"include": "content"}, timeout=40)
                        r.raise_for_status()
                        it["_content"] = r.json().get("content", "") or ""
                    elif ctype == "pins":
                        raw = it.get("content", "") or ""
                        if isinstance(raw, list):
                            parts = [seg.get("content", "") or seg.get("text", "") if isinstance(seg, dict) else str(seg) for seg in raw]
                            it["_content"] = "".join(parts)
                        else:
                            it["_content"] = str(raw)

                    save_item(it, idx, len(ordered), ctype, content_dir)
                    ok += 1
                    if idx % 50 == 0 or idx == len(ordered):
                        print(f"  [{idx}/{len(ordered)}] 已完成")
                except Exception as e:
                    fail += 1
                    print(f"  [{idx}/{len(ordered)}] FAIL {title}: {e}")
                if ctype != "articles":
                    time.sleep(args.pause)

            summary = {"type": ctype, "person_id": pid, "total": len(ordered), "ok": ok, "fail": fail,
                       "saved_at": datetime.now().isoformat(timespec="seconds")}
            (content_dir / "download_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  完成: {ok} 成功, {fail} 失败\n")

    # 汇总
    total_summary = {
        "person_id": pid, "url": args.url,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "articles": len(json.loads((base / "articles" / "articles_index.json").read_text(encoding="utf-8"))),
        "answers": len(json.loads((base / "answers" / "answers_index.json").read_text(encoding="utf-8"))),
        "pins": len(json.loads((base / "pins" / "pins_index.json").read_text(encoding="utf-8"))),
    }

    # 专栏
    if not args.skip_content:
        print(f"\n--- 发现并下载专栏 ---")
        cols = discover_columns(session, pid)
        if cols:
            col_out = base / "columns"
            col_out.mkdir(parents=True, exist_ok=True)
            total_col_articles = 0
            for i, col in enumerate(cols, 1):
                print(f"  [{i}/{len(cols)}] {col['title']}")
                n = download_one_column(session, col, col_out, args.pause)
                total_col_articles += n
            total_summary["columns"] = len(cols)
            total_summary["column_articles"] = total_col_articles
            print(f"  专栏完成: {len(cols)}个, {total_col_articles}篇")
        else:
            total_summary["columns"] = 0
            print("  该作者无专栏")
    (base / "summary.json").write_text(json.dumps(total_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 50)
    print(f"作者: {pid}")
    print(f"文章: {total_summary['articles']}  回答: {total_summary['answers']}  想法: {total_summary['pins']}")
    if total_summary.get("columns"):
        print(f"专栏: {total_summary['columns']} 个 ({total_summary.get('column_articles', 0)} 篇)")
    print(f"输出: {base}")
    print("=" * 50)


if __name__ == "__main__":
    main()
