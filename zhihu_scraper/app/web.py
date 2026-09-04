"""Zhihu Self-Service Web Application.
Provides interactive URL inspection, checklist selection, real-time progress bar,
full-text download, comment scraping, Playwright screenshotting, and one-click ZIP packaging.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
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

# In-memory store for background scraping jobs
JOBS: Dict[str, Dict[str, Any]] = {}


class InspectRequest(BaseModel):
    url: str
    cookie: Optional[str] = ""
    max_items: Optional[int] = 50


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

    # 1. If column URL
    if "zhihu.com/column/" in url:
        col_scraper = ColumnScraper(client)
        col_info = col_scraper.get_column_info(url)
        articles = col_scraper.list_column_articles(url, max_items=req.max_items or 100)
        return {
            "target_type": "column",
            "info": {
                "title": col_info.get("title", "专栏"),
                "description": col_info.get("description", ""),
                "articles_count": len(articles)
            },
            "total_items": len(articles),
            "items": articles
        }

    # 2. Otherwise treat as author or general profile
    author_scraper = AuthorScraper(client)
    try:
        catalog = author_scraper.catalog_all_assets(
            url,
            include_articles=True,
            include_answers=True,
            include_pins=True,
            include_columns=True,
            max_per_category=req.max_items or 50
        )
        catalog["target_type"] = "author"
        return catalog
    except Exception as e:
        logger.error("Error inspecting %s: %s", url, e)
        raise HTTPException(status_code=500, detail=f"解析知乎资产失败: {str(e)}")


def run_batch_job(job_id: str, cookie: str, items: List[Dict[str, Any]], options: Dict[str, Any]):
    """Background task executing the selected batch scraping."""
    job = JOBS[job_id]
    job["status"] = "running"
    job["total"] = len(items)
    job["current"] = 0
    job["logs"] = []

    client = ZhihuClient(cookie=cookie)
    article_scraper = ArticleScraper(client)
    answer_scraper = AnswerScraper(client)
    pin_scraper = PinScraper(client)
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

    # Package as ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                full_p = Path(root) / file
                rel_p = full_p.relative_to(temp_dir)
                zf.write(full_p, arcname=str(rel_p))

    zip_bytes = zip_buffer.getvalue()
    job["zip_bytes"] = zip_bytes
    job["status"] = "completed"
    job["current_message"] = "🎉 全部选定任务存证完毕！可以点击下载压缩包。"
    job["logs"].append(f"{time.strftime('%H:%M:%S')} - 全部完成！已打包生成 ZIP。")


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
        "zip_bytes": None
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
                "logs": job.get("logs", [])[-15:]
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if job["status"] in ["completed", "error"]:
                break
            await asyncio.sleep(0.8)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/download")
def download_job_zip(job_id: str):
    """Download the finalized ZIP containing all articles, comments, and screenshots."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job["status"] != "completed" or not job.get("zip_bytes"):
        raise HTTPException(status_code=400, detail="任务尚未完成或数据不可用")

    headers = {"Content-Disposition": f"attachment; filename=zhihu_archive_{job_id}.zip"}
    return StreamingResponse(io.BytesIO(job["zip_bytes"]), media_type="application/zip", headers=headers)


@app.get("/", response_class=HTMLResponse)
def index_ui():
    """Renders the comprehensive self-service Web UI."""
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知乎创作者定向排查与批量存证工具箱</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        [v-cloak] { display: none; }
        body { background-color: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    </style>
</head>
<body class="p-4 md:p-8">
    <div id="app" v-cloak class="max-w-6xl mx-auto space-y-6">
        
        <!-- Header -->
        <header class="bg-slate-800/80 p-6 rounded-2xl border border-slate-700 shadow-xl backdrop-blur flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <h1 class="text-2xl font-bold flex items-center gap-3 text-cyan-400">
                    <i class="fa-solid fa-crosshairs text-rose-500"></i>
                    知乎创作者定向排查与批量存证工具箱
                </h1>
                <p class="text-slate-400 text-sm mt-1">输入目标主页/专栏 ➔ 检索全部资产 ➔ 勾选所需条目 ➔ 全文、评论与高清截图一键存证</p>
            </div>
            <div class="flex items-center gap-2 text-xs text-slate-400 bg-slate-900/60 px-4 py-2 rounded-xl border border-slate-700">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>引擎就绪 (Playwright + Zhihu API)</span>
            </div>
        </header>

        <!-- Configuration Card -->
        <section class="bg-slate-800 p-6 rounded-2xl border border-slate-700 space-y-4 shadow-lg">
            <h2 class="text-lg font-semibold text-slate-200 flex items-center gap-2">
                <i class="fa-solid fa-sliders text-cyan-400"></i>
                第一步：设置目标与凭证
            </h2>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-xs text-slate-400 mb-1">目标知乎主页或专栏链接 (必填)</label>
                    <div class="relative">
                        <input v-model="targetUrl" type="text" placeholder="例: https://www.zhihu.com/people/shou-qi-hei 或 /column/xxx"
                            class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-cyan-400 text-slate-100 pl-10">
                        <i class="fa-solid fa-link absolute left-3 top-3.5 text-slate-500"></i>
                    </div>
                </div>
                <div>
                    <label class="block text-xs text-slate-400 mb-1">知乎 Cookie 凭证 (选填/建议填写本人 Cookie 避开限流)</label>
                    <div class="relative">
                        <input v-model="cookie" type="password" placeholder="粘贴你的知乎 Cookie (z_c0=...)"
                            class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-cyan-400 text-slate-100 pl-10">
                        <i class="fa-solid fa-key absolute left-3 top-3.5 text-slate-500"></i>
                    </div>
                </div>
            </div>

            <div class="flex flex-wrap items-center justify-between gap-4 pt-2">
                <div class="flex items-center gap-4 text-xs text-slate-400">
                    <label class="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" v-model="options.save_markdown" class="rounded bg-slate-900 border-slate-700 text-cyan-500">
                        <span>抓取正文 (Markdown)</span>
                    </label>
                    <label class="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" v-model="options.save_comments" class="rounded bg-slate-900 border-slate-700 text-cyan-500">
                        <span>抓取楼中楼评论</span>
                    </label>
                    <label class="flex items-center gap-1.5 cursor-pointer">
                        <input type="checkbox" v-model="options.save_screenshot" class="rounded bg-slate-900 border-slate-700 text-cyan-500">
                        <span>Playwright 高清长截图</span>
                    </label>
                </div>

                <button @click="inspect" :disabled="inspecting"
                    class="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-medium px-6 py-2.5 rounded-xl shadow-lg transition flex items-center gap-2 disabled:opacity-50">
                    <i v-if="inspecting" class="fa-solid fa-spinner fa-spin"></i>
                    <i v-else class="fa-solid fa-magnifying-glass"></i>
                    <span>{{ inspecting ? '正在解析资产...' : '🔍 检索目标已有资产' }}</span>
                </button>
            </div>
        </section>

        <!-- Author Profile Banner (if loaded) -->
        <section v-if="authorInfo" class="bg-slate-800/60 p-5 rounded-2xl border border-slate-700 flex items-center justify-between gap-4">
            <div class="flex items-center gap-4">
                <img :src="authorInfo.avatar_url || 'https://picx.zhimg.com/a4e7052e4958603230a623ebb569533a_l.jpg'" class="w-14 h-14 rounded-full border-2 border-cyan-500/40">
                <div>
                    <h3 class="text-lg font-bold text-white flex items-center gap-2">
                        {{ authorInfo.name }}
                        <a :href="authorInfo.profile_url" target="_blank" class="text-xs text-cyan-400 hover:underline">
                            <i class="fa-solid fa-arrow-up-right-from-square"></i>
                        </a>
                    </h3>
                    <p class="text-xs text-slate-400">{{ authorInfo.headline || '暂无签名' }}</p>
                </div>
            </div>
            <div class="flex gap-6 text-center text-xs">
                <div>
                    <div class="text-slate-400">文章</div>
                    <div class="text-base font-bold text-cyan-400">{{ authorInfo.articles_count || 0 }}</div>
                </div>
                <div>
                    <div class="text-slate-400">问答</div>
                    <div class="text-base font-bold text-cyan-400">{{ authorInfo.answers_count || 0 }}</div>
                </div>
                <div>
                    <div class="text-slate-400">想法</div>
                    <div class="text-base font-bold text-cyan-400">{{ authorInfo.pins_count || 0 }}</div>
                </div>
            </div>
        </section>

        <!-- Asset Checklist Card -->
        <section v-if="items.length > 0" class="bg-slate-800 p-6 rounded-2xl border border-slate-700 space-y-4 shadow-lg">
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div class="flex items-center gap-3">
                    <h2 class="text-lg font-semibold text-slate-200 flex items-center gap-2">
                        <i class="fa-solid fa-list-check text-emerald-400"></i>
                        第二步：勾选需要存证的条目 (共 {{ items.length }} 条)
                    </h2>
                    <span class="text-xs bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-2.5 py-0.5 rounded-full font-medium">
                        已选中 {{ selectedCount }} 项
                    </span>
                </div>

                <div class="flex items-center gap-3">
                    <button @click="toggleSelectAll" class="text-xs text-slate-300 hover:text-white bg-slate-700/60 px-3 py-1.5 rounded-lg border border-slate-600 transition">
                        {{ isAllSelected ? '取消全选' : '全部全选' }}
                    </button>
                    <button @click="startBatchScrape" :disabled="selectedCount === 0 || scraping"
                        class="bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium px-5 py-2 rounded-xl shadow-lg transition flex items-center gap-2 disabled:opacity-40">
                        <i v-if="scraping" class="fa-solid fa-spinner fa-spin"></i>
                        <i v-else class="fa-solid fa-cloud-arrow-down"></i>
                        <span>{{ scraping ? '正在执行抓取...' : '🚀 开始批量存证已选项' }}</span>
                    </button>
                </div>
            </div>

            <!-- Items Table -->
            <div class="overflow-x-auto border border-slate-700 rounded-xl">
                <table class="w-full text-left text-xs text-slate-300">
                    <thead class="bg-slate-900/80 text-slate-400 uppercase border-b border-slate-700">
                        <tr>
                            <th class="p-3 w-10 text-center">
                                <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" class="rounded bg-slate-900 border-slate-700">
                            </th>
                            <th class="p-3 w-20">类型</th>
                            <th class="p-3">标题 / 内容摘要</th>
                            <th class="p-3 w-28 text-center">互动数据</th>
                            <th class="p-3 w-16 text-center">操作</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-700/50">
                        <tr v-for="it in items" :key="it.id" class="hover:bg-slate-700/30 transition">
                            <td class="p-3 text-center">
                                <input type="checkbox" v-model="it.selected" class="rounded bg-slate-900 border-slate-700 text-cyan-500">
                            </td>
                            <td class="p-3">
                                <span :class="typeBadgeClass(it.type)" class="px-2 py-0.5 rounded text-[10px] font-semibold">
                                    {{ it.type === 'article' ? '专栏文章' : it.type === 'answer' ? '回答' : it.type === 'column' ? '专栏' : '想法' }}
                                </span>
                            </td>
                            <td class="p-3 font-medium text-slate-200">
                                <div class="line-clamp-1">{{ it.title }}</div>
                                <div v-if="it.excerpt" class="text-[11px] text-slate-400 line-clamp-1 mt-0.5">{{ it.excerpt }}</div>
                            </td>
                            <td class="p-3 text-center text-slate-400">
                                <span>👍 {{ it.voteup_count || 0 }}</span>
                                <span class="ml-2">💬 {{ it.comment_count || 0 }}</span>
                            </td>
                            <td class="p-3 text-center">
                                <a :href="it.url" target="_blank" class="text-cyan-400 hover:text-cyan-300">
                                    <i class="fa-solid fa-arrow-up-right-from-square"></i>
                                </a>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Real-time Progress Modal / Card -->
        <section v-if="activeJob" class="bg-slate-800 p-6 rounded-2xl border border-cyan-500/40 space-y-4 shadow-2xl animate-fade-in">
            <div class="flex items-center justify-between">
                <h3 class="text-base font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-spinner fa-spin text-cyan-400" v-if="activeJob.status === 'running'"></i>
                    <i class="fa-solid fa-circle-check text-emerald-400" v-else></i>
                    <span>执行进度: {{ activeJob.message }}</span>
                </h3>
                <span class="text-sm font-bold text-cyan-400">{{ activeJob.progress }}%</span>
            </div>

            <!-- Progress Bar -->
            <div class="w-full bg-slate-900 rounded-full h-3 overflow-hidden border border-slate-700">
                <div class="bg-gradient-to-r from-cyan-500 to-emerald-500 h-3 rounded-full transition-all duration-300"
                     :style="{ width: activeJob.progress + '%' }"></div>
            </div>

            <!-- Execution Logs -->
            <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-[11px] text-slate-400 h-36 overflow-y-auto space-y-1">
                <div v-for="(log, lidx) in activeJob.logs" :key="lidx">{{ log }}</div>
            </div>

            <!-- Download Button -->
            <div v-if="activeJob.status === 'completed'" class="flex justify-end pt-2">
                <a :href="'/api/jobs/' + activeJob.job_id + '/download'" target="_blank"
                   class="bg-emerald-600 hover:bg-emerald-500 text-white font-medium px-6 py-2.5 rounded-xl shadow-lg transition flex items-center gap-2 animate-bounce">
                    <i class="fa-solid fa-file-zipper"></i>
                    <span>📦 一键下载存证成果压缩包 (ZIP)</span>
                </a>
            </div>
        </section>

    </div>

    <script>
        const { createApp, ref, computed, onMounted } = Vue;

        createApp({
            setup() {
                const targetUrl = ref('');
                const cookie = ref(localStorage.getItem('zhihu_cookie') || '');
                const options = ref({
                    save_markdown: true,
                    save_comments: true,
                    save_screenshot: true,
                    highlight_keywords: []
                });
                const inspecting = ref(false);
                const scraping = ref(false);
                const authorInfo = ref(null);
                const items = ref([]);
                const activeJob = ref(null);

                const isAllSelected = computed(() => {
                    return items.value.length > 0 && items.value.every(i => i.selected);
                });

                const selectedCount = computed(() => {
                    return items.value.filter(i => i.selected).length;
                });

                const toggleSelectAll = () => {
                    const targetState = !isAllSelected.value;
                    items.value.forEach(i => i.selected = targetState);
                };

                const typeBadgeClass = (type) => {
                    if (type === 'article') return 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30';
                    if (type === 'answer') return 'bg-blue-500/20 text-blue-300 border border-blue-500/30';
                    if (type === 'column') return 'bg-purple-500/20 text-purple-300 border border-purple-500/30';
                    return 'bg-amber-500/20 text-amber-300 border border-amber-500/30';
                };

                const inspect = async () => {
                    if (!targetUrl.value) {
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
                                url: targetUrl.value,
                                cookie: cookie.value,
                                max_items: 60
                            })
                        });
                        const data = await res.json();
                        if (!res.ok) throw new Error(data.detail || '解析失败');
                        
                        authorInfo.value = data.author || null;
                        items.value = (data.items || []).map(i => ({ ...i, selected: true }));
                    } catch (e) {
                        alert('检索出错: ' + e.message);
                    } finally {
                        inspecting.value = false;
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
                    options,
                    inspecting,
                    scraping,
                    authorInfo,
                    items,
                    activeJob,
                    isAllSelected,
                    selectedCount,
                    toggleSelectAll,
                    typeBadgeClass,
                    inspect,
                    startBatchScrape
                };
            }
        }).mount('#app');
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
