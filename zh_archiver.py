#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎文章全量归档与安全审计工具 (Zhihu Complete Archiver & Gatekeeper)
目标：
1. 抓取文章元数据 (Meta / Topics / Author / Stats)
2. 抓取知乎原始富文本 Draft JSON (original.json)
3. 导出原始 HTML (body.html)
4. 下载正文中的所有原图并本地化 (images/*)
5. 完整抓取评论区数据 (comments.json)
6. Playwright 高清全页截图 (screenshot.png)
7. 生成规范排版的 Word 文档 (body.docx，内嵌原图供本地 AI 审查)
8. 计算各项资产 SHA-256 并生成核对清单 (manifest.json + checklist.md)
9. 硬门禁：100% 完整性校验，未通过严禁进入 P1

严格安全限制：
- 只允许操作当前 Cookie 对应用户的文章 (me.url_token 白名单强校验)
- 跨平台兼容 (Windows / macOS / Linux)
"""

import os
import sys
import re
import json
import time
import hashlib
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT


# ---------------------------------------------------------
# 常量与配置
# ---------------------------------------------------------
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

HEADERS_BASE = {
    "User-Agent": DEFAULT_UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def compute_sha256(filepath: Path) -> str:
    """计算文件的 SHA-256 哈希"""
    if not filepath.exists() or filepath.is_dir():
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class ZhihuArchiver:
    def __init__(self, cookie_str: str, output_base: Path):
        self.cookie_str = cookie_str.strip()
        self.output_base = output_base
        self.output_base.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update(HEADERS_BASE)
        self.session.headers["Cookie"] = self.cookie_str
        
        self.current_user: Optional[Dict[str, Any]] = None
        self.url_token: str = ""

    def authenticate(self) -> Dict[str, Any]:
        """校验登录身份并绑定用户白名单"""
        resp = self.session.get("https://www.zhihu.com/api/v4/me", timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"知乎登录态校验失败: HTTP {resp.status_code} {resp.text[:120]}")
        
        data = resp.json()
        self.current_user = data
        self.url_token = data.get("url_token") or ""
        if not self.url_token:
            raise RuntimeError(f"未能解析当前用户 url_token: {data}")
        
        print(f"[✓] 登录验证成功: {data.get('name')} (url_token: {self.url_token})")
        print(f"    账号文章总数: {data.get('articles_count')}")
        return data

    def list_my_articles(self, limit: int = 0) -> List[Dict[str, Any]]:
        """获取当前登录用户的所有专栏文章"""
        if not self.url_token:
            self.authenticate()

        articles = []
        offset = 0
        batch_size = 20

        print(f"[*] 正在拉取用户 [{self.url_token}] 的文章列表...")
        while True:
            url = f"https://www.zhihu.com/api/v4/members/{self.url_token}/articles?limit={batch_size}&offset={offset}"
            resp = self.session.get(url, headers={"Referer": f"https://www.zhihu.com/people/{self.url_token}/posts"}, timeout=20)
            if resp.status_code != 200:
                print(f"[!] 获取文章列表第 {offset} 偏移失败: HTTP {resp.status_code}")
                break

            data = resp.json()
            items = data.get("data", [])
            if not items:
                break

            for it in items:
                articles.append({
                    "id": str(it.get("id")),
                    "title": it.get("title", ""),
                    "url": it.get("url", f"https://zhuanlan.zhihu.com/p/{it.get('id')}"),
                    "created": it.get("created"),
                    "updated": it.get("updated"),
                    "voteup_count": it.get("reaction", {}).get("statistics", {}).get("like_count", 0),
                    "comment_permission": it.get("comment_permission"),
                })
                if 0 < limit <= len(articles):
                    return articles

            paging = data.get("paging", {})
            if paging.get("is_end", False):
                break
            offset += batch_size
            time.sleep(0.3)

        print(f"[✓] 共枚举到 {len(articles)} 篇自有文章")
        return articles

    def fetch_draft(self, aid: str) -> Dict[str, Any]:
        """从草稿接口获取最完整的富文本与全量元数据"""
        url = f"https://zhuanlan.zhihu.com/api/articles/{aid}/draft"
        headers = {
            "Referer": f"https://zhuanlan.zhihu.com/p/{aid}/edit",
        }
        resp = self.session.get(url, headers=headers, timeout=25)
        if resp.status_code != 200:
            raise RuntimeError(f"获取文章草稿失败 ({aid}): HTTP {resp.status_code}")
        draft = resp.json()
        
        # 安全断言：强制检查作者必须是当前登录账号！
        author = draft.get("author") or {}
        author_token = author.get("url_token") or ""
        if author_token and author_token != self.url_token:
            raise PermissionError(
                f"[严重安全告警] 文章 {aid} 作者 ({author_token}) 与当前登录账号 ({self.url_token}) 不符！操作已熔断中止！"
            )
        return draft

    def fetch_comments(self, aid: str, max_roots: int = 100) -> Dict[str, Any]:
        """抓取文章评论（支持游标分页，含一级评论与二级回复）"""
        comments_result = {
            "total_count": 0,
            "root_count": 0,
            "comments": []
        }
        
        limit = 20
        url = f"https://www.zhihu.com/api/v4/comment_v5/articles/{aid}/root_comment?order_by=score&limit={limit}&offset="
        visited_urls = set()
        
        while url and url not in visited_urls and len(comments_result["comments"]) < max_roots:
            visited_urls.add(url)
            try:
                resp = self.session.get(url, headers={"Referer": f"https://zhuanlan.zhihu.com/p/{aid}"}, timeout=15)
                if resp.status_code != 200:
                    break
                data = resp.json()
                counts = data.get("counts", {})
                comments_result["total_count"] = counts.get("total_counts", 0)
                
                roots = data.get("data", [])
                if not roots:
                    break

                for r in roots:
                    r_id = str(r.get("id"))
                    author = r.get("author") or {}
                    root_item = {
                        "id": r_id,
                        "author_name": author.get("name", ""),
                        "author_url": f"https://www.zhihu.com/people/{author.get('url_token')}" if author.get("url_token") else "",
                        "content": r.get("content", ""),
                        "created_time": r.get("created_time"),
                        "like_count": r.get("like_count", 0),
                        "child_comments": []
                    }
                    
                    # 抓取子评论（如果有）
                    child_count = r.get("child_comment_count", 0)
                    if child_count > 0:
                        child_url = f"https://www.zhihu.com/api/v4/comment_v5/comment/{r_id}/child_comment?limit=20&offset="
                        c_visited = set()
                        while child_url and child_url not in c_visited:
                            c_visited.add(child_url)
                            try:
                                c_resp = self.session.get(child_url, headers={"Referer": f"https://zhuanlan.zhihu.com/p/{aid}"}, timeout=15)
                                if c_resp.status_code != 200:
                                    break
                                c_data = c_resp.json()
                                for c in c_data.get("data", []):
                                    c_auth = c.get("author") or {}
                                    root_item["child_comments"].append({
                                        "id": str(c.get("id")),
                                        "author_name": c_auth.get("name", ""),
                                        "content": c.get("content", ""),
                                        "created_time": c.get("created_time"),
                                        "like_count": c.get("like_count", 0)
                                    })
                                c_paging = c_data.get("paging", {})
                                if c_paging.get("is_end", True):
                                    break
                                child_url = c_paging.get("next", "")
                            except Exception as e:
                                print(f"    [!] 获取子评论失败 ({r_id}): {e}")
                                break

                    comments_result["comments"].append(root_item)
                
                comments_result["root_count"] = len(comments_result["comments"])
                paging = data.get("paging", {})
                if paging.get("is_end", True):
                    break
                url = paging.get("next", "")
                time.sleep(0.2)
            except Exception as e:
                print(f"    [!] 抓取评论异常 ({aid}): {e}")
                break

        return comments_result

    def download_images(self, html_content: str, img_dir: Path) -> Tuple[List[Dict[str, str]], str]:
        """
        下载 HTML 中的所有图片并更新本地相对路径映射
        返回: (下载清单, 本地化后的 HTML)
        """
        img_dir.mkdir(parents=True, exist_ok=True)
        soup = BeautifulSoup(html_content, "html.parser")
        images = []
        
        img_tags = soup.find_all("img")
        for idx, img in enumerate(img_tags, start=1):
            src = img.get("data-original") or img.get("data-actualsrc") or img.get("src") or ""
            if not src or not src.startswith("http"):
                continue

            # 去除知乎尾部缩放参数（如 _r.jpg, _720w.jpg）保留高清原图
            clean_url = re.sub(r'_[a-zA-Z0-9]+\.(jpg|jpeg|png|webp|gif)', r'.\1', src)
            
            ext = os.path.splitext(urlparse(clean_url).path)[-1].lower() or ".jpg"
            img_filename = f"img_{idx:03d}{ext}"
            img_path = img_dir / img_filename

            download_ok = False
            if not img_path.exists() or img_path.stat().st_size == 0:
                for retry in range(3):
                    try:
                        r = self.session.get(clean_url, timeout=20)
                        if r.status_code == 200 and len(r.content) > 100:
                            img_path.write_bytes(r.content)
                            download_ok = True
                            break
                    except Exception:
                        time.sleep(1)
            else:
                download_ok = True

            if download_ok:
                img_size = img_path.stat().st_size
                img_sha256 = compute_sha256(img_path)
                images.append({
                    "index": idx,
                    "filename": img_filename,
                    "url": clean_url,
                    "size": img_size,
                    "sha256": img_sha256,
                    "local_path": str(img_path)
                })
                # 将标签中的 src 替换为本地相对路径
                img["src"] = f"images/{img_filename}"
            else:
                images.append({
                    "index": idx,
                    "filename": img_filename,
                    "url": clean_url,
                    "size": 0,
                    "sha256": "",
                    "local_path": "",
                    "error": "下载失败"
                })

        local_html = str(soup)
        return images, local_html

    def export_word(self, meta: Dict[str, Any], html_content: str, img_dir: Path, docx_path: Path):
        """将文章与图片高质量导出为 Word 文档 (.docx)"""
        doc = Document()
        
        # 页面边距设置 (2.54cm)
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)

        # 标题 (加大、居中/靠左)
        title_p = doc.add_paragraph()
        title_run = title_p.add_run(meta.get("title", "未命名文章"))
        title_run.font.size = Pt(20)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(17, 24, 39)
        title_p.paragraph_format.space_after = Pt(12)

        # 元数据表格摘要
        table = doc.add_table(rows=5, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = 'Table Grid'
        
        meta_items = [
            ("文章 ID", str(meta.get("id", ""))),
            ("原作者", str(meta.get("author", {}).get("name", ""))),
            ("发布时间", str(meta.get("created_formatted", ""))),
            ("点赞 / 评论", f"点赞: {meta.get('voteup_count', 0)} | 评论: {meta.get('comment_count', 0)}"),
            ("原始链接", str(meta.get("url", ""))),
        ]
        for row_idx, (k, v) in enumerate(meta_items):
            row_cells = table.rows[row_idx].cells
            row_cells[0].text = k
            row_cells[0].paragraphs[0].runs[0].font.bold = True
            row_cells[0].paragraphs[0].runs[0].font.size = Pt(9.5)
            row_cells[1].text = v
            row_cells[1].paragraphs[0].runs[0].font.size = Pt(9.5)

        doc.add_paragraph().paragraph_format.space_after = Pt(14)

        # 正文解析与排版
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 遍历顶层元素
        for elem in soup.children:
            if not elem.name:
                text = str(elem).strip()
                if text:
                    p = doc.add_paragraph(text)
                    p.paragraph_format.space_after = Pt(6)
                continue

            tag = elem.name.lower()
            if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                level = int(tag[1])
                h_p = doc.add_heading(elem.get_text().strip(), level=min(level, 3))
                h_p.paragraph_format.space_before = Pt(10)
                h_p.paragraph_format.space_after = Pt(4)
            elif tag == "p":
                # 检查段落内是否有图片
                imgs = elem.find_all("img")
                if imgs:
                    for img in imgs:
                        src = img.get("src", "")
                        # 查找本地图片文件
                        filename = os.path.basename(src)
                        local_img_file = img_dir / filename
                        if local_img_file.exists() and local_img_file.stat().st_size > 0:
                            p_img = doc.add_paragraph()
                            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            try:
                                p_img.add_run().add_picture(str(local_img_file), width=Inches(5.5))
                            except Exception as e:
                                p_img.add_run(f"[图片加载异常: {filename}]")
                            p_img.paragraph_format.space_after = Pt(8)
                
                # 正文文字
                text = elem.get_text().strip()
                if text:
                    p = doc.add_paragraph(text)
                    p.paragraph_format.line_spacing = 1.25
                    p.paragraph_format.space_after = Pt(6)
            elif tag == "blockquote":
                quote_text = elem.get_text().strip()
                if quote_text:
                    p = doc.add_paragraph()
                    run = p.add_run(f"“ {quote_text} ”")
                    run.font.italic = True
                    run.font.color.rgb = RGBColor(100, 116, 139)
                    p.paragraph_format.left_indent = Inches(0.4)
                    p.paragraph_format.space_after = Pt(8)
            elif tag in ["ul", "ol"]:
                for li in elem.find_all("li"):
                    li_text = li.get_text().strip()
                    if li_text:
                        p = doc.add_paragraph(li_text, style='List Bullet' if tag == 'ul' else 'List Number')
                        p.paragraph_format.space_after = Pt(3)
            elif tag == "figure":
                imgs = elem.find_all("img")
                for img in imgs:
                    src = img.get("src", "")
                    filename = os.path.basename(src)
                    local_img_file = img_dir / filename
                    if local_img_file.exists() and local_img_file.stat().st_size > 0:
                        p_img = doc.add_paragraph()
                        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        try:
                            p_img.add_run().add_picture(str(local_img_file), width=Inches(5.5))
                        except Exception:
                            p_img.add_run(f"[图片加载异常: {filename}]")
                        p_img.paragraph_format.space_after = Pt(8)
            elif tag == "img":
                src = elem.get("src", "")
                filename = os.path.basename(src)
                local_img_file = img_dir / filename
                if local_img_file.exists() and local_img_file.stat().st_size > 0:
                    p_img = doc.add_paragraph()
                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    try:
                        p_img.add_run().add_picture(str(local_img_file), width=Inches(5.5))
                    except Exception:
                        p_img.add_run(f"[图片加载异常: {filename}]")
                    p_img.paragraph_format.space_after = Pt(8)

        docx_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(docx_path))

    def capture_screenshot_playwright(self, aid: str, screenshot_path: Path):
        """使用 Playwright 捕获长截图（包含正文和已展开的评论区）"""
        from playwright.sync_api import sync_playwright

        url = f"https://zhuanlan.zhihu.com/p/{aid}"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # 建立高清 1920 宽屏 Context
            context = browser.new_context(
                viewport={"width": 1440, "height": 1080},
                device_scale_factor=2,  # 2x 高清
                user_agent=DEFAULT_UA
            )
            
            # 注入知乎 Cookie
            cookies = []
            for part in self.cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookies.append({
                        "name": k.strip(),
                        "value": v.strip(),
                        "domain": ".zhihu.com",
                        "path": "/"
                    })
            context.add_cookies(cookies)

            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                time.sleep(2)
                
                # 模拟向下滚动，触发图片懒加载与评论区展开
                page.evaluate("""
                    () => {
                        window.scrollTo(0, document.body.scrollHeight / 3);
                    }
                """)
                time.sleep(1)
                page.evaluate("""
                    () => {
                        window.scrollTo(0, document.body.scrollHeight * 2 / 3);
                    }
                """)
                time.sleep(1)
                page.evaluate("""
                    () => {
                        window.scrollTo(0, document.body.scrollHeight);
                    }
                """)
                time.sleep(2)
                
                # 全页长截图
                page.screenshot(path=str(screenshot_path), full_page=True)
            finally:
                context.close()
                browser.close()

    def archive_article(self, aid: str, capture_screenshot: bool = True) -> Dict[str, Any]:
        """单篇文章完整归档流水线"""
        art_dir = self.output_base / "articles" / aid
        art_dir.mkdir(parents=True, exist_ok=True)
        images_dir = art_dir / "images"

        print(f"\n[{aid}] 开始归档...")

        # 1. 抓取 Draft 原文
        draft = self.fetch_draft(aid)
        original_json_path = art_dir / "original.json"
        original_json_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [1/6] 原始草稿已保存: {original_json_path.name}")

        # 2. 抓取评论
        comments_data = self.fetch_comments(aid)
        comments_json_path = art_dir / "comments.json"
        comments_json_path.write_text(json.dumps(comments_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [2/6] 评论已保存: 共 {comments_data['total_count']} 条评论")

        # 3. 构造元数据
        created_ts = draft.get("created", 0)
        updated_ts = draft.get("updated", 0)
        meta = {
            "id": aid,
            "title": draft.get("title", ""),
            "author": draft.get("author", {}),
            "created": created_ts,
            "created_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_ts)) if created_ts else "",
            "updated": updated_ts,
            "updated_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(updated_ts)) if updated_ts else "",
            "url": f"https://zhuanlan.zhihu.com/p/{aid}",
            "topics": [t.get("name") for t in draft.get("topics", []) if isinstance(t, dict)],
            "voteup_count": draft.get("reaction", {}).get("statistics", {}).get("like_count", 0),
            "comment_count": comments_data.get("total_count", 0),
            "read_count": "N/A（知乎 API 未开放）",
            "copyright_permission": draft.get("copyright_permission"),
            "comment_permission": draft.get("comment_permission"),
        }
        meta_json_path = art_dir / "meta.json"
        meta_json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [3/6] 元数据已保存: {meta_json_path.name}")

        # 4. 提取原图并本地化 HTML
        raw_html = draft.get("content", "")
        body_html_path = art_dir / "body.html"
        body_html_path.write_text(raw_html, encoding="utf-8")
        
        images_info, localized_html = self.download_images(raw_html, images_dir)
        (art_dir / "body_local.html").write_text(localized_html, encoding="utf-8")
        print(f"  [4/6] 图片已下载: {len(images_info)} 张原图本地化完成")

        # 5. 生成 Word (.docx)
        docx_path = art_dir / "body.docx"
        self.export_word(meta, localized_html, images_dir, docx_path)
        print(f"  [5/6] Word 文档已生成: {docx_path.name} ({docx_path.stat().st_size} bytes)")

        # 6. 截图 (Playwright)
        screenshot_path = art_dir / "screenshot.png"
        if capture_screenshot:
            try:
                self.capture_screenshot_playwright(aid, screenshot_path)
                print(f"  [6/6] 全页长截图已捕获: {screenshot_path.name} ({screenshot_path.stat().st_size} bytes)")
            except Exception as e:
                print(f"  [6/6] 截图捕获失败: {e}")
        else:
            print("  [6/6] 截图跳过 (capture_screenshot=False)")

        # 7. 汇总单篇清单
        files_manifest = {
            "meta.json": {"size": meta_json_path.stat().st_size, "sha256": compute_sha256(meta_json_path)},
            "original.json": {"size": original_json_path.stat().st_size, "sha256": compute_sha256(original_json_path)},
            "body.html": {"size": body_html_path.stat().st_size, "sha256": compute_sha256(body_html_path)},
            "body.docx": {"size": docx_path.stat().st_size, "sha256": compute_sha256(docx_path)},
            "comments.json": {"size": comments_json_path.stat().st_size, "sha256": compute_sha256(comments_json_path)},
            "screenshot.png": {
                "size": screenshot_path.stat().st_size if screenshot_path.exists() else 0,
                "sha256": compute_sha256(screenshot_path) if screenshot_path.exists() else "",
            },
            "images_count": len(images_info),
            "images_downloaded": sum(1 for img in images_info if img.get("size", 0) > 0),
        }
        
        # 完整性判定 (每项必需 > 0 字节)
        is_complete = (
            files_manifest["meta.json"]["size"] > 0 and
            files_manifest["original.json"]["size"] > 0 and
            files_manifest["body.html"]["size"] > 0 and
            files_manifest["body.docx"]["size"] > 0 and
            files_manifest["comments.json"]["size"] > 0 and
            (not capture_screenshot or files_manifest["screenshot.png"]["size"] > 5000) and
            files_manifest["images_downloaded"] == files_manifest["images_count"]
        )

        item_result = {
            "id": aid,
            "title": meta["title"],
            "url": meta["url"],
            "is_complete": is_complete,
            "files": files_manifest,
        }
        (art_dir / "article_manifest.json").write_text(json.dumps(item_result, ensure_ascii=False, indent=2), encoding="utf-8")
        return item_result


def build_batch_checklist(output_base: Path, results: List[Dict[str, Any]]):
    """生成整批任务的 manifest.json 和人类可读 checklist.md"""
    manifest_data = {
        "timestamp": time.time(),
        "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_articles": len(results),
        "complete_count": sum(1 for r in results if r["is_complete"]),
        "incomplete_count": sum(1 for r in results if not r["is_complete"]),
        "items": results
    }
    
    # 1. 写入 manifest.json
    manifest_file = output_base / "manifest.json"
    manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. 写入 checklist.md
    md_lines = [
        "# 知乎文章归档核对与门禁清单 (Archive Checklist)",
        f"> 生成时间: {manifest_data['formatted_time']}  |  总文章数: {len(results)}  |  100% 完整通过: {manifest_data['complete_count']}  |  异常/不全: {manifest_data['incomplete_count']}",
        "",
        "| 序号 | 文章 ID | 文章标题 | 原始草稿 | 富文本 HTML | Word 文档 | 图片 (下载/总数) | 评论 | 网页截图 | 门禁状态 |",
        "| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for idx, r in enumerate(results, start=1):
        f = r["files"]
        orig_ok = "✓" if f["original.json"]["size"] > 0 else "✗"
        html_ok = "✓" if f["body.html"]["size"] > 0 else "✗"
        docx_ok = f"✓ ({f['body.docx']['size']//1024}KB)" if f["body.docx"]["size"] > 0 else "✗"
        img_stat = f"{f['images_downloaded']}/{f['images_count']}"
        comment_ok = "✓" if f["comments.json"]["size"] > 0 else "✗"
        shot_ok = f"✓ ({f['screenshot.png']['size']//1024}KB)" if f["screenshot.png"]["size"] > 0 else "✗"
        status_badge = "🟢 PASS" if r["is_complete"] else "🔴 FAIL"

        title_esc = r["title"].replace("|", "\\|")
        md_lines.append(
            f"| {idx} | [{r['id']}](https://zhuanlan.zhihu.com/p/{r['id']}) | {title_esc} | {orig_ok} | {html_ok} | {docx_ok} | {img_stat} | {comment_ok} | {shot_ok} | **{status_badge}** |"
        )

    checklist_file = output_base / "checklist.md"
    checklist_file.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\n[✓] 批次核对清单已生成: {checklist_file}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="知乎专栏文章全量归档工具")
    parser.add_argument("--cookie-file", default="/Users/rancho/QingyiEdu/cookie.txt", help="知乎 cookie 文件路径")
    parser.add_argument("--output", default="./archive_output", help="输出目录")
    parser.add_argument("--aid", default="", help="指定单篇文章 ID 进行单篇归档测试")
    parser.add_argument("--limit", type=int, default=1, help="批量归档篇数限制 (0 表示全量)")
    parser.add_argument("--no-screenshot", action="store_true", help="跳过 Playwright 截图")
    args = parser.parse_args()

    cookie_p = Path(args.cookie_file)
    if not cookie_p.exists():
        cookie_p = Path("./cookie.txt")
    if not cookie_p.exists():
        print(f"[!] 找不到 cookie 文件，请确认路径: {args.cookie_file}")
        sys.exit(1)

    raw_cookie = cookie_p.read_text(encoding="utf-8").strip()
    # 提取有效 cookie 行
    clean_cookie = ""
    for line in raw_cookie.splitlines():
        line = line.strip()
        if "z_c0" in line:
            clean_cookie = line
            break
    if not clean_cookie:
        clean_cookie = raw_cookie.splitlines()[0]

    out_base = Path(args.output).resolve()
    archiver = ZhihuArchiver(clean_cookie, out_base)
    
    # 身份认证
    archiver.authenticate()

    results = []
    if args.aid:
        # 单篇归档
        res = archiver.archive_article(args.aid, capture_screenshot=not args.no_screenshot)
        results.append(res)
    else:
        # 列表枚举并归档
        articles = archiver.list_my_articles(limit=args.limit)
        for it in articles:
            res = archiver.archive_article(it["id"], capture_screenshot=not args.no_screenshot)
            results.append(res)

    build_batch_checklist(out_base, results)


if __name__ == "__main__":
    main()
