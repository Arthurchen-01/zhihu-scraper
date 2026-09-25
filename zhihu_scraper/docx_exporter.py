# -*- coding: utf-8 -*-
"""
Word (.docx) 导出组件
用于将知乎文章及回答高保真导出为格式规范、图文排版的 Word 文档。
"""

import io
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from bs4 import BeautifulSoup


def generate_docx_for_item(item_meta: Dict[str, Any], content_html: str, session=None) -> bytes:
    """生成单个条目（文章/回答）的 Word (.docx) 字节流"""
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        
    title = (item_meta.get("title") or "未命名内容").strip()
    title_p = doc.add_paragraph()
    title_run = title_p.add_run(title)
    title_run.font.size = Pt(18)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(17, 24, 39)
    title_p.paragraph_format.space_after = Pt(10)
    
    # 元数据表格
    table = doc.add_table(rows=5, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    
    auth = item_meta.get("author_name") or (item_meta.get("author") or {}).get("name") or "知乎用户"
    pub_time = str(item_meta.get("created_formatted") or item_meta.get("created") or "")
    vc = item_meta.get("voteup_count", 0)
    cc = item_meta.get("comment_count", 0)
    meta_rows = [
        ("内容类型 / ID", f"[{item_meta.get('type', 'article')}] {item_meta.get('id', '')}"),
        ("作者信息", str(auth)),
        ("发布/更新时间", pub_time),
        ("获赞 / 评论数据", f"👍 赞同: {vc}  |  💬 评论: {cc}"),
        ("知乎原始链接", str(item_meta.get("url", ""))),
    ]
    for idx, (k, v) in enumerate(meta_rows):
        cells = table.rows[idx].cells
        cells[0].text = k
        if cells[0].paragraphs and cells[0].paragraphs[0].runs:
            cells[0].paragraphs[0].runs[0].font.bold = True
            cells[0].paragraphs[0].runs[0].font.size = Pt(9.5)
        cells[1].text = v
        if cells[1].paragraphs and cells[1].paragraphs[0].runs:
            cells[1].paragraphs[0].runs[0].font.size = Pt(9.5)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(12)
    
    # 正文富文本解析
    soup = BeautifulSoup(content_html or "", "html.parser")
    for elem in soup.children:
        if not elem.name:
            t = str(elem).strip()
            if t:
                p = doc.add_paragraph(t)
                p.paragraph_format.space_after = Pt(6)
            continue
        tag = elem.name.lower()
        if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            level = min(int(tag[1]), 3)
            h = doc.add_heading(elem.get_text().strip(), level=level)
            h.paragraph_format.space_before = Pt(10)
            h.paragraph_format.space_after = Pt(4)
        elif tag == "p":
            imgs = elem.find_all("img")
            if imgs and session:
                for img in imgs:
                    src = img.get("data-actualsrc") or img.get("src") or ""
                    if src.startswith("http"):
                        try:
                            ir = session.get(src, timeout=6)
                            if ir.status_code == 200 and len(ir.content) > 100:
                                p_img = doc.add_paragraph()
                                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                p_img.add_run().add_picture(io.BytesIO(ir.content), width=Inches(5.5))
                                p_img.paragraph_format.space_after = Pt(6)
                        except Exception:
                            pass
            text = elem.get_text().strip()
            if text:
                p = doc.add_paragraph(text)
                p.paragraph_format.line_spacing = 1.25
                p.paragraph_format.space_after = Pt(6)
        elif tag == "blockquote":
            q_text = elem.get_text().strip()
            if q_text:
                p = doc.add_paragraph()
                r = p.add_run(f"“ {q_text} ”")
                r.font.italic = True
                r.font.color.rgb = RGBColor(100, 116, 139)
                p.paragraph_format.left_indent = Inches(0.4)
                p.paragraph_format.space_after = Pt(6)
        elif tag in ["ul", "ol"]:
            for li in elem.find_all("li"):
                li_t = li.get_text().strip()
                if li_t:
                    p = doc.add_paragraph(li_t, style='List Bullet' if tag == 'ul' else 'List Number')
                    p.paragraph_format.space_after = Pt(3)
        elif tag in ["figure", "img"] and session:
            imgs = elem.find_all("img") if tag == "figure" else [elem]
            for img in imgs:
                src = img.get("data-actualsrc") or img.get("src") or ""
                if src.startswith("http"):
                    try:
                        ir = session.get(src, timeout=6)
                        if ir.status_code == 200 and len(ir.content) > 100:
                            p_img = doc.add_paragraph()
                            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                            p_img.add_run().add_picture(io.BytesIO(ir.content), width=Inches(5.5))
                            p_img.paragraph_format.space_after = Pt(6)
                    except Exception:
                        pass
                        
    out_buf = io.BytesIO()
    doc.save(out_buf)
    return out_buf.getvalue()

def export_items(signer, items: List[Dict[str, Any]]) -> Tuple[str, bytes, str]:
    """
    批量或单篇导出选中的 items (文章或回答)。
    返回 (filename, bytes, content_type)
    """
    import zipfile
    docs: List[Tuple[str, bytes]] = []
    for it in items:
        iid = str(it.get("id") or "").strip()
        if not iid:
            continue
        itype = str(it.get("type") or "article")
        title = it.get("title") or ""
        content_html = ""
        meta = {
            "id": iid,
            "type": itype,
            "title": title,
            "voteup_count": it.get("voteup_count", 0),
            "comment_count": it.get("comment_count", 0),
            "url": it.get("url") or (f"https://zhuanlan.zhihu.com/p/{iid}" if itype == "article" else f"https://www.zhihu.com/answer/{iid}")
        }
        try:
            if itype == "article":
                draft = signer.get_article_draft(iid)
                title = draft.get("title") or title
                content_html = draft.get("content") or ""
                meta["title"] = title
                meta["author_name"] = (draft.get("author") or {}).get("name") or "冠军班 胡启岩"
                cts = draft.get("created") or draft.get("created_time")
                if cts:
                    meta["created_formatted"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(cts))
            elif itype == "answer":
                ar = signer.s.get(f"https://www.zhihu.com/api/v4/answers/{iid}?include=content,voteup_count,comment_count,created_time,updated_time,question", timeout=12)
                if ar.status_code == 200:
                    adata = ar.json()
                    q = adata.get("question") or {}
                    meta["title"] = f"回答：{q.get('title') or title}"
                    content_html = adata.get("content") or ""
                    meta["author_name"] = (adata.get("author") or {}).get("name") or "冠军班 胡启岩"
                    meta["voteup_count"] = adata.get("voteup_count", it.get("voteup_count", 0))
                    meta["comment_count"] = adata.get("comment_count", it.get("comment_count", 0))
                    cts = adata.get("created_time")
                    if cts:
                        meta["created_formatted"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(cts))
            docx_data = generate_docx_for_item(meta, content_html, session=signer.s)
            safe_name = re.sub(r'[\/\\:*?"<>|]', "_", meta["title"])[:50].strip() or f"{itype}_{iid}"
            docs.append((f"{safe_name}.docx", docx_data))
        except Exception as exc:
            pass

    if not docs:
        raise ValueError("未能成功抓取并生成 Word 文档内容")

    if len(docs) == 1:
        fname, data = docs[0]
        return fname, data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, (fname, data) in enumerate(docs, 1):
                zf.writestr(f"{idx:03d}_{fname}", data)
        zname = f"知乎内容导出_Word_{time.strftime('%Y%m%d_%H%M%S')}.zip"
        return zname, zbuf.getvalue(), "application/zip"
