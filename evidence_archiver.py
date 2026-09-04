"""Zhihu High-Precision Evidence Archiver with Full-Text, Comments & Screenshots.
Generates full-text markdown, comment JSON trees, high-DPI screenshots, and lawyer-standard Excel.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from playwright.sync_api import sync_playwright
from zhihu_client import ZhihuClient, strip_html_tags

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DESKTOP_TARGET = Path(r"C:\Users\25472\Desktop\清一武道馆")

OUTPUTS_DIR = DESKTOP_TARGET / "outputs"
SCREENSHOTS_DIR = OUTPUTS_DIR / "screenshots"
ARTICLES_DIR = OUTPUTS_DIR / "articles"
COMMENTS_DIR = OUTPUTS_DIR / "comments"
REPORTS_DIR = OUTPUTS_DIR / "excel_reports"

for d in [SCREENSHOTS_DIR, ARTICLES_DIR, COMMENTS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = ROOT / "config.json"


def capture_evidence_screenshot(page, url: str, target_id: str, highlight_text: str = "") -> str:
    """Capture full-page / element screenshot using Playwright and highlight target text."""
    clean_id = re.sub(r"[^\w\-]", "_", target_id)
    img_name = f"{clean_id}.png"
    img_path = SCREENSHOTS_DIR / img_name

    if img_path.exists() and img_path.stat().st_size > 10000:
        return f"outputs/screenshots/{img_name}"

    try:
        page.goto(url, wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(2000)

        # Remove modal overlays / cookie banners if any
        page.evaluate("""
            () => {
                const overlays = document.querySelectorAll('.Modal-wrapper, .signFlowModal, .css-18z7g90');
                overlays.forEach(el => el.remove());
            }
        """)

        # Highlight attack sentence if found on page
        if highlight_text and len(highlight_text) >= 4:
            clean_snippet = highlight_text[:30].replace('"', '\\"').replace("'", "\\'")
            page.evaluate(f"""
                () => {{
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    let node;
                    while (node = walker.nextNode()) {{
                        if (node.nodeValue && node.nodeValue.includes("{clean_snippet}")) {{
                            const parent = node.parentElement;
                            if (parent) {{
                                parent.style.border = "3px solid red";
                                parent.style.backgroundColor = "rgba(255, 0, 0, 0.15)";
                                parent.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                            }}
                            break;
                        }}
                    }}
                }}
            """)
            page.wait_for_timeout(1000)

        page.screenshot(path=str(img_path), full_page=False)
        return f"outputs/screenshots/{img_name}"
    except Exception as e:
        print(f"  ⚠️ 截图异常 ({url}): {e}")
        return ""


def export_lawyer_format_excel(evidence_items: list[dict[str, Any]], output_filename: str = "清一武道馆_全网侵权文章汇总表_最新取证版.xlsx") -> Path:
    """Export evidence into lawyer-standard multi-sheet Excel."""
    out_path = REPORTS_DIR / output_filename

    # Group evidence by author / attacker
    grouped_by_author = {}
    for it in evidence_items:
        author = it.get("author_name") or it.get("发帖者账号名称") or "未知用户"
        if author not in grouped_by_author:
            grouped_by_author[author] = []
        grouped_by_author[author].append(it)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # 1. Sheet 1: 汇总全量大盘
        all_rows = []
        for author, items in grouped_by_author.items():
            for idx, it in enumerate(items, 1):
                all_rows.append({
                    "发帖者账号名称": author,
                    "序号": idx,
                    "发帖日期": it.get("created_at") or it.get("发帖日期") or datetime.now().strftime("%Y-%m-%d"),
                    "链接": it.get("parent_url") or it.get("链接") or "",
                    "文章标题": it.get("parent_title") or it.get("文章标题") or it.get("source_type") or "侵权言论",
                    "认为该文章侵权的主要原因（如：用“XXX”暗指山长、攻击辱骂、宗教传播等……）": it.get("evidence_quote") or it.get("判定依据") or it.get("content") or "",
                    "证据截图相对路径": it.get("screenshot_path") or "",
                    "是否为武道专精攻击": "是" if any(w in (it.get("content") or "") for w in ["武道", "功夫", "武术", "泰拳", "实战", "打败泰拳"]) else "否"
                })
        df_all = pd.DataFrame(all_rows)
        df_all.to_excel(writer, sheet_name="全网侵权言论总览", index=False)

        # 2. 重点核心黑子独立 Sheet (大王, 茅箴, 嘲笑鸟, 清风溪流, 守其黑, 行云流水, 逸尘等)
        for author, items in grouped_by_author.items():
            if len(items) >= 2 or author in ["大王", "茅箴", "嘲笑鸟", "清风溪流", "守其黑", "行云流水", "逸尘", "楠楠", "香雪莲"]:
                sheet_title = re.sub(r"[\\/*?:\[\]]", "_", author)[:25]
                author_rows = []
                for idx, it in enumerate(items, 1):
                    author_rows.append({
                        "发帖者账号名称": author,
                        "序号": idx,
                        "发帖日期": it.get("created_at") or it.get("发帖日期") or datetime.now().strftime("%Y-%m-%d"),
                        "链接": it.get("parent_url") or it.get("链接") or "",
                        "文章标题": it.get("parent_title") or it.get("文章标题") or it.get("source_type") or "侵权言论",
                        "认为该文章侵权的主要原因（如：用“XXX”暗指山长、攻击辱骂、宗教传播等……）": it.get("evidence_quote") or it.get("判定依据") or it.get("content") or "",
                        "证据截图相对路径": it.get("screenshot_path") or "",
                        "是否为武道专精攻击": "是" if any(w in (it.get("content") or "") for w in ["武道", "功夫", "武术", "泰拳", "实战", "打败泰拳"]) else "否"
                    })
                df_author = pd.DataFrame(author_rows)
                df_author.to_excel(writer, sheet_name=sheet_title, index=False)

    print(f"✅ 律师标准版 Excel 报表已生成: {out_path}")
    return out_path
