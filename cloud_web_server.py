"""Zhihu Cloud Monitor Web Console & Real-Time Dashboard (Port 8770)
Provides real-time evidence stream, suspect leaderboard, and one-click Excel/CSV export.
"""

from __future__ import annotations

import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
import pandas as pd
import uvicorn

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "zhihu_monitor.db"
CONFIG_PATH = ROOT / "config.json"

app = FastAPI(title="知乎全网负面舆情监控与穿透中枢")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/api/stats")
def get_stats():
    if not DB_PATH.exists():
        return {"total_evidence": 0, "high_risk": 0, "suspects": 0, "latest_items": []}
    
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM evidence WHERE is_true_negative = 1")
        total_ev = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM evidence WHERE is_true_negative = 1 AND risk_level = 'HIGH'")
        high_risk = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM suspect_users WHERE true_attack_count > 0")
        total_suspects = cur.fetchone()[0]
        
        cur.execute("""
            SELECT * FROM evidence 
            WHERE is_true_negative = 1 
            ORDER BY first_seen_at DESC LIMIT 20
        """)
        latest_items = [dict(r) for r in cur.fetchall()]
        
        cur.execute("""
            SELECT * FROM suspect_users 
            WHERE true_attack_count > 0 
            ORDER BY true_attack_count DESC LIMIT 20
        """)
        top_suspects = [dict(r) for r in cur.fetchall()]

    return {
        "total_evidence": total_ev,
        "high_risk": high_risk,
        "suspects": total_suspects,
        "latest_items": latest_items,
        "top_suspects": top_suspects
    }


@app.get("/api/export/excel")
def export_excel():
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database not initialized")
    
    with get_db() as conn:
        df_ev = pd.read_sql_query("SELECT * FROM evidence WHERE is_true_negative = 1 ORDER BY first_seen_at DESC", conn)
        df_sus = pd.read_sql_query("SELECT * FROM suspect_users WHERE true_attack_count > 0 ORDER BY true_attack_count DESC", conn)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_ev.to_excel(writer, sheet_name="真实黑帖证据明细", index=False)
        df_sus.to_excel(writer, sheet_name="可疑人员深度画像", index=False)
    
    output.seek(0)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = {"Content-Disposition": f"attachment; filename=zhihu_evidence_{now_str}.xlsx"}
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)


@app.get("/api/export/csv")
def export_csv():
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail="Database not initialized")
    
    with get_db() as conn:
        df_ev = pd.read_sql_query("SELECT * FROM evidence WHERE is_true_negative = 1 ORDER BY first_seen_at DESC", conn)

    output = io.StringIO()
    df_ev.to_csv(output, index=False, encoding="utf-8-sig")
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = {"Content-Disposition": f"attachment; filename=zhihu_evidence_{now_str}.csv"}
    return Response(content=output.getvalue().encode("utf-8-sig"), media_type="text/csv", headers=headers)


@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>知乎全网负面舆情监控与人员穿透大盘</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    </style>
</head>
<body class="p-6">
    <div class="max-w-7xl mx-auto space-y-6">
        <!-- Header -->
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center bg-slate-800/80 p-6 rounded-2xl border border-slate-700 backdrop-blur shadow-xl gap-4">
            <div>
                <h1 class="text-2xl font-bold flex items-center gap-3 text-cyan-400">
                    <i class="fa-solid fa-shield-halved text-rose-500"></i>
                    知乎全网负面证据取证与人员穿透大盘
                </h1>
                <p class="text-slate-400 text-sm mt-1">云端 7x24 小时持续深度搜寻 · 评论楼中楼穿透 · 重点黑号全网追踪</p>
            </div>
            <div class="flex items-center gap-3">
                <span class="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 animate-pulse">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 mr-2"></span>
                    云端引擎持续运行中
                </span>
                <a href="/api/export/excel" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl transition shadow-lg flex items-center gap-2">
                    <i class="fa-solid fa-file-excel"></i> 下载最新 Excel 证据表
                </a>
            </div>
        </div>

        <!-- Metrics Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="bg-slate-800/60 p-6 rounded-2xl border border-slate-700 shadow-lg">
                <div class="text-slate-400 text-sm font-medium">累计捕获真实黑帖证据</div>
                <div class="text-4xl font-extrabold text-cyan-400 mt-2" id="stat-total">--</div>
                <div class="text-xs text-slate-500 mt-2">已 100% 剔除己方与辩护言论</div>
            </div>
            <div class="bg-slate-800/60 p-6 rounded-2xl border border-slate-700 shadow-lg">
                <div class="text-slate-400 text-sm font-medium">高风险实锤攻击言论</div>
                <div class="text-4xl font-extrabold text-rose-400 mt-2" id="stat-high">--</div>
                <div class="text-xs text-slate-500 mt-2">涉及“骗子/假武术/误人子弟/洗脑”</div>
            </div>
            <div class="bg-slate-800/60 p-6 rounded-2xl border border-slate-700 shadow-lg">
                <div class="text-slate-400 text-sm font-medium">穿透锁定真实黑号人数</div>
                <div class="text-4xl font-extrabold text-amber-400 mt-2" id="stat-suspects">--</div>
                <div class="text-xs text-slate-500 mt-2">已对其个人主页全量历史做底细排查</div>
            </div>
        </div>

        <!-- Main Content: Left Leaderboard, Right Feed -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Left: Top Suspects -->
            <div class="lg:col-span-1 bg-slate-800/60 p-6 rounded-2xl border border-slate-700 shadow-lg">
                <h2 class="text-lg font-bold text-amber-400 flex items-center gap-2 mb-4">
                    <i class="fa-solid fa-users-viewfinder"></i> 核心黑号人员排行榜
                </h2>
                <div class="space-y-3 max-h-[700px] overflow-y-auto pr-2" id="suspects-list">
                    <div class="text-slate-500 text-sm">加载中...</div>
                </div>
            </div>

            <!-- Right: Latest Real-time Evidence Feed -->
            <div class="lg:col-span-2 bg-slate-800/60 p-6 rounded-2xl border border-slate-700 shadow-lg">
                <h2 class="text-lg font-bold text-cyan-400 flex items-center gap-2 mb-4">
                    <i class="fa-solid fa-list-check"></i> 实时捕获黑帖与评论证据流
                </h2>
                <div class="space-y-4 max-h-[700px] overflow-y-auto pr-2" id="evidence-feed">
                    <div class="text-slate-500 text-sm">加载中...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function loadData() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                document.getElementById('stat-total').innerText = data.total_evidence;
                document.getElementById('stat-high').innerText = data.high_risk;
                document.getElementById('stat-suspects').innerText = data.suspects;

                // Render Top Suspects
                const susContainer = document.getElementById('suspects-list');
                susContainer.innerHTML = '';
                if (!data.top_suspects || data.top_suspects.length === 0) {
                    susContainer.innerHTML = '<div class="text-slate-500 text-sm">暂无数据</div>';
                } else {
                    data.top_suspects.forEach((u, idx) => {
                        susContainer.innerHTML += `
                            <div class="p-3 bg-slate-900/70 rounded-xl border border-slate-700/60 hover:border-amber-500/50 transition">
                                <div class="flex justify-between items-center">
                                    <div class="font-bold text-sm text-slate-200">
                                        <span class="text-amber-400 mr-1">#${idx+1}</span> ${u.user_name}
                                    </div>
                                    <span class="text-xs px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold">
                                        ${u.true_attack_count} 条攻击
                                    </span>
                                </div>
                                <div class="text-xs text-slate-400 mt-1 truncate">${u.headline || '无简介'}</div>
                                <div class="mt-2 flex justify-between items-center text-xs">
                                    <a href="${u.user_url}" target="_blank" class="text-cyan-400 hover:underline flex items-center gap-1">
                                        <i class="fa-solid fa-up-right-from-square text-[10px]"></i> 查看主页
                                    </a>
                                    <span class="text-slate-500">${u.last_updated_at || ''}</span>
                                </div>
                            </div>
                        `;
                    });
                }

                // Render Evidence Feed
                const evContainer = document.getElementById('evidence-feed');
                evContainer.innerHTML = '';
                if (!data.latest_items || data.latest_items.length === 0) {
                    evContainer.innerHTML = '<div class="text-slate-500 text-sm">暂无数据</div>';
                } else {
                    data.latest_items.forEach((item, idx) => {
                        evContainer.innerHTML += `
                            <div class="p-4 bg-slate-900/70 rounded-xl border border-slate-700/60 space-y-2 hover:border-cyan-500/50 transition">
                                <div class="flex justify-between items-center flex-wrap gap-2">
                                    <div class="flex items-center gap-2">
                                        <span class="text-xs px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                                            ${item.source_type}
                                        </span>
                                        <span class="text-xs px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-medium">
                                            ${item.category || '负面'}
                                        </span>
                                        <span class="text-sm font-semibold text-slate-200">
                                            ${item.author_name}
                                        </span>
                                    </div>
                                    <span class="text-xs text-slate-500">${item.first_seen_at || item.created_at}</span>
                                </div>
                                <div class="text-xs text-slate-400 font-medium truncate">
                                    关联帖子: ${item.parent_title}
                                </div>
                                <div class="text-sm text-slate-300 bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 leading-relaxed">
                                    ${item.content}
                                </div>
                                <div class="flex justify-between items-center text-xs text-slate-400 pt-1">
                                    <span>获赞: ${item.voteup_count || 0}</span>
                                    <a href="${item.parent_url}" target="_blank" class="text-cyan-400 hover:underline flex items-center gap-1">
                                        <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i> 直达原帖/评论
                                    </a>
                                </div>
                            </div>
                        `;
                    });
                }
            } catch (err) {
                console.error("加载数据失败:", err);
            }
        }

        loadData();
        setInterval(loadData, 10000); // 10秒自动刷新
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8770)
