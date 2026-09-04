"""High-Performance Full-Batch Evidence Collector & Screenshotter.
Processes ALL 375+ evidence items from the cloud database,
downloads full-text markdown + HTML, nested comments, and high-DPI screenshots.
Filters out temporary Excel ~$ lock files.
"""

from __future__ import annotations

import io
import json
import os
import re
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


def run_full_archive_and_screenshots(max_items: int = None):
    print("=" * 65)
    print("📸 启动全网黑帖【全量 375+ 证据】全文归档 + 评论全量抓取 + 现场高清截图")
    print("=" * 65)

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    client = ZhihuClient(cookie=config.get("cookie", ""))

    # 1. 查找最新的 Excel 数据源 (排除 Windows Excel ~$ 临时锁定文件)
    excel_candidates = [
        p for p in REPORTS_DIR.glob("*.xlsx")
        if not p.name.startswith("~$")
    ]
    excel_candidates = sorted(excel_candidates, key=lambda p: p.stat().st_mtime, reverse=True)

    if not excel_candidates:
        excel_candidates = [
            p for p in (ROOT / "outputs").glob("*.xlsx")
            if not p.name.startswith("~$")
        ]
        excel_candidates = sorted(excel_candidates, key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not excel_candidates:
        print("❌ 未找到待处理的 Excel 证据源！")
        return

    target_excel = excel_candidates[0]
    print(f"📖 读取最新证据大盘: {target_excel.name}...")
    
    df = pd.read_excel(target_excel)
    print(f"📊 本批次待处理全量总记录数: {len(df)} 条")

    if max_items:
        df = df.head(max_items)
        print(f"⚙️ 限制处理前: {len(df)} 条")

    cookie_str = config.get("cookie", "").strip()
    cookies = []
    for item in cookie_str.split(";"):
        if "=" in item:
            name, value = item.strip().split("=", 1)
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".zhihu.com",
                "path": "/"
            })

    updated_records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
        )
        context.add_cookies(cookies)
        page = context.new_page()

        for idx, row in df.iterrows():
            author = str(row.get("发帖者账号名称") or row.get("发帖人昵称") or "未知作者").strip()
            link = str(row.get("链接") or row.get("parent_url") or "").strip()
            title = str(row.get("文章标题") or row.get("parent_title") or "无标题").strip()
            reason = str(row.get("认为该文章侵权的主要原因（如：用“XXX”暗指山长、攻击辱骂、宗教传播等……）") or row.get("攻击原句") or "").strip()
            date_str = str(row.get("发帖日期") or row.get("created_at") or datetime.now().strftime("%Y-%m-%d")).strip()

            item_id = f"item_{idx+1}_{abs(hash(link)) % 1000000}"
            match_ans = re.search(r"answer/(\d+)", link)
            match_art = re.search(r"p/(\d+)", link)

            if match_ans:
                item_id = f"ans_{match_ans.group(1)}"
            elif match_art:
                item_id = f"art_{match_art.group(1)}"

            img_name = f"{item_id}.png"
            img_path = SCREENSHOTS_DIR / img_name
            art_file = ARTICLES_DIR / f"{item_id}.md"
            c_file = COMMENTS_DIR / f"{item_id}_comments.json"

            screenshot_rel = f"outputs/screenshots/{img_name}" if img_path.exists() and img_path.stat().st_size > 10000 else ""
            fulltext_rel = f"outputs/articles/{item_id}.md" if art_file.exists() and art_file.stat().st_size > 50 else ""
            comments_rel = f"outputs/comments/{item_id}_comments.json" if c_file.exists() else ""

            # 若已存在截图与全文，直接复用快速跳过
            if screenshot_rel and fulltext_rel:
                print(f"[{idx+1}/{len(df)}] ⚡ [缓存复用] 已存证: 【{author}】{title[:25]}...")
            else:
                print(f"\n[{idx+1}/{len(df)}] 📸 正在为【{author}】抓取全文并现场截图: {title[:25]}...")

                # A & B: Playwright 导航、全文抓取与现场截图
                if link and link.startswith("http"):
                    try:
                        page.goto(link, wait_until="domcontentloaded", timeout=18000)
                        page.wait_for_timeout(1000)

                        # 移除浮层遮罩
                        page.evaluate("""
                            () => {
                                const overlays = document.querySelectorAll('.Modal-wrapper, .signFlowModal, .css-18z7g90');
                                overlays.forEach(el => el.remove());
                            }
                        """)

                        # 提取真实 DOM 中的作者与标题
                        extracted_author = page.evaluate("""
                            () => {
                                const a = document.querySelector('.AuthorInfo-name, .UserLink-link');
                                return a ? a.innerText.trim() : '';
                            }
                        """)
                        if extracted_author and (not author or author == "nan" or author == "未知作者"):
                            author = extracted_author

                        # 提取全文 HTML 与 纯文本
                        full_content_text = page.evaluate("""
                            () => {
                                const el = document.querySelector('.RichContent-inner, .Post-content, .ContentItem-content');
                                return el ? el.innerText : document.body.innerText;
                            }
                        """)
                        full_content_html = page.evaluate("""
                            () => {
                                const el = document.querySelector('.RichContent-inner, .Post-content, .ContentItem-content');
                                return el ? el.innerHTML : '';
                            }
                        """)

                        # 保存全文 Markdown / HTML
                        art_file.write_text(
                            f"# {title}\n\n"
                            f"- **发帖作者**：{author}\n"
                            f"- **原始链接**：{link}\n"
                            f"- **取证时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"- **侵权理由**：{reason}\n\n"
                            f"---\n\n"
                            f"## 📄 文章/回答全文纯文本\n\n{full_content_text}\n\n"
                            f"---\n\n"
                            f"### 🌐 原始完整 HTML DOM\n```html\n{full_content_html}\n```\n",
                            encoding="utf-8"
                        )
                        fulltext_rel = f"outputs/articles/{item_id}.md"

                        # 若有攻击原句，红框高亮并滚动到中心
                        if reason and len(reason) >= 4:
                            clean_quote = reason[:25].replace('"', '\\"').replace("'", "\\'")
                            page.evaluate(f"""
                                () => {{
                                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                                    let node;
                                    while (node = walker.nextNode()) {{
                                        if (node.nodeValue && node.nodeValue.includes("{clean_quote}")) {{
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
                            page.wait_for_timeout(500)

                        if not img_path.exists() or img_path.stat().st_size < 10000:
                            page.screenshot(path=str(img_path), full_page=False)
                        screenshot_rel = f"outputs/screenshots/{img_name}"
                        print(f"  ✓ 现场截图与全文已保存 ({len(full_content_text)} 字)")
                    except Exception as e:
                        print(f"  ⚠️ 现场截图/全文异常: {e}")

                # C. 抓取评论楼中楼 JSON
                if (match_ans or match_art) and not c_file.exists():
                    t_type = "answers" if match_ans else "articles"
                    t_id = match_ans.group(1) if match_ans else match_art.group(1)
                    try:
                        comments = client.fetch_all_comments_for_target(t_type, t_id, max_roots=30)
                        if comments:
                            c_file.write_text(json.dumps(comments, ensure_ascii=False, indent=2), encoding="utf-8")
                            comments_rel = f"outputs/comments/{item_id}_comments.json"
                            print(f"  ✓ 成功下载评论区: {len(comments)} 条楼中楼评论")
                    except Exception as e:
                        print(f"  ⚠️ 评论抓取异常: {e}")

            updated_records.append({
                "发帖者账号名称": author,
                "序号": idx + 1,
                "发帖日期": date_str,
                "链接": link,
                "文章标题": title,
                "认为该文章侵权的主要原因（如：用“XXX”暗指山长、攻击辱骂、宗教传播等……）": reason,
                "证据截图相对路径": screenshot_rel,
                "全文归档路径": fulltext_rel,
                "评论楼中楼归档路径": comments_rel,
                "是否为武道专精攻击": "是" if any(w in (reason + title) for w in ["武道", "功夫", "武术", "泰拳", "实战", "打败泰拳"]) else "否"
            })

        browser.close()

    # 4. 生成图文印证对齐的最新 Excel 证据报表
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_excel = REPORTS_DIR / f"清一武道馆_全网侵权文章汇总表_全量图文印证版_{now_str}.xlsx"

    grouped = {}
    for r in updated_records:
        acc = r["发帖者账号名称"]
        if acc not in grouped:
            grouped[acc] = []
        grouped[acc].append(r)

    with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
        df_all = pd.DataFrame(updated_records)
        df_all.to_excel(writer, sheet_name="全网侵权言论总览", index=False)

        for acc, items in grouped.items():
            if len(items) >= 2 or acc in ["大王", "茅箴", "嘲笑鸟", "清风溪流", "守其黑", "行云流水", "逸尘", "楠楠", "香雪莲"]:
                sheet_title = re.sub(r"[\\/*?:\[\]]", "_", acc)[:25]
                pd.DataFrame(items).to_excel(writer, sheet_name=sheet_title, index=False)

    print("\n" + "=" * 65)
    print("🎉 全量 375+ 证据全文下载、评论抓取与现场截图批处理完成！")
    print(f"📁 最终图文印证 Excel 报表已保存: {out_excel}")
    print("=" * 65)


if __name__ == "__main__":
    run_full_archive_and_screenshots(max_items=None)
