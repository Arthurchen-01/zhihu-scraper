"""Zhihu Self-Service Web Application.
Provides interactive URL inspection, author/column drill-down, checklist selection,
real-time SSE progress bar, full-text download, comment scraping, Playwright screenshotting,
password authentication (guanjun2026), dynamic/pins filtering, and EPUB/ZIP dual export.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from ..client import ZhihuClient, safe_name
from ..scrapers.author import AuthorScraper
from ..scrapers.column import ColumnScraper
from ..scrapers.article import ArticleScraper
from ..scrapers.answer import AnswerScraper
from ..scrapers.pin import PinScraper
from ..scrapers.comment import CommentScraper
from ..visual.screenshot import VisualArchiver
from ..epub_builder import ZhihuEpubBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zhihu_scraper.web")

# Password Gate Configuration
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "guanjun2026")
AUTH_TOKEN = hashlib.sha256(f"{SITE_PASSWORD}:zhihu_secure_2026".encode()).hexdigest()

app = FastAPI(title="Zhihu Investigator & Scraper Web App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # Allow public endpoints
    if (
        path in [
            "/",
            "/api/auth/login",
            "/api/auth/status",
            "/download/taiji.zip",
            "/favicon.ico",
            "/manifest.json",
        ]
        or path.startswith("/static/")
    ):
        return await call_next(request)

    # Check authentication token in cookie or headers
    token = request.cookies.get("site_auth_token") or request.headers.get("X-Auth-Token")
    if token != AUTH_TOKEN:
        return Response(
            content=json.dumps({"detail": "系统需要访问密码，请先验证密码"}, ensure_ascii=False),
            status_code=401,
            media_type="application/json"
        )
    return await call_next(request)


STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory store for background scraping jobs
JOBS: Dict[str, Dict[str, Any]] = {}


class LoginRequest(BaseModel):
    password: str


class InspectRequest(BaseModel):
    url: str
    cookie: Optional[str] = ""
    max_items: Optional[int] = 0  # 0 or None means unlimited / all articles


class BatchScrapeRequest(BaseModel):
    cookie: Optional[str] = ""
    items: List[Dict[str, Any]]
    options: Optional[Dict[str, Any]] = {
        "save_markdown": True,
        "save_comments": True,
        "save_screenshot": True,
        "highlight_keywords": []
    }


@app.post("/api/auth/login")
def auth_login(req: LoginRequest, response: Response):
    """Authenticate user with master password and set secure session cookie."""
    if req.password.strip() == SITE_PASSWORD:
        response.set_cookie(
            key="site_auth_token",
            value=AUTH_TOKEN,
            httponly=False,
            max_age=30 * 86400,
            samesite="lax",
            path="/"
        )
        return {"ok": True, "token": AUTH_TOKEN, "message": "认证成功"}
    raise HTTPException(status_code=401, detail="密码错误，请重新输入")


@app.get("/api/auth/status")
def auth_status(request: Request):
    """Check current authentication status."""
    token = request.cookies.get("site_auth_token") or request.headers.get("X-Auth-Token")
    return {"authenticated": bool(token == AUTH_TOKEN)}


def get_default_cookie() -> str:
    """Load default cookie from config.json if present."""
    try:
        cfg = Path(__file__).resolve().parent.parent.parent / "config.json"
        if cfg.exists():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            return data.get("cookie", "")
    except Exception:
        pass
    return ""


def extract_local_zhihu_cookie() -> dict:
    """Attempts to auto-detect Zhihu cookie from local Edge/Chrome browser databases."""
    if sys.platform != "win32":
        return {
            "ok": False,
            "reason": "non_windows",
            "message": "当前处于云端服务器环境，受浏览器安全沙箱限制无法跨网络读取您个人电脑。请使用【方式二：1秒控制台口诀】或【方式三：弹出网页登录】！",
        }

    try:
        import base64
        import sqlite3
        import win32crypt
        from Crypto.Cipher import AES
    except ImportError:
        return {
            "ok": False,
            "reason": "missing_deps",
            "message": "本地环境缺少解密组件，请直接使用【方式二：1秒控制台口诀】。",
        }

    home = Path.home()
    browsers = [
        ("Edge", home / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"),
        ("Chrome", home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"),
    ]

    found_browsers = []
    locked = False

    for b_name, user_data in browsers:
        if not user_data.exists():
            continue
        found_browsers.append(b_name)
        local_state_path = user_data / "Local State"
        if not local_state_path.exists():
            continue

        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                local_state = json.load(f)
            enc_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
            key = win32crypt.CryptUnprotectData(enc_key, None, None, None, 0)[1]
        except Exception:
            continue

        profiles = ["Default"] + [f"Profile {i}" for i in range(1, 8)]
        for prof in profiles:
            cookies_db = user_data / prof / "Network" / "Cookies"
            if not cookies_db.exists():
                cookies_db = user_data / prof / "Cookies"
            if not cookies_db.exists():
                continue

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
                    tmp_path = Path(tmp.name)
                shutil.copy2(cookies_db, tmp_path)
                conn = sqlite3.connect(tmp_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%zhihu.com%'"
                )
                rows = cursor.fetchall()
                conn.close()

                cookies_dict = {}
                for name, enc_val in rows:
                    try:
                        if enc_val[:3] in (b"v10", b"v11"):
                            nonce = enc_val[3:15]
                            ciphertext = enc_val[15:-16]
                            tag = enc_val[-16:]
                            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                            val = cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8", errors="ignore")
                        else:
                            val = win32crypt.CryptUnprotectData(enc_val, None, None, None, 0)[1].decode("utf-8", errors="ignore")
                        if val:
                            cookies_dict[name] = val
                    except Exception:
                        pass

                if "z_c0" in cookies_dict:
                    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
                    return {
                        "ok": True,
                        "browser": b_name,
                        "profile": prof,
                        "z_c0": cookies_dict["z_c0"],
                        "cookie": cookie_str,
                        "message": f"成功从电脑 {b_name} ({prof}) 读取到知乎凭证！",
                    }
            except PermissionError:
                locked = True
            except Exception:
                pass
            finally:
                if tmp_path and tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except Exception:
                        pass

    if locked:
        return {
            "ok": False,
            "reason": "locked",
            "message": f"已检测到电脑中的 {'/'.join(found_browsers)}，但浏览器当前正在运行并锁定了数据文件。请关闭浏览器窗口后再点一次；或者直接使用下方的【方式二：1秒控制台口诀】！",
        }

    if found_browsers:
        return {
            "ok": False,
            "reason": "not_logged_in",
            "message": f"已扫描电脑中的 {'/'.join(found_browsers)}，但未发现知乎登录凭证。请确保浏览器已登录知乎，或使用下方的【方式二：1秒控制台口诀】！",
        }

    return {
        "ok": False,
        "reason": "not_found",
        "message": "未在电脑默认路径找到 Edge 或 Chrome。建议直接使用【方式二：1秒控制台口诀】。",
    }


def normalize_zhihu_cookie(raw_cookie: str) -> dict:
    """Extracts z_c0 and normalizes raw cookie strings or document.cookie paste."""
    raw = (raw_cookie or "").strip()
    if not raw:
        return {"valid": False, "cookie": "", "z_c0": "", "message": "凭证为空"}

    z_c0_match = re.search(r'z_c0="?([^";\s]+)"?', raw)
    if z_c0_match:
        z_c0_val = z_c0_match.group(1)
        return {
            "valid": True,
            "cookie": raw,
            "z_c0": z_c0_val,
            "message": f"成功识别知乎凭证 (z_c0: {z_c0_val[:12]}...)",
        }

    if raw.startswith("2|") or (len(raw) > 40 and "=" not in raw):
        return {
            "valid": True,
            "cookie": f"z_c0={raw}",
            "z_c0": raw,
            "message": f"成功识别并封装 z_c0 凭证 ({raw[:12]}...)",
        }

    return {
        "valid": False,
        "cookie": raw,
        "z_c0": "",
        "message": "已填入凭证，若遇限流建议包含 z_c0=...",
    }


class CookieParseRequest(BaseModel):
    cookie: str


@app.post("/api/cookie/auto-detect")
def api_cookie_auto_detect():
    """Auto-detects local Zhihu cookie from Chrome/Edge databases."""
    return extract_local_zhihu_cookie()


@app.post("/api/cookie/parse")
def api_cookie_parse(req: CookieParseRequest):
    """Parses and validates a raw cookie string or z_c0."""
    return normalize_zhihu_cookie(req.cookie)


@app.post("/api/inspect")
def inspect_target(req: InspectRequest):
    """Inspects any author profile, column, or link and catalogs all child assets including dynamic activities."""
    cookie = (req.cookie or "").strip() or get_default_cookie()
    client = ZhihuClient(cookie=cookie)
    url = req.url.strip()

    if not url:
        raise HTTPException(status_code=400, detail="请输入有效的知乎主页或专栏链接")

    # 1. If column URL or column slug
    is_column = (
        "zhihu.com/column/" in url
        or "/c_" in url
        or url.startswith("c_")
        or ("zhuanlan.zhihu.com" in url and "/p/" not in url)
    )

    if is_column:
        col_scraper = ColumnScraper(client)
        col_info = col_scraper.get_column_info(url)
        limit = None if (req.max_items is None or req.max_items <= 0) else req.max_items
        articles = col_scraper.list_column_articles(url, max_items=limit)
        return {
            "target_type": "column",
            "column": {
                "id": col_info.get("id", ""),
                "title": col_info.get("title", "专栏"),
                "description": col_info.get("description", ""),
                "image_url": col_info.get("image_url", ""),
                "articles_count": col_info.get("items_count") or col_info.get("articles_count") or len(articles),
                "author": col_info.get("author", {})
            },
            "total_items": len(articles),
            "items": articles
        }

    # 2. Otherwise treat as author or general profile
    author_scraper = AuthorScraper(client)
    try:
        limit = None if (req.max_items is not None and req.max_items <= 0) else (req.max_items or 50)
        catalog = author_scraper.catalog_all_assets(
            url,
            include_articles=True,
            include_answers=True,
            include_pins=True,
            include_columns=True,
            include_activities=True,
            max_per_category=limit or 50
        )
        catalog["target_type"] = "author"
        return catalog
    except Exception as e:
        logger.error("Error inspecting %s: %s", url, e)
        raise HTTPException(status_code=500, detail=f"解析知乎资产失败: {str(e)}")


def run_batch_job(job_id: str, cookie: str, items: List[Dict[str, Any]], options: Dict[str, Any]):
    """Background task executing batch scraping with physical ZIP persistence & standard EPUB generation."""
    job = JOBS[job_id]
    job["status"] = "running"
    job["total"] = len(items)
    job["current"] = 0
    job["logs"] = []

    client = ZhihuClient(cookie=cookie)
    article_scraper = ArticleScraper(client)
    answer_scraper = AnswerScraper(client)
    pin_scraper = PinScraper(client)
    col_scraper = ColumnScraper(client)
    comment_scraper = CommentScraper(client)
    visual_archiver = VisualArchiver(cookie=cookie)

    save_markdown = options.get("save_markdown", True)
    save_comments = options.get("save_comments", True)
    save_screenshot = options.get("save_screenshot", True)
    highlight_kws = options.get("highlight_keywords", [])

    temp_dir = Path(tempfile.mkdtemp(prefix=f"zhihu_job_{job_id}_"))
    job["output_dir"] = str(temp_dir)

    articles_dir = temp_dir / "articles"
    comments_dir = temp_dir / "comments"
    screenshots_dir = temp_dir / "screenshots"

    articles_dir.mkdir(parents=True, exist_ok=True)
    comments_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Prepare EPUB builder
    author_guess = "知乎创作者"
    if items:
        author_guess = items[0].get("author_name") or items[0].get("author", {}).get("name") or "知乎创作者"
    epub_builder = ZhihuEpubBuilder(title=f"知乎精选存证合集 (共{len(items)}篇)", author=author_guess)
    epub_builder.add_cover_page(subtitle=f"归档批次 ID: {job_id}", extra_info={
        "收录条目数": f"{len(items)} 条",
        "生成时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "归档引擎": "Zhihu Scraper & Investigator"
    })

    total = len(items)
    for idx, item in enumerate(items, 1):
        item_type = item.get("type", "article")
        item_id = str(item.get("id"))
        raw_title = item.get("raw_title") or item.get("title", f"item_{item_id}")
        title = item.get("title", f"item_{item_id}")
        url = item.get("url", "")
        created_at = item.get("created_at", "")
        voteup = item.get("voteup_count", 0)
        comment_cnt = item.get("comment_count", 0)

        msg = f"[{idx}/{total}] 正在抓取 ({item_type}): 《{raw_title[:30]}》"
        job["current"] = idx
        job["progress"] = int((idx / total) * 100)
        job["current_message"] = msg
        job["logs"].append(f"{time.strftime('%H:%M:%S')} - {msg}")

        # Column handling
        if item_type == "column":
            try:
                col_sub_dir = articles_dir / f"column_{safe_name(raw_title)}"
                sub_arts = col_scraper.list_column_articles(item_id, max_items=50)
                job["logs"].append(f"{time.strftime('%H:%M:%S')} - 专栏内包含 {len(sub_arts)} 篇，正在同步批量抓取...")
                for s_idx, s_art in enumerate(sub_arts, 1):
                    s_id = s_art["id"]
                    if save_markdown:
                        art_res = article_scraper.scrape(s_id, save_dir=col_sub_dir)
                        if art_res and art_res.get("content"):
                            epub_builder.add_article_chapter(
                                len(epub_builder.chapters),
                                s_art.get("title", f"专栏文章_{s_id}"),
                                art_res.get("content", ""),
                                created_at=s_art.get("created_at", ""),
                                url=f"https://zhuanlan.zhihu.com/p/{s_id}",
                                voteup_count=s_art.get("voteup_count", 0),
                                comment_count=s_art.get("comment_count", 0),
                                item_type="专栏文章"
                            )
                    if save_comments:
                        c_path = comments_dir / f"comments_article_{s_id}.json"
                        comment_scraper.scrape_comment_tree("article", s_id, save_path=c_path)
            except Exception as e:
                job["logs"].append(f"{time.strftime('%H:%M:%S')} - ⚠️ 专栏批量抓取异常: {e}")
            continue

        # 1. Scrape Content & Feed into EPUB
        scraped_content = ""
        if save_markdown:
            try:
                res_data = None
                if item_type == "article":
                    res_data = article_scraper.scrape(item_id, save_dir=articles_dir)
                elif item_type == "answer":
                    res_data = answer_scraper.scrape(item_id, save_dir=articles_dir)
                elif item_type == "pin":
                    res_data = pin_scraper.scrape(item_id, save_dir=articles_dir)

                if res_data and isinstance(res_data, dict):
                    scraped_content = res_data.get("content", "")
            except Exception as e:
                job["logs"].append(f"{time.strftime('%H:%M:%S')} - ⚠️ 正文抓取异常: {e}")

        # Fallback to excerpt if full content empty
        if not scraped_content:
            scraped_content = item.get("excerpt") or "（该条目无正文或仅包含动态动作）"

        # Add to EPUB
        try:
            epub_builder.add_article_chapter(
                idx,
                raw_title,
                scraped_content,
                created_at=created_at,
                url=url,
                voteup_count=voteup,
                comment_count=comment_cnt,
                item_type="文章" if item_type == "article" else "想法" if item_type == "pin" else "回答" if item_type == "answer" else "动态"
            )
        except Exception as e:
            logger.warning("Failed to add chapter to EPUB: %s", e)

        # 2. Scrape Comments
        if save_comments and item_type in ["article", "answer", "pin"]:
            try:
                c_path = comments_dir / f"comments_{item_type}_{item_id}.json"
                comment_scraper.scrape_comment_tree(item_type, item_id, save_path=c_path)
            except Exception as e:
                job["logs"].append(f"{time.strftime('%H:%M:%S')} - ⚠️ 评论抓取异常: {e}")

        # 3. Capture Screenshot
        if save_screenshot and url:
            try:
                img_path = screenshots_dir / f"screenshot_{item_type}_{safe_name(raw_title)}_{item_id}.png"
                visual_archiver.capture_screenshot(
                    url,
                    output_path=img_path,
                    highlight_keywords=highlight_kws
                )
            except Exception as e:
                job["logs"].append(f"{time.strftime('%H:%M:%S')} - ⚠️ 截图异常: {e}")

        time.sleep(0.2)

    # 4. Build Standalone EPUB
    epub_path = temp_dir / f"zhihu_archive_{job_id}.epub"
    try:
        epub_builder.build(epub_path)
        job["epub_path"] = str(epub_path)
        job["epub_size"] = epub_path.stat().st_size
        job["logs"].append(f"{time.strftime('%H:%M:%S')} - 📖 EPUB 电子书已生成 ({job['epub_size'] / (1024*1024):.2f} MB)。")
    except Exception as e:
        logger.error("EPUB build error: %s", e)
        job["logs"].append(f"{time.strftime('%H:%M:%S')} - ⚠️ EPUB 生成异常: {e}")

    # 5. Package as Physical ZIP
    zip_path = temp_dir / f"zhihu_archive_{job_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(".zip"):
                    continue
                full_p = Path(root) / file
                rel_p = full_p.relative_to(temp_dir)
                zf.write(full_p, arcname=str(rel_p))

    job["zip_path"] = str(zip_path)
    job["zip_size"] = zip_path.stat().st_size
    job["status"] = "completed"
    job["current_message"] = "🎉 全部选定任务存证完毕！支持下载 ZIP 压缩包或 EPUB 电子书。"
    job["logs"].append(f"{time.strftime('%H:%M:%S')} - 📦 全部完成！ZIP 文件已生成 ({job['zip_size'] / (1024*1024):.2f} MB)。")


@app.post("/api/scrape/batch")
def start_batch_scrape(req: BatchScrapeRequest, bg_tasks: BackgroundTasks):
    """Starts a batch scraping job in the background."""
    if not req.items:
        raise HTTPException(status_code=400, detail="未勾选任何抓取条目")

    job_id = str(uuid.uuid4())[:8]
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "total": len(req.items),
        "current": 0,
        "current_message": "准备开始...",
        "logs": [],
        "zip_path": None,
        "epub_path": None
    }

    cookie = (req.cookie or "").strip() or get_default_cookie()
    bg_tasks.add_task(run_batch_job, job_id, cookie, req.items, req.options or {})
    return {"job_id": job_id, "status": "started"}


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """SSE event stream pushing real-time progress updates to frontend."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_generator():
        while True:
            job = JOBS.get(job_id)
            if not job:
                break
            payload = {
                "job_id": job["job_id"],
                "status": job["status"],
                "progress": job.get("progress", 0),
                "current": job.get("current", 0),
                "total": job.get("total", 0),
                "message": job.get("current_message", ""),
                "logs": job.get("logs", [])[-20:],
                "has_epub": bool(job.get("epub_path"))
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if job["status"] in ["completed", "error"]:
                break
            await asyncio.sleep(0.8)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/download")
def download_job_zip(job_id: str):
    """Download the finalized ZIP containing all articles, comments, screenshots and EPUB."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    zip_path_str = job.get("zip_path")
    if job["status"] != "completed" or not zip_path_str or not os.path.exists(zip_path_str):
        raise HTTPException(status_code=400, detail="任务尚未完成或数据不可用")

    return FileResponse(
        path=zip_path_str,
        media_type="application/zip",
        filename=f"zhihu_archive_{job_id}.zip"
    )


@app.get("/api/jobs/{job_id}/download_epub")
def download_job_epub(job_id: str):
    """Download the finalized EPUB e-book directly for e-readers."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    epub_path_str = job.get("epub_path")
    if not epub_path_str or not os.path.exists(epub_path_str):
        raise HTTPException(status_code=400, detail="电子书尚未生成或数据不可用")

    return FileResponse(
        path=epub_path_str,
        media_type="application/epub+zip",
        filename=f"zhihu_archive_{job_id}.epub"
    )


@app.get("/download/taiji.zip")
def download_taiji_public():
    """Public direct download endpoint for the complete martial arts column archive."""
    candidates = [
        Path("/opt/zhihu-scraper/data/清一太极武术理论与实践_全量专栏归档.zip"),
        Path(r"C:\Users\25472\Desktop\清一太极武术理论与实践_全量专栏归档.zip"),
        Path(r"C:\Users\25472\.gemini\antigravity\brain\96353930-0ede-48a8-be01-ea896847ab4c\清一太极武术理论与实践_全量专栏归档.zip")
    ]
    for p in candidates:
        if p.exists():
            return FileResponse(
                path=str(p),
                filename="清一太极武术理论与实践_全量专栏归档.zip",
                media_type="application/zip"
            )
@app.get("/favicon.ico", include_in_schema=False)
def get_favicon():
    """Serves the vector favicon for browser tabs and Omnibox autocomplete."""
    fav = STATIC_DIR / "favicon.svg"
    if fav.exists():
        return FileResponse(path=str(fav), media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")


@app.get("/manifest.json", include_in_schema=False)
def get_manifest():
    """Web App Manifest for browser identity recognition, PWA installation, and Omnibox search."""
    return {
        "name": "Apex | 知乎创作者定向排查与批量存证系统",
        "short_name": "Apex",
        "description": "知乎创作者定向排查、专栏穿透、想法动态筛选、EPUB与ZIP双导出 (zh.samuraiguan.cloud)",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0b0f19",
        "theme_color": "#06b6d4",
        "icons": [
            {
                "src": "/static/logo.svg",
                "sizes": "any",
                "type": "image/svg+xml"
            }
        ]
    }


@app.get("/", response_class=HTMLResponse)
def index_ui():
    """Renders the comprehensive self-service Web UI with password gate, category filters, and dual export."""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Apex | 知乎创作者定向排查与批量存证系统 (zh.samuraiguan.cloud)</title>
    
    <!-- Brand Identity & Browser Omnibox Autocomplete Metadata -->
    <meta name="application-name" content="Apex">
    <meta name="apple-mobile-web-app-title" content="Apex">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="description" content="Apex - 知乎创作者定向排查与批量存证系统。创作者资产与动态全息检索、专栏穿透、想法/动态独立筛选、ZIP 压缩包与 EPUB 电子书一键导出 (zh.samuraiguan.cloud)。">
    <meta name="keywords" content="Apex, apex, zhihu, 知乎, 知乎存证, 批量下载, 知乎爬虫, zh.samuraiguan.cloud">
    <meta name="theme-color" content="#06b6d4">
    
    <!-- Open Graph for Social, Omnibox, and Bookmarks -->
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Apex">
    <meta property="og:title" content="Apex | 知乎创作者定向排查与批量存证系统">
    <meta property="og:description" content="创作者资产全息检索、专栏穿透、想法/动态独立筛选、ZIP 与 EPUB 一键导出。">
    <meta property="og:url" content="https://zh.samuraiguan.cloud">
    <meta property="og:image" content="/static/logo.svg">
    
    <!-- Favicon & Touch Icons -->
    <link rel="icon" type="image/svg+xml" href="/static/logo.svg">
    <link rel="alternate icon" href="/favicon.ico">
    <link rel="apple-touch-icon" href="/static/logo.svg">
    <link rel="manifest" href="/manifest.json">
    <script>
        (function() {
            var theme = localStorage.getItem('theme_mode') || 'dark';
            document.documentElement.setAttribute('data-theme', theme);
        })();
    </script>
    <style>
        :root, [data-theme="dark"] {
            --bg-base: #0b0f19;
            --card-bg: #151d30;
            --card-border: #222f4c;
            --card-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
            --header-bg: linear-gradient(135deg, #151d30 0%, #1a2540 100%);
            --header-border: #2a3b61;
            --h1-color: #38bdf8;
            --h2-color: #f1f5f9;
            --text-main: #e2e8f0;
            --text-muted: #94a3b8;
            --text-subtle: #64748b;
            --input-bg: #090e18;
            --input-border: #253352;
            --input-color: #f8fafc;
            --input-date-bg: #151d30;
            --input-date-border: #2d3f66;
            --toolbar-bg: #090e18;
            --toolbar-border: #1e293b;
            --toolbar-divider: #141f36;
            --checkbox-color: #cbd5e1;
            --pill-bg: #131b2e;
            --pill-border: #233252;
            --pill-color: #94a3b8;
            --pill-hover-border: #38bdf8;
            --pill-hover-color: #f1f5f9;
            --pill-active-bg: rgba(6, 182, 212, 0.15);
            --pill-active-border: #06b6d4;
            --pill-active-color: #38bdf8;
            --profile-bg: #131b2e;
            --profile-border: #233252;
            --profile-name-color: #ffffff;
            --col-card-bg: #0d1424;
            --col-card-border: #212e4a;
            --col-card-title: #e0f2fe;
            --col-card-desc: #94a3b8;
            --table-wrap-bg: #090e18;
            --table-wrap-border: #1e293b;
            --th-bg: #0f172a;
            --th-color: #94a3b8;
            --th-border: #1e293b;
            --tr-border: #141f36;
            --tr-hover: rgba(30, 41, 59, 0.5);
            --tr-title: #f8fafc;
            --tr-date: #cbd5e1;
            --btn-outline-bg: #1e293b;
            --btn-outline-color: #cbd5e1;
            --btn-outline-border: #334155;
            --btn-outline-hover-bg: #334155;
            --btn-outline-hover-color: #ffffff;
            --progress-card-bg: linear-gradient(180deg, #111b2e 0%, #0d1527 100%);
            --progress-card-border: #0284c7;
            --progress-bar-bg: #090e18;
            --terminal-bg: #050811;
            --terminal-border: #141f36;
            --terminal-color: #94a3b8;
            --modal-backdrop: rgba(5, 9, 17, 0.85);
            --modal-box-bg: #111827;
            --modal-box-border: #1f293d;
            --modal-box-shadow: 0 20px 40px -10px rgba(0,0,0,0.6);
            --modal-title-color: #38bdf8;
            --modal-desc-color: #94a3b8;
            --cyan: #06b6d4;
            --cyan-glow: rgba(6, 182, 212, 0.25);
            --emerald: #10b981;
            --emerald-glow: rgba(16, 185, 129, 0.25);
            --purple: #a855f7;
            --purple-glow: rgba(168, 85, 247, 0.25);
            --blue: #3b82f6;
            --amber: #f59e0b;
            --rose: #f43f5e;
        }

        [data-theme="light"] {
            --bg-base: #f8fafc;
            --card-bg: #ffffff;
            --card-border: #e2e8f0;
            --card-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.06);
            --header-bg: linear-gradient(135deg, #ffffff 0%, #f1f5f9 100%);
            --header-border: #cbd5e1;
            --h1-color: #0284c7;
            --h2-color: #0f172a;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --text-subtle: #94a3b8;
            --input-bg: #f8fafc;
            --input-border: #cbd5e1;
            --input-color: #0f172a;
            --input-date-bg: #ffffff;
            --input-date-border: #cbd5e1;
            --toolbar-bg: #f8fafc;
            --toolbar-border: #e2e8f0;
            --toolbar-divider: #e2e8f0;
            --checkbox-color: #334155;
            --pill-bg: #f1f5f9;
            --pill-border: #e2e8f0;
            --pill-color: #475569;
            --pill-hover-border: #0284c7;
            --pill-hover-color: #0284c7;
            --pill-active-bg: rgba(2, 132, 199, 0.12);
            --pill-active-border: #0284c7;
            --pill-active-color: #0284c7;
            --profile-bg: #f8fafc;
            --profile-border: #e2e8f0;
            --profile-name-color: #0f172a;
            --col-card-bg: #ffffff;
            --col-card-border: #e2e8f0;
            --col-card-title: #0f172a;
            --col-card-desc: #64748b;
            --table-wrap-bg: #ffffff;
            --table-wrap-border: #e2e8f0;
            --th-bg: #f8fafc;
            --th-color: #475569;
            --th-border: #e2e8f0;
            --tr-border: #f1f5f9;
            --tr-hover: #f8fafc;
            --tr-title: #0f172a;
            --tr-date: #475569;
            --btn-outline-bg: #f1f5f9;
            --btn-outline-color: #334155;
            --btn-outline-border: #cbd5e1;
            --btn-outline-hover-bg: #e2e8f0;
            --btn-outline-hover-color: #0f172a;
            --progress-card-bg: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            --progress-card-border: #0284c7;
            --progress-bar-bg: #e2e8f0;
            --terminal-bg: #0f172a;
            --terminal-border: #cbd5e1;
            --terminal-color: #cbd5e1;
            --modal-backdrop: rgba(15, 23, 42, 0.45);
            --modal-box-bg: #ffffff;
            --modal-box-border: #e2e8f0;
            --modal-box-shadow: 0 20px 40px -10px rgba(0,0,0,0.12);
            --modal-title-color: #0284c7;
            --modal-desc-color: #64748b;
            --cyan: #0284c7;
            --cyan-glow: rgba(2, 132, 199, 0.2);
            --emerald: #059669;
            --emerald-glow: rgba(5, 150, 105, 0.2);
            --purple: #7c3aed;
            --purple-glow: rgba(124, 58, 237, 0.2);
            --blue: #2563eb;
            --amber: #d97706;
            --rose: #e11d48;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            padding: 24px 16px;
            transition: background-color 0.25s ease, color 0.25s ease;
        }
        .container { max-width: 1160px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }

        /* Card Styles */
        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: var(--card-shadow);
            transition: background-color 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        }

        /* Header */
        header.card {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            background: var(--header-bg);
            border-color: var(--header-border);
        }
        .brand-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .brand-logo-wrap {
            width: 48px;
            height: 48px;
            min-width: 48px;
            border-radius: 12px;
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(16, 185, 129, 0.15) 100%);
            border: 1px solid rgba(6, 182, 212, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 5px;
            box-shadow: 0 4px 15px var(--cyan-glow);
            transition: all 0.25s ease;
            cursor: pointer;
        }
        .brand-logo-wrap:hover {
            transform: scale(1.05) rotate(2deg);
            box-shadow: 0 6px 20px var(--cyan-glow);
        }
        .brand-logo-img {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }
        .brand-text {
            display: flex;
            flex-direction: column;
        }
        .brand-title-row {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .brand-title-name {
            font-size: 26px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #38bdf8 0%, #34d399 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 2px 10px rgba(56, 189, 248, 0.25);
            font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        [data-theme="light"] .brand-title-name {
            background: linear-gradient(135deg, #0284c7 0%, #059669 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: none;
        }
        .brand-vault-badge {
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            padding: 2px 8px;
            border-radius: 4px;
            background: rgba(6, 182, 212, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(6, 182, 212, 0.3);
        }
        [data-theme="light"] .brand-vault-badge {
            background: rgba(2, 132, 199, 0.12);
            color: #0284c7;
            border-color: rgba(2, 132, 199, 0.25);
        }
        .brand-h1 {
            font-size: 17px;
            font-weight: 700;
            color: var(--text-main);
            margin: 0;
            display: inline;
        }
        .brand-subtitle {
            color: var(--text-muted);
            font-size: 13px;
            margin-top: 3px;
        }
        h1 { font-size: 22px; font-weight: 700; color: var(--h1-color); display: flex; align-items: center; gap: 10px; }
        .subtitle { color: var(--text-muted); font-size: 13px; margin-top: 4px; }
        .badge-status {
            font-size: 12px;
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 6px 14px;
            border-radius: 9999px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-weight: 500;
        }
        [data-theme="light"] .badge-status {
            background: rgba(5, 150, 105, 0.1);
            color: #059669;
            border-color: rgba(5, 150, 105, 0.25);
        }

        /* Form Inputs */
        label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; font-weight: 500; }
        input[type="text"], input[type="password"], select {
            width: 100%;
            background: var(--input-bg);
            border: 1px solid var(--input-border);
            border-radius: 10px;
            padding: 12px 16px;
            color: var(--input-color);
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s, background-color 0.25s ease, color 0.25s ease;
        }
        input[type="text"]:focus, input[type="password"]:focus, select:focus {
            border-color: var(--cyan);
            box-shadow: 0 0 0 3px var(--cyan-glow);
        }

        /* Credential Helper Trigger & Cards */
        .btn-credential-helper {
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.2) 0%, rgba(16, 185, 129, 0.2) 100%);
            border: 1px solid #06b6d4;
            color: #38bdf8;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 9999px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px var(--cyan-glow);
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .btn-credential-helper:hover {
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.35) 0%, rgba(16, 185, 129, 0.35) 100%);
            transform: translateY(-1px);
            box-shadow: 0 4px 14px var(--cyan-glow);
            color: #ffffff;
        }
        [data-theme="light"] .btn-credential-helper {
            background: linear-gradient(135deg, #e0f2fe 0%, #d1fae5 100%);
            border-color: #0284c7;
            color: #0284c7;
        }
        [data-theme="light"] .btn-credential-helper:hover {
            background: linear-gradient(135deg, #0284c7 0%, #059669 100%);
            color: #ffffff;
        }
        .input-inline-btn {
            position: absolute;
            right: 8px;
            top: 50%;
            transform: translateY(-50%);
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 11px;
            padding: 4px 8px;
            border-radius: 6px;
            cursor: pointer;
        }
        .input-inline-btn:hover {
            background: rgba(244, 63, 94, 0.15);
            color: #f43f5e;
        }

        .cred-card {
            background: var(--input-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px;
            transition: all 0.2s ease;
        }
        .cred-card:hover {
            border-color: var(--cyan);
            box-shadow: 0 4px 16px var(--cyan-glow);
        }
        .cred-card-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
        }
        .cred-card-title {
            font-size: 14px;
            font-weight: 700;
            color: var(--text-main);
            margin: 0;
        }
        .cred-card-desc {
            font-size: 12px;
            color: var(--text-muted);
            line-height: 1.5;
        }
        .cred-card-tag {
            font-size: 10px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
            background: var(--pill-bg);
            color: var(--text-muted);
            border: 1px solid var(--pill-border);
        }
        .cred-tag-recommend {
            background: rgba(6, 182, 212, 0.15);
            color: #38bdf8;
            border-color: rgba(6, 182, 212, 0.35);
        }
        [data-theme="light"] .cred-tag-recommend {
            background: rgba(2, 132, 199, 0.12);
            color: #0284c7;
            border-color: rgba(2, 132, 199, 0.25);
        }
        .cred-tag-foolproof {
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border-color: rgba(16, 185, 129, 0.35);
        }
        [data-theme="light"] .cred-tag-foolproof {
            background: rgba(5, 150, 105, 0.12);
            color: #059669;
            border-color: rgba(5, 150, 105, 0.25);
        }

        /* Checkbox Options */
        .options-row {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--options-border);
        }
        .checkbox-group { display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px; color: var(--checkbox-color); }
        .checkbox-label { display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
        .checkbox-label input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--cyan); cursor: pointer; }

        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 10px 20px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: all 0.2s ease;
            text-decoration: none;
        }
        .btn-primary {
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35);
        }
        .btn-primary:hover:not(:disabled) {
            background: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
            transform: translateY(-1px);
        }
        .btn-emerald {
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(5, 150, 105, 0.35);
        }
        .btn-emerald:hover:not(:disabled) {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            transform: translateY(-1px);
        }
        .btn-purple {
            background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.35);
        }
        .btn-purple:hover:not(:disabled) {
            background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
            transform: translateY(-1px);
        }
        .btn-outline {
            background: var(--btn-outline-bg);
            color: var(--btn-outline-color);
            border: 1px solid var(--btn-outline-border);
            padding: 6px 12px;
            font-size: 12px;
        }
        .btn-outline:hover { background: var(--btn-outline-hover-bg); color: var(--btn-outline-hover-color); }
        .btn-sm { padding: 6px 12px; font-size: 12px; border-radius: 8px; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; }

        /* Theme Toggle Button */
        .theme-switch-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--btn-outline-bg);
            border: 1px solid var(--btn-outline-border);
            color: var(--btn-outline-color);
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            transition: all 0.2s ease;
        }
        .theme-switch-btn:hover {
            background: var(--btn-outline-hover-bg);
            color: var(--btn-outline-hover-color);
            border-color: var(--cyan);
        }

        /* Filter Pills */
        .filter-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 6px;
        }
        .filter-pill {
            background: var(--pill-bg);
            border: 1px solid var(--pill-border);
            color: var(--pill-color);
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .filter-pill:hover {
            border-color: var(--pill-hover-border);
            color: var(--pill-hover-color);
        }
        .filter-pill.active {
            background: var(--pill-active-bg);
            border-color: var(--pill-active-border);
            color: var(--pill-active-color);
            font-weight: 600;
        }

        /* Profile Banner */
        .profile-banner {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            background: var(--profile-bg);
            border: 1px solid var(--profile-border);
            border-radius: 14px;
            padding: 20px;
            transition: background-color 0.25s ease, border-color 0.25s ease;
        }
        .profile-left { display: flex; align-items: center; gap: 16px; }
        .profile-avatar { width: 60px; height: 60px; border-radius: 50%; border: 2px solid var(--cyan); object-fit: cover; }
        .profile-name { font-size: 18px; font-weight: 700; color: var(--profile-name-color); display: flex; align-items: center; gap: 8px; }
        .profile-headline { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
        .profile-stats { display: flex; gap: 24px; text-align: center; }
        .stat-label { font-size: 11px; color: var(--text-muted); }
        .stat-value { font-size: 17px; font-weight: 700; color: var(--cyan); }

        /* Column Grid */
        .columns-container { margin-top: 16px; }
        .columns-header { font-size: 14px; font-weight: 600; color: var(--text-main); margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
        .columns-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 14px;
        }
        .column-card {
            background: var(--col-card-bg);
            border: 1px solid var(--col-card-border);
            border-radius: 12px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.2s ease;
        }
        .column-card:hover {
            border-color: var(--cyan);
            box-shadow: 0 4px 20px var(--cyan-glow);
            transform: translateY(-2px);
        }
        .column-card-title { font-size: 14px; font-weight: 700; color: var(--col-card-title); margin-bottom: 6px; }
        .column-card-desc { font-size: 12px; color: var(--col-card-desc); line-height: 1.4; margin-bottom: 12px; flex-grow: 1; }
        .column-card-footer { display: flex; justify-content: space-between; align-items: center; }
        .column-badge { font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 6px; background: rgba(168, 85, 247, 0.15); color: #a855f7; border: 1px solid rgba(168, 85, 247, 0.3); }

        /* Table */
        .table-wrap {
            overflow-x: auto;
            border: 1px solid var(--table-wrap-border);
            border-radius: 12px;
            background: var(--table-wrap-bg);
            margin-top: 14px;
            transition: background-color 0.25s ease, border-color 0.25s ease;
        }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
        thead th {
            background: var(--th-bg);
            color: var(--th-color);
            padding: 12px 14px;
            font-weight: 600;
            border-bottom: 1px solid var(--th-border);
            white-space: nowrap;
        }
        tbody tr { border-bottom: 1px solid var(--tr-border); transition: background 0.15s; }
        tbody tr:hover { background: var(--tr-hover); }
        td { padding: 12px 14px; vertical-align: middle; }

        /* Badges */
        .badge {
            display: inline-block;
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 6px;
            white-space: nowrap;
        }
        .badge-article { background: rgba(6, 182, 212, 0.15); color: #0284c7; border: 1px solid rgba(6, 182, 212, 0.3); }
        [data-theme="dark"] .badge-article { color: #22d3ee; }
        .badge-answer { background: rgba(59, 130, 246, 0.15); color: #2563eb; border: 1px solid rgba(59, 130, 246, 0.3); }
        [data-theme="dark"] .badge-answer { color: #60a5fa; }
        .badge-column { background: rgba(168, 85, 247, 0.15); color: #7c3aed; border: 1px solid rgba(168, 85, 247, 0.3); }
        [data-theme="dark"] .badge-column { color: #c084fc; }
        .badge-pin { background: rgba(245, 158, 11, 0.15); color: #d97706; border: 1px solid rgba(245, 158, 11, 0.3); }
        [data-theme="dark"] .badge-pin { color: #fbbf24; }
        .badge-act { background: rgba(16, 185, 129, 0.15); color: #059669; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 11px; margin-right: 6px; }
        [data-theme="dark"] .badge-act { color: #34d399; }

        /* Progress Card */
        .progress-card {
            border-color: var(--progress-card-border);
            background: var(--progress-card-bg);
            box-shadow: 0 10px 35px rgba(2, 132, 199, 0.2);
        }
        .progress-bar-bg { width: 100%; height: 12px; background: var(--progress-bar-bg); border-radius: 9999px; overflow: hidden; border: 1px solid var(--card-border); margin: 12px 0; }
        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #06b6d4 0%, #10b981 100%);
            border-radius: 9999px;
            transition: width 0.3s ease;
        }
        .terminal-log {
            background: var(--terminal-bg);
            border: 1px solid var(--terminal-border);
            border-radius: 10px;
            padding: 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 11px;
            color: var(--terminal-color);
            height: 150px;
            overflow-y: auto;
            line-height: 1.6;
        }

        /* Password Modal Backdrop */
        .modal-backdrop {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: var(--modal-backdrop);
            backdrop-filter: blur(8px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            transition: background 0.25s ease;
        }
        .modal-box {
            position: relative;
            width: 90%;
            max-width: 440px;
            background: var(--modal-box-bg);
            border: 1px solid var(--modal-box-border);
            border-radius: 20px;
            padding: 36px 32px 32px;
            box-shadow: var(--modal-box-shadow);
            text-align: center;
            transition: background-color 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        }
        .modal-logo-wrap {
            width: 64px;
            height: 64px;
            margin: 0 auto 16px auto;
            border-radius: 16px;
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(16, 185, 129, 0.15) 100%);
            border: 1px solid rgba(6, 182, 212, 0.35);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 8px;
            box-shadow: 0 8px 25px var(--cyan-glow);
            animation: pulseGlow 3s infinite alternate ease-in-out;
        }
        @keyframes pulseGlow {
            0% { transform: scale(1); box-shadow: 0 4px 20px var(--cyan-glow); }
            100% { transform: scale(1.04); box-shadow: 0 8px 30px rgba(6, 182, 212, 0.4); }
        }
        .modal-logo-img {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }
        .modal-title {
            font-size: 19px;
            font-weight: 800;
            color: var(--modal-title-color);
            margin-bottom: 6px;
            letter-spacing: 0.5px;
        }
        .modal-desc {
            font-size: 13px;
            color: var(--modal-desc-color);
            margin-bottom: 24px;
        }
        .error-tip {
            color: #f43f5e;
            font-size: 12px;
            margin-top: 8px;
        }
    </style>
    <script src="/static/vue.global.prod.js" onerror="this.onerror=null;this.src='https://cdnjs.cloudflare.com/ajax/libs/vue/3.3.4/vue.global.prod.js';"></script>
</head>
<body>
    <div id="app">

        <!-- Password Gate Modal -->
        <div v-if="!isAuthenticated" class="modal-backdrop">
            <div class="modal-box">
                <!-- Theme Toggle Button on Modal -->
                <button 
                    @click="toggleTheme" 
                    class="theme-switch-btn" 
                    style="position: absolute; top: 16px; right: 16px; font-size: 11px; padding: 4px 10px;"
                    :title="'切换到' + (theme === 'dark' ? '白天风格' : '暗黑风格')"
                >
                    <span>{{ theme === 'dark' ? '☀️ 白天' : '🌙 暗黑' }}</span>
                </button>
                <div class="modal-logo-wrap">
                    <img src="/static/logo.svg" alt="Apex Logo" class="modal-logo-img">
                </div>
                <div class="modal-title">Apex 系统安全访问门禁</div>
                <div class="modal-desc">请输入系统访问密码以解锁 Apex 定向排查与批量存证系统</div>
                
                <div style="margin-bottom: 16px;">
                    <input 
                        type="password" 
                        v-model="loginPassword" 
                        @keyup.enter="handleLogin" 
                        placeholder="请输入系统访问密码" 
                        style="text-align: center; letter-spacing: 2px; font-size: 15px;"
                        autofocus
                    >
                    <div v-if="loginError" class="error-tip">{{ loginError }}</div>
                </div>

                <button @click="handleLogin" :disabled="loggingIn" class="btn btn-primary" style="width: 100%; padding: 12px; font-size: 14px;">
                    <span v-if="loggingIn">🔄 正在校验中...</span>
                    <span v-else>🚀 验证并进入 Apex</span>
                </button>
            </div>
        </div>

        <!-- Credential Helper Modal -->
        <div v-if="showCredentialModal" class="modal-backdrop" @click.self="showCredentialModal = false">
            <div class="modal-box" style="max-width: 680px; width: 92%; text-align: left; padding: 28px 28px 24px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div style="font-size: 28px;">🔑</div>
                        <div>
                            <h3 style="font-size: 18px; font-weight: 700; color: var(--modal-title-color);">知乎登录凭证一键获取助手</h3>
                            <p style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">彻底告别技术名词与抓包，根据你的情况任选一种傻瓜方式搞定凭证</p>
                        </div>
                    </div>
                    <button @click="showCredentialModal = false" class="btn btn-outline btn-sm" style="padding: 4px 10px; font-size: 13px;">✕ 关闭</button>
                </div>

                <!-- Method Cards Grid -->
                <div style="display: flex; flex-direction: column; gap: 14px;">

                    <!-- Method 1: Local Auto-Read -->
                    <div class="cred-card">
                        <div class="cred-card-header">
                            <span class="cred-card-tag cred-tag-recommend">没手机 · 最推荐</span>
                            <h4 class="cred-card-title">⚡ 方式一：一键读取我电脑里已登录的知乎</h4>
                        </div>
                        <p class="cred-card-desc">只要你电脑里的 Edge 或 Chrome 曾经登录过知乎，点击下方按钮，0 秒直接读取已存凭证，无需掏手机！</p>
                        <div style="display: flex; align-items: center; gap: 12px; margin-top: 10px;">
                            <button @click="autoDetectLocalCookie" :disabled="detectingCookie" class="btn btn-primary" style="padding: 9px 18px; font-size: 13px;">
                                <span v-if="detectingCookie">🔄 正在扫描电脑 Edge/Chrome...</span>
                                <span v-else>⚡ 立即读取电脑已登录的知乎</span>
                            </button>
                            <span v-if="detectMsg" :style="{ fontSize: '12px', color: detectSuccess ? '#10b981' : '#f59e0b', fontWeight: '500' }">
                                {{ detectMsg }}
                            </span>
                        </div>
                    </div>

                    <!-- Method 2: 1-Second Console Trick -->
                    <div class="cred-card" style="border-color: rgba(16, 185, 129, 0.35);">
                        <div class="cred-card-header">
                            <span class="cred-card-tag cred-tag-foolproof">万能 · 100% 成功</span>
                            <h4 class="cred-card-title">💡 方式二：1秒控制台口诀（无需手机·零基础推荐）</h4>
                        </div>
                        <p class="cred-card-desc">如果当前浏览器正在打开知乎，照着下面 3 步做，1 秒搞定：</p>
                        <div style="background: var(--input-bg); border: 1px solid var(--card-border); border-radius: 10px; padding: 12px 14px; margin: 8px 0; font-size: 12px; line-height: 1.8;">
                            <div>1️⃣ 确保打开知乎网页并已登录：<a href="https://www.zhihu.com" target="_blank" style="color: var(--cyan); text-decoration: underline; font-weight: 600;">🔗 点击打开知乎 (在新标签页)</a></div>
                            <div>2️⃣ 在知乎网页按键盘最顶部的 <strong>F12</strong> 键，点击弹出来的顶部 <strong>Console (控制台)</strong></div>
                            <div>3️⃣ 点击下方复制口诀，粘贴到控制台按回车：</div>
                            <div style="display: flex; align-items: center; gap: 10px; margin-top: 6px;">
                                <code style="background: var(--bg-base); border: 1px solid var(--card-border); padding: 5px 12px; border-radius: 6px; font-family: monospace; font-size: 13px; color: #38bdf8;">copy(document.cookie)</code>
                                <button @click="copySnippet" class="btn btn-secondary" style="padding: 6px 14px; font-size: 12px;">
                                    {{ snippetCopied ? '✅ 已复制口诀！' : '📋 点击一键复制口诀' }}
                                </button>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px; margin-top: 8px;">
                            <button @click="pasteFromClipboard" class="btn btn-primary" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); border-color: #10b981; padding: 8px 16px; font-size: 13px;">
                                📋 我已在知乎回车，点此一键自动粘贴并填入
                            </button>
                            <span style="font-size: 11px; color: var(--text-muted);">（点击将直接从剪贴板读取并自动提取有效凭证）</span>
                        </div>
                    </div>

                    <!-- Method 3: Mobile QR or Normal Web Login -->
                    <div class="cred-card">
                        <div class="cred-card-header">
                            <span class="cred-card-tag">有手机 / 记得密码</span>
                            <h4 class="cred-card-title">💻 方式三：弹出知乎官方页面登录</h4>
                        </div>
                        <p class="cred-card-desc">弹出一个知乎官方登录弹窗，有手机可直接用知乎 App 扫码，没手机可输入知乎账号密码登录：</p>
                        <div style="display: flex; align-items: center; gap: 12px; margin-top: 8px;">
                            <button @click="openZhihuPopup" class="btn btn-outline" style="padding: 8px 16px; font-size: 13px;">
                                🌐 弹出知乎官方登录窗口
                            </button>
                            <span style="font-size: 11px; color: var(--text-muted);">登录完成后，再按方式二口诀一键复制即可</span>
                        </div>
                    </div>

                </div>

                <div style="margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--card-border); display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 12px; color: var(--text-muted);">
                        💡 提示：凭证仅保存在您当前浏览器内存中，用于作者数据检索与避开知乎接口风控。
                    </div>
                    <button @click="showCredentialModal = false" class="btn btn-secondary btn-sm" style="padding: 6px 16px;">
                        完成
                    </button>
                </div>
            </div>
        </div>

        <!-- Main Container -->
        <div v-if="isAuthenticated" class="container">
            
            <!-- Header -->
            <header class="card">
                <div class="brand-left">
                    <div class="brand-logo-wrap" title="Apex - 定向排查与批量存证系统">
                        <img src="/static/logo.svg" alt="Apex Logo" class="brand-logo-img">
                    </div>
                    <div class="brand-text">
                        <div class="brand-title-row">
                            <span class="brand-title-name">Apex</span>
                            <span class="brand-vault-badge">Z-VAULT</span>
                            <h1 class="brand-h1">知乎创作者定向排查与批量存证系统</h1>
                        </div>
                        <p class="brand-subtitle">创作者资产全息检索 · 专栏穿透 · 想法/动态独立筛选 · EPUB与ZIP一键导出 (zh.samuraiguan.cloud)</p>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <button 
                        @click="toggleTheme" 
                        class="theme-switch-btn" 
                        :title="'切换到' + (theme === 'dark' ? '白天风格' : '暗黑风格')"
                    >
                        <span>{{ theme === 'dark' ? '☀️ 白天风格' : '🌙 暗黑风格' }}</span>
                    </button>
                    <div class="badge-status">
                        <span style="width: 8px; height: 8px; border-radius: 50%; background: #10b981; display: inline-block;"></span>
                        <span>系统就绪 (Apex Core)</span>
                    </div>
                    <button @click="handleLogout" class="btn btn-outline btn-sm" title="锁定并退出">
                        🔒 退出
                    </button>
                </div>
            </header>

            <!-- Configuration Form Card -->
            <section class="card">
                <h2 style="font-size: 16px; font-weight: 600; color: var(--h2-color); margin-bottom: 16px;">
                    ⚙️ 第一步：输入知乎链接与操作凭证
                </h2>
                
                <div style="display: grid; grid-template-columns: 2fr 2fr 1.2fr; gap: 14px;">
                    <div>
                        <label>目标知乎主页或专栏链接 (必填)</label>
                        <input v-model="targetUrl" type="text" placeholder="例: https://www.zhihu.com/people/shan-chang-qing-yi 或 /column/c_xxx">
                    </div>
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <label style="margin-bottom: 0;">知乎登录凭证 (选填 · 避免知乎限流)</label>
                            <button 
                                type="button" 
                                @click="openCredentialModal" 
                                class="btn-credential-helper"
                                title="打开知乎凭证一键获取助手"
                            >
                                🔑 点我一键获取知乎凭证
                            </button>
                        </div>
                        <div style="position: relative;">
                            <input 
                                v-model="cookie" 
                                @input="handleCookieInput"
                                :type="showCookie ? 'text' : 'password'" 
                                placeholder="无需手动找 Cookie，点击右上角【🔑 一键获取】即可自动填入"
                                style="padding-right: 70px;"
                            >
                            <button 
                                type="button" 
                                v-if="cookie" 
                                @click="cookie = ''; cookieStatus = null" 
                                class="input-inline-btn"
                                title="清空凭证"
                            >
                                ✕ 清空
                            </button>
                        </div>
                        <div v-if="cookieStatus" style="font-size: 11px; margin-top: 4px; display: flex; align-items: center; gap: 4px;">
                            <span v-if="cookieStatus.valid" style="color: #10b981; font-weight: 600;">
                                ✅ {{ cookieStatus.message }}
                            </span>
                            <span v-else style="color: #f59e0b; font-weight: 500;">
                                ⚠️ {{ cookieStatus.message }}
                            </span>
                        </div>
                    </div>
                    <div>
                        <label>检索深度 / 数量上限</label>
                        <select v-model="fetchLimit" style="width: 100%; height: 44px; border-radius: 10px; padding: 0 10px; font-size: 13px;">
                            <option :value="0">🔥 全量无上限 (全部加载)</option>
                            <option :value="300">⚡ 深度拉取 (前300篇)</option>
                            <option :value="100">📋 标准拉取 (前100篇)</option>
                            <option :value="30">🚀 极速预览 (前30篇)</option>
                        </select>
                    </div>
                </div>

                <div class="options-row">
                    <div class="checkbox-group">
                        <label class="checkbox-label">
                            <input type="checkbox" v-model="options.save_markdown">
                            <span>抓取正文 (Markdown)</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" v-model="options.save_comments">
                            <span>抓取楼中楼评论 (.json)</span>
                        </label>
                        <label class="checkbox-label">
                            <input type="checkbox" v-model="options.save_screenshot">
                            <span>原生高清截图 (.png)</span>
                        </label>
                        <label class="checkbox-label" style="color: #c084fc;">
                            <input type="checkbox" checked disabled>
                            <span>📖 自动生成 EPUB 电子书</span>
                        </label>
                    </div>

                    <button @click="inspect(targetUrl)" :disabled="inspecting" class="btn btn-primary">
                        <span v-if="inspecting">🔄 正在检索资产与动态...</span>
                        <span v-else>🔍 检索目标已有资产与动态</span>
                    </button>
                </div>
            </section>

            <!-- Breadcrumb Bar -->
            <div v-if="parentAuthor && targetType === 'column'" class="card" style="padding: 12px 20px; display: flex; justify-content: space-between; align-items: center;">
                <div style="font-size: 13px; color: var(--text-muted);">
                    <span>创作者: <strong style="color: var(--profile-name-color);">{{ parentAuthor.name }}</strong></span>
                    <span style="margin: 0 8px;">➔</span>
                    <span style="color: var(--cyan); font-weight: 600;">专栏: 《{{ currentColumn ? currentColumn.title : '专栏文章' }}》</span>
                </div>
                <button @click="returnToAuthor" class="btn btn-outline btn-sm">
                    ⬅️ 返回创作者全量列表
                </button>
            </div>

            <!-- Author Profile Banner -->
            <section v-if="authorInfo && targetType === 'author'" class="card" style="padding: 20px;">
                <div class="profile-banner">
                    <div class="profile-left">
                        <img :src="authorInfo.avatar_url || 'https://picx.zhimg.com/a4e7052e4958603230a623ebb569533a_l.jpg'" class="profile-avatar">
                        <div>
                            <div class="profile-name">
                                <span>{{ authorInfo.name }}</span>
                                <a :href="authorInfo.profile_url" target="_blank" style="color: var(--cyan); font-size: 13px; text-decoration: none;">🔗 主页</a>
                            </div>
                            <div class="profile-headline">{{ authorInfo.headline || '暂无签名' }}</div>
                        </div>
                    </div>
                    <div class="profile-stats">
                        <div>
                            <div class="stat-label">文章</div>
                            <div class="stat-value">{{ authorInfo.articles_count || 0 }}</div>
                        </div>
                        <div>
                            <div class="stat-label">想法</div>
                            <div class="stat-value" style="color: #fbbf24;">{{ authorInfo.pins_count || countPins }}</div>
                        </div>
                        <div>
                            <div class="stat-label">问答</div>
                            <div class="stat-value">{{ authorInfo.answers_count || 0 }}</div>
                        </div>
                        <div>
                            <div class="stat-label">专栏</div>
                            <div class="stat-value">{{ columnsList.length || authorInfo.columns_count || 0 }}</div>
                        </div>
                    </div>
                </div>

                <!-- Author Columns Grid -->
                <div v-if="columnsList.length > 0" class="columns-container">
                    <div class="columns-header">
                        <span>📚 创作者专栏列表 (共 {{ columnsList.length }} 个专栏，点击即可直接穿透进入)：</span>
                    </div>
                    <div class="columns-grid">
                        <div v-for="col in columnsList" :key="col.id" class="column-card">
                            <div>
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                                    <span class="column-card-title">{{ col.title }}</span>
                                    <span class="column-badge">{{ col.articles_count ? col.articles_count + ' 篇' : '专栏' }}</span>
                                </div>
                                <div class="column-card-desc">{{ col.description || '暂无专栏简介' }}</div>
                            </div>
                            <div class="column-card-footer">
                                <a :href="col.url" target="_blank" style="color: var(--text-subtle); font-size: 12px; text-decoration: none;">知乎原文 ↗</a>
                                <button @click="enterColumn(col)" class="btn btn-primary btn-sm">
                                    📂 进入此专栏下载 ➔
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Column Profile Banner -->
            <section v-if="currentColumn && targetType === 'column'" class="card" style="padding: 20px;">
                <div class="profile-banner" style="border-color: #7c3aed;">
                    <div class="profile-left">
                        <div style="width: 50px; height: 50px; border-radius: 12px; background: rgba(168,85,247,0.2); display: flex; align-items: center; justify-content: center; font-size: 24px;">
                            📚
                        </div>
                        <div>
                            <div class="profile-name" style="color: #c084fc;">
                                <span>《{{ currentColumn.title }}》</span>
                                <a :href="'https://www.zhihu.com/column/' + currentColumn.id" target="_blank" style="color: #a855f7; font-size: 13px; text-decoration: none;">🔗 知乎专栏</a>
                            </div>
                            <div class="profile-headline">{{ currentColumn.description || '暂无简介' }}</div>
                        </div>
                    </div>
                    <div class="profile-stats">
                        <div>
                            <div class="stat-label">本专栏文章</div>
                            <div class="stat-value" style="color: #c084fc;">{{ items.length }} 篇</div>
                        </div>
                        <div v-if="currentColumn.author && currentColumn.author.name">
                            <div class="stat-label">创建者</div>
                            <div class="stat-value" style="color: var(--text-main); font-size: 14px;">{{ currentColumn.author.name }}</div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Checklist & Filter Section -->
            <section v-if="items.length > 0" class="card">
                <!-- Header with Action -->
                <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid var(--toolbar-border);">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <h2 style="font-size: 16px; font-weight: 600; color: var(--h2-color);">
                            📋 第二步：分类过滤与批量勾选存证
                        </h2>
                        <span style="font-size: 12px; background: rgba(6, 182, 212, 0.15); color: var(--cyan); border: 1px solid rgba(6, 182, 212, 0.3); padding: 2px 10px; border-radius: 9999px;">
                            总条目 {{ items.length }} 条 | 当前匹配 {{ filteredItems.length }} 条 | 已勾选 {{ selectedCount }} 项
                        </span>
                    </div>

                    <div>
                        <button @click="startBatchScrape" :disabled="selectedCount === 0 || scraping" class="btn btn-emerald" style="padding: 10px 22px; font-size: 14px;">
                            <span v-if="scraping">⏳ 正在存证中...</span>
                            <span v-else>🚀 开始批量存证 (选定 {{ selectedCount }} 项，含 EPUB)</span>
                        </button>
                    </div>
                </div>

                <!-- Category Filtering Toolbar -->
                <div style="background: var(--toolbar-bg); border: 1px solid var(--toolbar-border); border-radius: 12px; padding: 14px 16px; margin-bottom: 16px; display: flex; flex-direction: column; gap: 12px;">
                    
                    <!-- Type Pills -->
                    <div>
                        <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">🏷️ 内容分类独立筛选：</span>
                        <div class="filter-pills">
                            <button @click="activeCategory = 'all'" :class="['filter-pill', activeCategory === 'all' ? 'active' : '']">
                                🌟 全部 ({{ items.length }})
                            </button>
                            <button @click="activeCategory = 'article'" :class="['filter-pill', activeCategory === 'article' ? 'active' : '']">
                                📰 仅文章 ({{ countArticles }})
                            </button>
                            <button @click="activeCategory = 'pin'" :class="['filter-pill', activeCategory === 'pin' ? 'active' : '']">
                                💡 仅想法 ({{ countPins }})
                            </button>
                            <button @click="activeCategory = 'activity'" :class="['filter-pill', activeCategory === 'activity' ? 'active' : '']">
                                ⚡ 仅动态全部 ({{ countActivities }})
                            </button>
                            <button @click="activeCategory = 'activity_article'" :class="['filter-pill', activeCategory === 'activity_article' ? 'active' : '']">
                                🎯 动态中的文章 ({{ countActivityArticles }})
                            </button>
                            <button @click="activeCategory = 'answer'" :class="['filter-pill', activeCategory === 'answer' ? 'active' : '']">
                                💬 仅回答 ({{ countAnswers }})
                            </button>
                            <button @click="activeCategory = 'column'" :class="['filter-pill', activeCategory === 'column' ? 'active' : '']">
                                📚 仅专栏 ({{ countColumns }})
                            </button>
                        </div>
                    </div>

                    <!-- Date & Keyword Filter -->
                    <div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding-top: 10px; border-top: 1px solid var(--toolbar-divider);">
                        <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px;">
                            <span style="font-size: 13px; font-weight: 600; color: var(--cyan);">📅 时间线:</span>
                            <input type="date" v-model="filterStartDate" style="padding: 6px 10px; background: var(--input-date-bg); border: 1px solid var(--input-date-border); color: var(--text-main); border-radius: 6px; font-size: 12px;" title="起始日期">
                            <span style="color: var(--text-subtle);">至</span>
                            <input type="date" v-model="filterEndDate" style="padding: 6px 10px; background: var(--input-date-bg); border: 1px solid var(--input-date-border); color: var(--text-main); border-radius: 6px; font-size: 12px;" title="截止日期">
                            <input type="text" v-model="searchKeyword" placeholder="🔍 关键词实时过滤..." style="padding: 6px 12px; background: var(--input-date-bg); border: 1px solid var(--input-date-border); color: var(--text-main); border-radius: 6px; font-size: 12px; width: 180px;">
                        </div>

                        <div style="display: flex; align-items: center; gap: 8px;">
                            <button @click="toggleSortOrder" class="btn btn-outline" style="padding: 6px 12px; font-size: 12px;">
                                {{ sortOrder === 'desc' ? '⬇️ 最新在前 (倒序)' : '⬆️ 最早在前 (正序)' }}
                            </button>
                        </div>
                    </div>

                    <!-- Bulk Selection Actions -->
                    <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-top: 10px; border-top: 1px solid var(--toolbar-divider);">
                        <button @click="selectAllFiltered" class="btn btn-emerald btn-sm" style="font-weight: 600;">
                            ✨ 勾选当前筛选分类全部 ({{ filteredItems.length }}项)
                        </button>
                        <button @click="selectAllGlobal" class="btn btn-outline btn-sm">
                            🌟 全选所有内容 ({{ items.length }}项)
                        </button>
                        <button @click="unselectAll" class="btn btn-outline btn-sm">❌ 取消全选</button>
                        <span style="color: var(--text-subtle); margin: 0 4px;">|</span>
                        <button @click="selectTopN(20)" class="btn btn-outline btn-sm">选前20项</button>
                        <button @click="selectTopN(50)" class="btn btn-outline btn-sm">选前50项</button>
                        <button @click="selectTopN(100)" class="btn btn-outline btn-sm">选前100项</button>
                    </div>
                </div>

                <!-- Table -->
                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th style="width: 40px; text-align: center;">
                                    <input type="checkbox" :checked="isAllFilteredSelected" @change="toggleSelectAllFiltered" style="width: 16px; height: 16px; accent-color: var(--cyan); cursor: pointer;">
                                </th>
                                <th style="width: 110px;">分类/类型</th>
                                <th>标题 / 动态动向 / 内容摘要</th>
                                <th style="width: 150px; text-align: center; cursor: pointer;" @click="toggleSortOrder" title="点击切换时间正反序">
                                    📅 发布时间 {{ sortOrder === 'desc' ? '▼' : '▲' }}
                                </th>
                                <th style="width: 130px; text-align: center;">互动数据</th>
                                <th style="width: 90px; text-align: center;">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="it in filteredItems" :key="it.id">
                                <td style="text-align: center;">
                                    <input type="checkbox" v-model="it.selected" style="width: 16px; height: 16px; accent-color: var(--cyan); cursor: pointer;">
                                </td>
                                <td>
                                    <span v-if="it.action_text" class="badge badge-act">
                                        {{ it.action_text }}
                                    </span>
                                    <span :class="'badge badge-' + it.type">
                                        {{ it.type === 'article' ? '文章' : it.type === 'answer' ? '回答' : it.type === 'column' ? '专栏' : '想法' }}
                                    </span>
                                </td>
                                <td>
                                    <div style="font-weight: 600; color: var(--tr-title); margin-bottom: 2px;">
                                        <a :href="it.url" target="_blank" style="color: inherit; text-decoration: none;">{{ it.raw_title || it.title }}</a>
                                    </div>
                                    <div v-if="it.excerpt" style="font-size: 12px; color: var(--text-subtle); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 650px;">
                                        {{ it.excerpt }}
                                    </div>
                                </td>
                                <td style="text-align: center; color: var(--tr-date); font-size: 12px; font-family: monospace;">
                                    {{ it.created_at || it.created_date || '—' }}
                                </td>
                                <td style="text-align: center; color: var(--text-muted); font-size: 12px;">
                                    <template v-if="it.type === 'column'">
                                        <span style="color: #c084fc;">📚 {{ it.articles_count || 0 }} 篇</span>
                                    </template>
                                    <template v-else>
                                        <span>👍 {{ it.voteup_count || 0 }}</span>
                                        <span style="margin-left: 8px;">💬 {{ it.comment_count || 0 }}</span>
                                    </template>
                                </td>
                                <td style="text-align: center;">
                                    <button v-if="it.type === 'column'" @click="enterColumn(it)" class="btn btn-primary btn-sm">
                                        📂 进入
                                    </button>
                                    <a v-else :href="it.url" target="_blank" style="color: #38bdf8; font-size: 12px; text-decoration: none;">
                                        知乎 ↗
                                    </a>
                                </td>
                            </tr>
                            <tr v-if="filteredItems.length === 0">
                                <td colspan="6" style="text-align: center; color: #64748b; padding: 30px;">
                                    ⚠️ 当前分类或筛选条件下未检索到匹配条目，请调整分类或重置时间线。
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- Real-time Progress & Dual Download Card -->
            <section v-if="activeJob" class="card progress-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="font-size: 16px; font-weight: 700; color: var(--text-title); display: flex; align-items: center; gap: 8px;">
                        <span v-if="activeJob.status === 'running'">🔄</span>
                        <span v-else>✅</span>
                        <span>任务状态: {{ activeJob.message }}</span>
                    </h3>
                    <span style="font-size: 16px; font-weight: 700; color: var(--cyan);">{{ activeJob.progress }}%</span>
                </div>

                <!-- Progress Bar -->
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" :style="{ width: activeJob.progress + '%' }"></div>
                </div>

                <!-- Terminal Log -->
                <div class="terminal-log">
                    <div v-for="(log, idx) in activeJob.logs" :key="idx">{{ log }}</div>
                </div>

                <!-- Dual Download Actions -->
                <div v-if="activeJob.status === 'completed'" style="display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 14px; margin-top: 18px;">
                    <a :href="'/api/jobs/' + activeJob.job_id + '/download_epub'" class="btn btn-purple" style="padding: 12px 24px; font-size: 14px; font-weight: 700;">
                        📖 点击下载精美电子书 (EPUB)
                    </a>
                    <a :href="'/api/jobs/' + activeJob.job_id + '/download'" class="btn btn-emerald" style="padding: 12px 24px; font-size: 14px; font-weight: 700;">
                        📦 点击下载完整证据包 (ZIP)
                    </a>
                </div>
            </section>

        </div>
    </div>

    <script>
        function initApp() {
            if (typeof Vue === 'undefined') {
                setTimeout(initApp, 100);
                return;
            }
            const { createApp, ref, computed, onMounted } = Vue;

            createApp({
                setup() {
                    const theme = ref(localStorage.getItem('theme_mode') || 'dark');
                    const applyTheme = (t) => {
                        theme.value = t;
                        localStorage.setItem('theme_mode', t);
                        document.documentElement.setAttribute('data-theme', t);
                    };
                    const toggleTheme = () => {
                        applyTheme(theme.value === 'dark' ? 'light' : 'dark');
                    };

                    const isAuthenticated = ref(false);
                    const loginPassword = ref('');
                    const loggingIn = ref(false);
                    const loginError = ref('');

                    const targetUrl = ref('');
                    const cookie = ref(localStorage.getItem('zhihu_cookie') || '');
                    const fetchLimit = ref(0);
                    const filterStartDate = ref('');
                    const filterEndDate = ref('');
                    const searchKeyword = ref('');
                    const sortOrder = ref('desc');
                    const activeCategory = ref('all');

                    const options = ref({
                        save_markdown: true,
                        save_comments: true,
                        save_screenshot: true,
                        highlight_keywords: []
                    });
                    const inspecting = ref(false);
                    const scraping = ref(false);
                    const targetType = ref('');
                    const authorInfo = ref(null);
                    const currentColumn = ref(null);
                    const columnsList = ref([]);
                    const parentAuthor = ref(null);
                    const items = ref([]);
                    const activeJob = ref(null);

                    // Credential Helper State
                    const showCredentialModal = ref(false);
                    const detectingCookie = ref(false);
                    const detectMsg = ref('');
                    const detectSuccess = ref(false);
                    const snippetCopied = ref(false);
                    const cookieStatus = ref(null);
                    const showCookie = ref(false);

                    const getAuthHeader = () => {
                        const token = localStorage.getItem('site_auth_token');
                        return token ? { 'X-Auth-Token': token } : {};
                    };

                    const openCredentialModal = () => {
                        showCredentialModal.value = true;
                        detectMsg.value = '';
                        snippetCopied.value = false;
                    };

                    const handleCookieInput = () => {
                        localStorage.setItem('zhihu_cookie', cookie.value);
                        if (!cookie.value.trim()) {
                            cookieStatus.value = null;
                            return;
                        }
                        const m = cookie.value.match(/z_c0="?([^";\\s]+)"?/);
                        if (m) {
                            cookieStatus.value = {
                                valid: true,
                                message: `成功识别知乎凭证 (z_c0: ${m[1].substring(0, 12)}...)`
                            };
                        } else if (cookie.value.startsWith('2|') || (cookie.value.length > 40 && !cookie.value.includes('='))) {
                            cookie.value = `z_c0=${cookie.value.trim()}`;
                            localStorage.setItem('zhihu_cookie', cookie.value);
                            cookieStatus.value = {
                                valid: true,
                                message: `已自动封装有效 z_c0 凭证`
                            };
                        } else {
                            cookieStatus.value = {
                                valid: false,
                                message: `已填入凭证，若遇知乎限流建议包含 z_c0=...`
                            };
                        }
                    };

                    const autoDetectLocalCookie = async () => {
                        detectingCookie.value = true;
                        detectMsg.value = '正在扫描电脑已保存的知乎登录凭证...';
                        detectSuccess.value = false;
                        try {
                            const res = await fetch('/api/cookie/auto-detect', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    ...getAuthHeader()
                                }
                            });
                            const data = await res.json();
                            if (data.ok && data.cookie) {
                                cookie.value = data.cookie;
                                detectSuccess.value = true;
                                detectMsg.value = `🎉 ${data.message || '读取成功！'}`;
                                handleCookieInput();
                                setTimeout(() => {
                                    showCredentialModal.value = false;
                                }, 1200);
                            } else {
                                detectSuccess.value = false;
                                detectMsg.value = data.message || '未检测到可用登录态，请使用方式二！';
                            }
                        } catch (e) {
                            detectSuccess.value = false;
                            detectMsg.value = '请求失败，建议使用方式二！';
                        } finally {
                            detectingCookie.value = false;
                        }
                    };

                    const copySnippet = async () => {
                        const text = 'copy(document.cookie)';
                        try {
                            await navigator.clipboard.writeText(text);
                            snippetCopied.value = true;
                            setTimeout(() => { snippetCopied.value = false; }, 3000);
                        } catch (e) {
                            const ta = document.createElement('textarea');
                            ta.value = text;
                            document.body.appendChild(ta);
                            ta.select();
                            document.execCommand('copy');
                            document.body.removeChild(ta);
                            snippetCopied.value = true;
                            setTimeout(() => { snippetCopied.value = false; }, 3000);
                        }
                    };

                    const pasteFromClipboard = async () => {
                        try {
                            const text = await navigator.clipboard.readText();
                            if (text && text.trim()) {
                                cookie.value = text.trim();
                                handleCookieInput();
                                showCredentialModal.value = false;
                                alert('🎉 已自动读取剪贴板凭证并填入！');
                            } else {
                                alert('剪贴板为空，请先在知乎控制台粘贴口诀并按回车！');
                            }
                        } catch (e) {
                            const manual = prompt('无法直接读取剪贴板（可能未开启剪贴板权限），请在此粘贴 (Ctrl+V)：');
                            if (manual && manual.trim()) {
                                cookie.value = manual.trim();
                                handleCookieInput();
                                showCredentialModal.value = false;
                            }
                        }
                    };

                    const openZhihuPopup = () => {
                        window.open('https://www.zhihu.com/signin', 'zhihu_login_popup', 'width=540,height=680,top=100,left=300');
                    };

                    // Check Auth Status on Mount
                    onMounted(async () => {
                        const savedToken = localStorage.getItem('site_auth_token');
                        try {
                            const res = await fetch('/api/auth/status', {
                                headers: savedToken ? { 'X-Auth-Token': savedToken } : {}
                            });
                            const data = await res.json();
                            if (data.authenticated) {
                                isAuthenticated.value = true;
                            }
                        } catch (e) {
                            console.error('Auth check error:', e);
                        }
                        if (cookie.value) {
                            handleCookieInput();
                        }
                    });

                    const handleLogin = async () => {
                        if (!loginPassword.value.trim()) {
                            loginError.value = '请输入密码';
                            return;
                        }
                        loggingIn.value = true;
                        loginError.value = '';
                        try {
                            const res = await fetch('/api/auth/login', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ password: loginPassword.value.trim() })
                            });
                            const data = await res.json();
                            if (res.ok && data.ok) {
                                localStorage.setItem('site_auth_token', data.token);
                                isAuthenticated.value = true;
                            } else {
                                loginError.value = data.detail || '密码错误，请重新输入';
                            }
                        } catch (e) {
                            loginError.value = '请求失败: ' + e.message;
                        } finally {
                            loggingIn.value = false;
                        }
                    };

                    const handleLogout = () => {
                        localStorage.removeItem('site_auth_token');
                        document.cookie = 'site_auth_token=; Max-Age=0; path=/;';
                        isAuthenticated.value = false;
                        loginPassword.value = '';
                    };

                    // Counts
                    const countArticles = computed(() => items.value.filter(i => i.type === 'article').length);
                    const countPins = computed(() => items.value.filter(i => i.type === 'pin').length);
                    const countAnswers = computed(() => items.value.filter(i => i.type === 'answer').length);
                    const countColumns = computed(() => items.value.filter(i => i.type === 'column').length);
                    const countActivities = computed(() => items.value.filter(i => i.is_activity).length);
                    const countActivityArticles = computed(() => items.value.filter(i => i.is_activity && i.type === 'article').length);

                    const filteredItems = computed(() => {
                        let res = items.value.slice();

                        // 1. Category Filter
                        if (activeCategory.value === 'article') {
                            res = res.filter(i => i.type === 'article');
                        } else if (activeCategory.value === 'pin') {
                            res = res.filter(i => i.type === 'pin');
                        } else if (activeCategory.value === 'activity') {
                            res = res.filter(i => i.is_activity);
                        } else if (activeCategory.value === 'activity_article') {
                            res = res.filter(i => i.is_activity && i.type === 'article');
                        } else if (activeCategory.value === 'answer') {
                            res = res.filter(i => i.type === 'answer');
                        } else if (activeCategory.value === 'column') {
                            res = res.filter(i => i.type === 'column');
                        }

                        // 2. Keyword Filter
                        if (searchKeyword.value.trim()) {
                            const kw = searchKeyword.value.trim().toLowerCase();
                            res = res.filter(i => 
                                (i.title && i.title.toLowerCase().includes(kw)) ||
                                (i.excerpt && i.excerpt.toLowerCase().includes(kw))
                            );
                        }

                        // 3. Date Range Filter
                        if (filterStartDate.value) {
                            res = res.filter(i => {
                                const d = i.created_date || (i.created_at ? i.created_at.slice(0, 10) : '');
                                return !d || d >= filterStartDate.value;
                            });
                        }
                        if (filterEndDate.value) {
                            res = res.filter(i => {
                                const d = i.created_date || (i.created_at ? i.created_at.slice(0, 10) : '');
                                return !d || d <= filterEndDate.value;
                            });
                        }

                        // 4. Sort
                        res.sort((a, b) => {
                            const ta = a.created_timestamp || 0;
                            const tb = b.created_timestamp || 0;
                            return sortOrder.value === 'desc' ? (tb - ta) : (ta - tb);
                        });

                        return res;
                    });

                    const selectedCount = computed(() => {
                        return items.value.filter(i => i.selected).length;
                    });

                    const isAllFilteredSelected = computed(() => {
                        return filteredItems.value.length > 0 && filteredItems.value.every(i => i.selected);
                    });

                    const toggleSelectAllFiltered = () => {
                        const targetState = !isAllFilteredSelected.value;
                        filteredItems.value.forEach(i => i.selected = targetState);
                    };

                    const selectAllFiltered = () => {
                        filteredItems.value.forEach(i => i.selected = true);
                    };

                    const selectAllGlobal = () => {
                        items.value.forEach(i => i.selected = true);
                    };

                    const unselectAll = () => {
                        items.value.forEach(i => i.selected = false);
                    };

                    const selectTopN = (n) => {
                        filteredItems.value.forEach((it, idx) => {
                            it.selected = idx < n;
                        });
                    };

                    const toggleSortOrder = () => {
                        sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc';
                    };

                    const getAuthHeader = () => {
                        const t = localStorage.getItem('site_auth_token');
                        return t ? { 'X-Auth-Token': t } : {};
                    };

                    const inspect = async (urlToInspect) => {
                        const u = (urlToInspect || targetUrl.value).trim();
                        if (!u) {
                            alert('请输入知乎链接');
                            return;
                        }
                        if (cookie.value) {
                            localStorage.setItem('zhihu_cookie', cookie.value);
                        }
                        inspecting.value = true;
                        try {
                            const res = await fetch('/api/inspect', {
                                method: 'POST',
                                headers: { 
                                    'Content-Type': 'application/json',
                                    ...getAuthHeader()
                                },
                                body: JSON.stringify({
                                    url: u,
                                    cookie: cookie.value,
                                    max_items: fetchLimit.value
                                })
                            });
                            if (res.status === 401) {
                                isAuthenticated.value = false;
                                return;
                            }
                            const data = await res.json();
                            if (!res.ok) throw new Error(data.detail || '解析失败');
                            
                            targetType.value = data.target_type || 'author';

                            if (data.target_type === 'column') {
                                currentColumn.value = data.column;
                                items.value = (data.items || []).map(i => ({ ...i, selected: true }));
                            } else {
                                authorInfo.value = data.author || null;
                                columnsList.value = data.columns || (data.items || []).filter(i => i.type === 'column');
                                currentColumn.value = null;
                                items.value = (data.items || []).map(i => ({ ...i, selected: true }));
                            }
                        } catch (e) {
                            alert('检索出错: ' + e.message);
                        } finally {
                            inspecting.value = false;
                        }
                    };

                    const enterColumn = (col) => {
                        if (authorInfo.value) {
                            parentAuthor.value = { ...authorInfo.value, url: targetUrl.value };
                        }
                        targetUrl.value = col.url || ('https://www.zhihu.com/column/' + col.id);
                        inspect(targetUrl.value);
                    };

                    const returnToAuthor = () => {
                        if (parentAuthor.value) {
                            targetUrl.value = parentAuthor.value.url || parentAuthor.value.profile_url;
                            parentAuthor.value = null;
                            inspect(targetUrl.value);
                        }
                    };

                    const startBatchScrape = async () => {
                        const chosen = items.value.filter(i => i.selected);
                        if (chosen.length === 0) return;

                        scraping.value = true;
                        try {
                            const res = await fetch('/api/scrape/batch', {
                                method: 'POST',
                                headers: { 
                                    'Content-Type': 'application/json',
                                    ...getAuthHeader()
                                },
                                body: JSON.stringify({
                                    cookie: cookie.value,
                                    items: chosen,
                                    options: options.value
                                })
                            });
                            if (res.status === 401) {
                                isAuthenticated.value = false;
                                return;
                            }
                            const data = await res.json();
                            if (!res.ok) throw new Error(data.detail || '启动抓取失败');
                            
                            listenProgress(data.job_id);
                        } catch (e) {
                            alert('执行出错: ' + e.message);
                            scraping.value = false;
                        }
                    };

                    const listenProgress = (jobId) => {
                        const evtSource = new EventSource('/api/jobs/' + jobId + '/stream');
                        evtSource.onmessage = (event) => {
                            const data = JSON.parse(event.data);
                            activeJob.value = data;
                            if (data.status === 'completed' || data.status === 'error') {
                                evtSource.close();
                                scraping.value = false;
                            }
                        };
                        evtSource.onerror = () => {
                            evtSource.close();
                            scraping.value = false;
                        };
                    };

                    return {
                        theme,
                        toggleTheme,
                        isAuthenticated,
                        loginPassword,
                        loggingIn,
                        loginError,
                        handleLogin,
                        handleLogout,
                        targetUrl,
                        cookie,
                        showCredentialModal,
                        detectingCookie,
                        detectMsg,
                        detectSuccess,
                        snippetCopied,
                        cookieStatus,
                        showCookie,
                        openCredentialModal,
                        handleCookieInput,
                        autoDetectLocalCookie,
                        copySnippet,
                        pasteFromClipboard,
                        openZhihuPopup,
                        fetchLimit,
                        filterStartDate,
                        filterEndDate,
                        searchKeyword,
                        sortOrder,
                        activeCategory,
                        countArticles,
                        countPins,
                        countAnswers,
                        countColumns,
                        countActivities,
                        countActivityArticles,
                        filteredItems,
                        options,
                        inspecting,
                        scraping,
                        targetType,
                        authorInfo,
                        currentColumn,
                        columnsList,
                        parentAuthor,
                        items,
                        activeJob,
                        selectedCount,
                        isAllFilteredSelected,
                        toggleSelectAllFiltered,
                        selectAllFiltered,
                        selectAllGlobal,
                        unselectAll,
                        selectTopN,
                        toggleSortOrder,
                        inspect,
                        enterColumn,
                        returnToAuthor,
                        startBatchScrape
                    };
                }
            }).mount('#app');
        }
        initApp();
    </script>
</body>
</html>
"""


def main():
    """CLI launcher for local web server."""
    port = int(os.environ.get("PORT", 8775))
    print(f"🚀 知乎定向排查与存证 Web 交互系统已启动: http://127.0.0.1:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
