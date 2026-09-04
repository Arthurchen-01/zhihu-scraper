"""Zhihu Self-Service Web Application.
Provides interactive URL inspection, author/column drill-down, checklist selection,
real-time SSE progress bar, full-text download, comment scraping, Playwright screenshotting,
and reliable FileResponse ZIP packaging.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zhihu_scraper.web")

app = FastAPI(title="Zhihu Investigator & Scraper Web App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory store for background scraping jobs
JOBS: Dict[str, Dict[str, Any]] = {}


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


@app.post("/api/inspect")
def inspect_target(req: InspectRequest):
    """Inspects any author profile, column, or link and catalogs all child assets."""
    client = ZhihuClient(cookie=req.cookie or "")
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
        # 0 or None means unlimited full pagination (download ALL articles)
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
            max_per_category=limit or 50
        )
        catalog["target_type"] = "author"
        return catalog
    except Exception as e:
        logger.error("Error inspecting %s: %s", url, e)
        raise HTTPException(status_code=500, detail=f"解析知乎资产失败: {str(e)}")


def run_batch_job(job_id: str, cookie: str, items: List[Dict[str, Any]], options: Dict[str, Any]):
    """Background task executing the selected batch scraping with physical ZIP persistence."""
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

    total = len(items)
    for idx, item in enumerate(items, 1):
        item_type = item.get("type", "article")
        item_id = str(item.get("id"))
        title = item.get("title", f"item_{item_id}")
        url = item.get("url", "")

        msg = f"[{idx}/{total}] 正在抓取 ({item_type}): 《{title[:30]}》"
        job["current"] = idx
        job["progress"] = int((idx / total) * 100)
        job["current_message"] = msg
        job["logs"].append(f"{time.strftime('%H:%M:%S')} - {msg}")

        # Handle column item if selected directly
        if item_type == "column":
            try:
                col_sub_dir = articles_dir / f"column_{safe_name(title)}"
                sub_arts = col_scraper.list_column_articles(item_id, max_items=50)
                job["logs"].append(f"{time.strftime('%H:%M:%S')} - 专栏内包含 {len(sub_arts)} 篇，正在同步批量抓取...")
                for s_idx, s_art in enumerate(sub_arts, 1):
                    s_id = s_art["id"]
                    if save_markdown:
                        article_scraper.scrape(s_id, save_dir=col_sub_dir)
                    if save_comments:
                        c_path = comments_dir / f"comments_article_{s_id}.json"
                        comment_scraper.scrape_comment_tree("article", s_id, save_path=c_path)
            except Exception as e:
                job["logs"].append(f"{time.strftime('%H:%M:%S')} - ⚠️ 专栏批量抓取异常: {e}")
            continue

        # 1. Scrape Content
        if save_markdown:
            try:
                if item_type == "article":
                    article_scraper.scrape(item_id, save_dir=articles_dir)
                elif item_type == "answer":
                    answer_scraper.scrape(item_id, save_dir=articles_dir)
                elif item_type == "pin":
                    pin_scraper.scrape(item_id, save_dir=articles_dir)
            except Exception as e:
                job["logs"].append(f"{time.strftime('%H:%M:%S')} - ⚠️ 正文抓取异常: {e}")

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
                img_path = screenshots_dir / f"screenshot_{item_type}_{safe_name(title)}_{item_id}.png"
                visual_archiver.capture_screenshot(
                    url,
                    output_path=img_path,
                    highlight_keywords=highlight_kws
                )
            except Exception as e:
                job["logs"].append(f"{time.strftime('%H:%M:%S')} - ⚠️ 截图异常: {e}")

        time.sleep(0.3)

    # Package as physical ZIP file on disk for 100% reliable streaming
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
    job["current_message"] = "🎉 全部选定任务存证完毕！可以点击下载压缩包。"
    job["logs"].append(f"{time.strftime('%H:%M:%S')} - 全部完成！ZIP 文件已生成 ({job['zip_size'] / (1024*1024):.2f} MB)。")


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
        "zip_path": None
    }

    bg_tasks.add_task(run_batch_job, job_id, req.cookie or "", req.items, req.options or {})
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
                "logs": job.get("logs", [])[-20:]
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if job["status"] in ["completed", "error"]:
                break
            await asyncio.sleep(0.8)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/download")
def download_job_zip(job_id: str):
    """Download the finalized ZIP containing all articles, comments, and screenshots via FileResponse."""
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


@app.get("/", response_class=HTMLResponse)
def index_ui():
    """Renders the comprehensive self-service Web UI with standalone, robust styling."""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知乎创作者定向排查与批量存证工具箱</title>
    <!-- Robust CSS Grid / Modern Glassmorphism Styling (Self-Contained, Zero Failure) -->
    <style>
        :root {
            --bg-base: #0b0f19;
            --card-bg: #151d30;
            --card-border: #222f4c;
            --text-main: #e2e8f0;
            --text-muted: #94a3b8;
            --cyan: #06b6d4;
            --cyan-glow: rgba(6, 182, 212, 0.25);
            --emerald: #10b981;
            --emerald-glow: rgba(16, 185, 129, 0.25);
            --purple: #a855f7;
            --blue: #3b82f6;
            --amber: #f59e0b;
            --rose: #f43f5e;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            padding: 24px 16px;
        }
        .container { max-width: 1140px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }

        /* Card Styles */
        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }

        /* Header */
        header.card {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            background: linear-gradient(135deg, #151d30 0%, #1a2540 100%);
            border-color: #2a3b61;
        }
        h1 { font-size: 22px; font-weight: 700; color: #38bdf8; display: flex; align-items: center; gap: 10px; }
        .subtitle { color: var(--text-muted); font-size: 13px; margin-top: 4px; }
        .badge-status {
            font-size: 12px;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 6px 14px;
            border-radius: 9999px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-weight: 500;
        }

        /* Form Inputs */
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        @media (max-width: 768px) { .grid-2 { grid-template-columns: 1fr; } }
        label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; font-weight: 500; }
        input[type="text"], input[type="password"] {
            width: 100%;
            background: #090e18;
            border: 1px solid #253352;
            border-radius: 10px;
            padding: 12px 16px;
            color: #f8fafc;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        input[type="text"]:focus, input[type="password"]:focus {
            border-color: var(--cyan);
            box-shadow: 0 0 0 3px var(--cyan-glow);
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
            border-top: 1px solid #1e293b;
        }
        .checkbox-group { display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px; color: #cbd5e1; }
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
        .btn-outline {
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid #334155;
            padding: 6px 12px;
            font-size: 12px;
        }
        .btn-outline:hover { background: #334155; color: #ffffff; }
        .btn-sm { padding: 6px 12px; font-size: 12px; border-radius: 8px; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; }

        /* Author & Column Banners */
        .profile-banner {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            background: #131b2e;
            border: 1px solid #233252;
            border-radius: 14px;
            padding: 20px;
        }
        .profile-left { display: flex; align-items: center; gap: 16px; }
        .profile-avatar { width: 60px; height: 60px; border-radius: 50%; border: 2px solid #38bdf8; object-fit: cover; }
        .profile-name { font-size: 18px; font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 8px; }
        .profile-headline { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
        .profile-stats { display: flex; gap: 24px; text-align: center; }
        .stat-label { font-size: 11px; color: var(--text-muted); }
        .stat-value { font-size: 17px; font-weight: 700; color: #38bdf8; }

        /* Column Showcase Grid */
        .columns-container { margin-top: 16px; }
        .columns-header { font-size: 14px; font-weight: 600; color: #cbd5e1; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
        .columns-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 14px;
        }
        .column-card {
            background: #0d1424;
            border: 1px solid #212e4a;
            border-radius: 12px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.2s ease;
        }
        .column-card:hover {
            border-color: #38bdf8;
            box-shadow: 0 4px 20px var(--cyan-glow);
            transform: translateY(-2px);
        }
        .column-card-title { font-size: 14px; font-weight: 700; color: #e0f2fe; margin-bottom: 6px; }
        .column-card-desc { font-size: 12px; color: #94a3b8; line-height: 1.4; margin-bottom: 12px; flex-grow: 1; }
        .column-card-footer { display: flex; justify-content: space-between; align-items: center; }
        .column-badge { font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 6px; background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }

        /* Breadcrumb Bar */
        .breadcrumb-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #0d1527;
            border: 1px solid #233357;
            border-radius: 10px;
            padding: 10px 16px;
            font-size: 13px;
        }
        .breadcrumb-text { color: #94a3b8; display: flex; align-items: center; gap: 8px; }
        .breadcrumb-active { color: #38bdf8; font-weight: 600; }

        /* Checklist Table */
        .table-wrap {
            overflow-x: auto;
            border: 1px solid #1e293b;
            border-radius: 12px;
            background: #090e18;
            margin-top: 14px;
        }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
        thead th {
            background: #0f172a;
            color: #94a3b8;
            padding: 12px 14px;
            font-weight: 600;
            border-bottom: 1px solid #1e293b;
            white-space: nowrap;
        }
        tbody tr { border-bottom: 1px solid #141f36; transition: background 0.15s; }
        tbody tr:hover { background: rgba(30, 41, 59, 0.5); }
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
        .badge-article { background: rgba(6, 182, 212, 0.15); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.3); }
        .badge-answer { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
        .badge-column { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }
        .badge-pin { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }

        /* Progress Card */
        .progress-card {
            border-color: #0284c7;
            background: linear-gradient(180deg, #111b2e 0%, #0d1527 100%);
            box-shadow: 0 10px 35px rgba(2, 132, 199, 0.25);
        }
        .progress-bar-bg { width: 100%; height: 12px; background: #090e18; border-radius: 9999px; overflow: hidden; border: 1px solid #1e293b; margin: 12px 0; }
        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #06b6d4 0%, #10b981 100%);
            border-radius: 9999px;
            transition: width 0.3s ease;
        }
        .terminal-log {
            background: #050811;
            border: 1px solid #141f36;
            border-radius: 10px;
            padding: 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 11px;
            color: #94a3b8;
            height: 150px;
            overflow-y: auto;
            line-height: 1.6;
        }
        .bounce-btn {
            animation: bounce 2s infinite;
        }
        @keyframes bounce {
            0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-6px); }
            60% { transform: translateY(-3px); }
        }
    </style>
    <!-- Local Static Vue 3 with CDN Fallbacks -->
    <script src="/static/vue.global.prod.js" onerror="this.onerror=null;this.src='https://cdnjs.cloudflare.com/ajax/libs/vue/3.3.4/vue.global.prod.js';"></script>
</head>
<body>
    <div id="app" class="container">
        
        <!-- Header -->
        <header class="card">
            <div>
                <h1>🎯 知乎创作者定向排查与批量存证工具箱</h1>
                <p class="subtitle">支持创作者全量资产检索、专栏一键穿透下钻、文章勾选、楼中楼评论与现场高清长截图存证</p>
            </div>
            <div class="badge-status">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: #34d399; display: inline-block;"></span>
                <span>自动化引擎就绪 (Playwright + Zhihu API)</span>
            </div>
        </header>

        <!-- Configuration Form Card -->
        <section class="card">
            <h2 style="font-size: 16px; font-weight: 600; color: #f1f5f9; margin-bottom: 16px;">
                ⚙️ 第一步：输入知乎链接与操作凭证
            </h2>
            
            <div style="display: grid; grid-template-columns: 2fr 2fr 1.2fr; gap: 14px;">
                <div>
                    <label>目标知乎主页或专栏链接 (必填)</label>
                    <input v-model="targetUrl" type="text" placeholder="例: https://www.zhihu.com/people/shan-chang-qing-yi 或 /column/c_xxx">
                </div>
                <div>
                    <label>知乎 Cookie 凭证 (选填/粘贴本人 Cookie 避免限流)</label>
                    <input v-model="cookie" type="password" placeholder="粘贴你的知乎 Cookie (包含 z_c0=...)">
                </div>
                <div>
                    <label>检索深度 / 数量上限</label>
                    <select v-model="fetchLimit" style="width: 100%; height: 44px; background: #090e18; border: 1px solid #253352; color: #f8fafc; border-radius: 10px; padding: 0 10px; font-size: 13px;">
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
                        <span>抓取正文 (Markdown 格式化)</span>
                    </label>
                    <label class="checkbox-label">
                        <input type="checkbox" v-model="options.save_comments">
                        <span>抓取楼中楼评论 (.json 树)</span>
                    </label>
                    <label class="checkbox-label">
                        <input type="checkbox" v-model="options.save_screenshot">
                        <span>Playwright 原生高清长截图 (.png)</span>
                    </label>
                </div>

                <button @click="inspect(targetUrl)" :disabled="inspecting" class="btn btn-primary">
                    <span v-if="inspecting">🔄 正在检索资产...</span>
                    <span v-else>🔍 检索目标已有资产</span>
                </button>
            </div>
        </section>

        <!-- Breadcrumb Bar (when viewing a column from an author) -->
        <div v-if="parentAuthor && targetType === 'column'" class="breadcrumb-bar">
            <div class="breadcrumb-text">
                <span>创作者: <strong>{{ parentAuthor.name }}</strong></span>
                <span>➔</span>
                <span class="breadcrumb-active">专栏: 《{{ currentColumn ? currentColumn.title : '专栏文章' }}》</span>
            </div>
            <button @click="returnToAuthor" class="btn btn-outline">
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
                            <a :href="authorInfo.profile_url" target="_blank" style="color: #38bdf8; font-size: 13px; text-decoration: none;">🔗 主页</a>
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
                        <div class="stat-label">问答</div>
                        <div class="stat-value">{{ authorInfo.answers_count || 0 }}</div>
                    </div>
                    <div>
                        <div class="stat-label">想法</div>
                        <div class="stat-value">{{ authorInfo.pins_count || 0 }}</div>
                    </div>
                    <div>
                        <div class="stat-label">专栏</div>
                        <div class="stat-value">{{ columnsList.length || authorInfo.columns_count || 0 }}</div>
                    </div>
                </div>
            </div>

            <!-- Author Columns Showcase (点进专栏核心入口) -->
            <div v-if="columnsList.length > 0" class="columns-container">
                <div class="columns-header">
                    <span>📚 创作者专栏列表 (共 {{ columnsList.length }} 个专栏，点击即可直接进入专栏文章库)：</span>
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
                            <a :href="col.url" target="_blank" style="color: #64748b; font-size: 12px; text-decoration: none;">知乎原文 ↗</a>
                            <button @click="enterColumn(col)" class="btn btn-primary btn-sm">
                                📂 点进此专栏下载 ➔
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Column Profile Banner (when target is a Column) -->
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
                        <div class="stat-value" style="color: #cbd5e1; font-size: 14px;">{{ currentColumn.author.name }}</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Checklist Section -->
        <section v-if="items.length > 0" class="card">
            <!-- Header with dynamic counts -->
            <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid #1e293b;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <h2 style="font-size: 16px; font-weight: 600; color: #f1f5f9;">
                        📋 第二步：勾选需要存证的条目
                    </h2>
                    <span style="font-size: 12px; background: rgba(6, 182, 212, 0.2); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.3); padding: 2px 10px; border-radius: 9999px;">
                        总资产 {{ items.length }} 条 | 时间线匹配 {{ filteredItems.length }} 条 | 已勾选 {{ selectedCount }} 项
                    </span>
                </div>

                <!-- Scraping Action Button -->
                <div>
                    <button @click="startBatchScrape" :disabled="selectedCount === 0 || scraping" class="btn btn-emerald" style="padding: 10px 22px; font-size: 14px;">
                        <span v-if="scraping">⏳ 正在存证中...</span>
                        <span v-else>🚀 开始批量存证已选项 (共 {{ selectedCount }} 项)</span>
                    </button>
                </div>
            </div>

            <!-- Timeline Filter Toolbar -->
            <div style="background: #090e18; border: 1px solid #1e293b; border-radius: 12px; padding: 14px 16px; margin-bottom: 16px; display: flex; flex-direction: column; gap: 12px;">
                <div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px;">
                    <!-- Date Inputs & Search -->
                    <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px;">
                        <span style="font-size: 13px; font-weight: 600; color: #38bdf8;">📅 时间线筛选:</span>
                        <input type="date" v-model="filterStartDate" style="padding: 6px 10px; background: #151d30; border: 1px solid #2d3f66; color: #e2e8f0; border-radius: 6px; font-size: 12px;" title="起始日期">
                        <span style="color: #64748b;">至</span>
                        <input type="date" v-model="filterEndDate" style="padding: 6px 10px; background: #151d30; border: 1px solid #2d3f66; color: #e2e8f0; border-radius: 6px; font-size: 12px;" title="截止日期">
                        <input type="text" v-model="searchKeyword" placeholder="🔍 标题/关键词实时过滤..." style="padding: 6px 12px; background: #151d30; border: 1px solid #2d3f66; color: #e2e8f0; border-radius: 6px; font-size: 12px; width: 180px;">
                    </div>

                    <!-- Sort Order Toggle -->
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <button @click="toggleSortOrder" class="btn btn-outline" style="padding: 6px 12px; font-size: 12px;">
                            {{ sortOrder === 'desc' ? '⬇️ 最新在前 (倒序)' : '⬆️ 最早在前 (正序)' }}
                        </button>
                    </div>
                </div>

                <!-- Quick Date Presets -->
                <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 6px;">
                    <span style="font-size: 12px; color: #94a3b8; margin-right: 4px;">快捷预设:</span>
                    <button @click="setTimelinePreset('all')" :class="activePreset === 'all' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'">全部时间</button>
                    <button @click="setTimelinePreset('2026')" :class="activePreset === '2026' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'">2026年 (最新)</button>
                    <button @click="setTimelinePreset('2025')" :class="activePreset === '2025' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'">2025年</button>
                    <button @click="setTimelinePreset('2024')" :class="activePreset === '2024' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'">2024年及以前</button>
                    <button @click="setTimelinePreset('30d')" :class="activePreset === '30d' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'">近30天</button>
                    <button @click="setTimelinePreset('90d')" :class="activePreset === '90d' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'">近90天</button>
                    <button @click="setTimelinePreset('365d')" :class="activePreset === '365d' ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'">近1年</button>
                </div>

                <!-- Bulk Selection Buttons -->
                <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding-top: 8px; border-top: 1px solid #141f36;">
                    <button @click="selectAllFiltered" class="btn btn-emerald btn-sm" style="font-weight: 600;">
                        ✨ 勾选当前时间线全部 ({{ filteredItems.length }}篇)
                    </button>
                    <button @click="selectAllGlobal" class="btn btn-outline btn-sm">
                        🌟 全选大盘所有文章 ({{ items.length }}篇)
                    </button>
                    <button @click="unselectAll" class="btn btn-outline btn-sm">❌ 取消全选</button>
                    <span style="color: #334155; margin: 0 4px;">|</span>
                    <button @click="selectTopN(20)" class="btn btn-outline btn-sm">选前20篇</button>
                    <button @click="selectTopN(50)" class="btn btn-outline btn-sm">选前50篇</button>
                    <button @click="selectTopN(100)" class="btn btn-outline btn-sm">选前100篇</button>
                    <button @click="selectTopN(200)" class="btn btn-outline btn-sm">选前200篇</button>
                </div>
            </div>

            <!-- Items Table -->
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th style="width: 40px; text-align: center;">
                                <input type="checkbox" :checked="isAllFilteredSelected" @change="toggleSelectAllFiltered" style="width: 16px; height: 16px; accent-color: var(--cyan); cursor: pointer;">
                            </th>
                            <th style="width: 70px;">类型</th>
                            <th>标题 / 专栏名称 / 内容摘要</th>
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
                                <span :class="'badge badge-' + it.type">
                                    {{ it.type === 'article' ? '文章' : it.type === 'answer' ? '回答' : it.type === 'column' ? '专栏' : '想法' }}
                                </span>
                            </td>
                            <td>
                                <div style="font-weight: 600; color: #f8fafc; margin-bottom: 2px;">
                                    <a :href="it.url" target="_blank" style="color: inherit; text-decoration: none;">{{ it.title }}</a>
                                </div>
                                <div v-if="it.excerpt" style="font-size: 12px; color: #64748b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 650px;">
                                    {{ it.excerpt }}
                                </div>
                            </td>
                            <td style="text-align: center; color: #cbd5e1; font-size: 12px; font-family: monospace;">
                                {{ it.created_at || it.created_date || '—' }}
                            </td>
                            <td style="text-align: center; color: #94a3b8; font-size: 12px;">
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
                                ⚠️ 在当前所选时间段 ({{ filterStartDate || '起' }} 至 {{ filterEndDate || '止' }}) 或关键词下未检索到匹配条目，请重置时间线或关键词。
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Real-time Progress Card -->
        <section v-if="activeJob" class="card progress-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="font-size: 16px; font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 8px;">
                    <span v-if="activeJob.status === 'running'">🔄</span>
                    <span v-else>✅</span>
                    <span>任务状态: {{ activeJob.message }}</span>
                </h3>
                <span style="font-size: 16px; font-weight: 700; color: #38bdf8;">{{ activeJob.progress }}%</span>
            </div>

            <!-- Progress Bar -->
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" :style="{ width: activeJob.progress + '%' }"></div>
            </div>

            <!-- Real-time Terminal Log -->
            <div class="terminal-log">
                <div v-for="(log, idx) in activeJob.logs" :key="idx">{{ log }}</div>
            </div>

            <!-- Download Button (Bouncing Emerald) -->
            <div v-if="activeJob.status === 'completed'" style="display: flex; justify-content: flex-end; margin-top: 16px;">
                <a :href="'/api/jobs/' + activeJob.job_id + '/download'" class="btn btn-emerald bounce-btn" style="padding: 12px 24px; font-size: 15px;">
                    📦 点击下载完整证据压缩包 (ZIP)
                </a>
            </div>
        </section>

    </div>

    <script>
        function initApp() {
            if (typeof Vue === 'undefined') {
                setTimeout(initApp, 100);
                return;
            }
            const { createApp, ref, computed } = Vue;

            createApp({
                setup() {
                    const targetUrl = ref('');
                    const cookie = ref(localStorage.getItem('zhihu_cookie') || '');
                    const fetchLimit = ref(0);
                    const filterStartDate = ref('');
                    const filterEndDate = ref('');
                    const searchKeyword = ref('');
                    const sortOrder = ref('desc');
                    const activePreset = ref('all');

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

                    const setTimelinePreset = (preset) => {
                        activePreset.value = preset;
                        const now = new Date();
                        const pad = (n) => String(n).padStart(2, '0');
                        const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

                        if (preset === 'all') {
                            filterStartDate.value = '';
                            filterEndDate.value = '';
                        } else if (preset === '2026') {
                            filterStartDate.value = '2026-01-01';
                            filterEndDate.value = '2026-12-31';
                        } else if (preset === '2025') {
                            filterStartDate.value = '2025-01-01';
                            filterEndDate.value = '2025-12-31';
                        } else if (preset === '2024') {
                            filterStartDate.value = '1970-01-01';
                            filterEndDate.value = '2024-12-31';
                        } else if (preset === '30d') {
                            const past = new Date(now.getTime() - 30 * 24 * 3600 * 1000);
                            filterStartDate.value = fmt(past);
                            filterEndDate.value = fmt(now);
                        } else if (preset === '90d') {
                            const past = new Date(now.getTime() - 90 * 24 * 3600 * 1000);
                            filterStartDate.value = fmt(past);
                            filterEndDate.value = fmt(now);
                        } else if (preset === '365d') {
                            const past = new Date(now.getTime() - 365 * 24 * 3600 * 1000);
                            filterStartDate.value = fmt(past);
                            filterEndDate.value = fmt(now);
                        }
                    };

                    const filteredItems = computed(() => {
                        let res = items.value.slice();
                        if (searchKeyword.value.trim()) {
                            const kw = searchKeyword.value.trim().toLowerCase();
                            res = res.filter(i => 
                                (i.title && i.title.toLowerCase().includes(kw)) ||
                                (i.excerpt && i.excerpt.toLowerCase().includes(kw))
                            );
                        }
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
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    url: u,
                                    cookie: cookie.value,
                                    max_items: fetchLimit.value
                                })
                            });
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
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    cookie: cookie.value,
                                    items: chosen,
                                    options: options.value
                                })
                            });
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
                        targetUrl,
                        cookie,
                        fetchLimit,
                        filterStartDate,
                        filterEndDate,
                        searchKeyword,
                        sortOrder,
                        activePreset,
                        setTimelinePreset,
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
