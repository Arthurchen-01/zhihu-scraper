"""清一新教育 · 控制面 API 路由（挂载到现有 FastAPI 应用）。

控制面职责边界
--------------
* 只读：枚举调用者本人的知乎资产（文章 / 想法 / 回答）
* 编排：把勾选结果固化成任务
* 观测：聚合本地执行器上报的进度与结果
* 分发：向本地执行器下发任务与执行命令

真正的知乎写入由本地执行器完成（见 qingyi_worker.py），
目的是让编辑行为来自操作者自身网络身份而非机房 IP。
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import (FileResponse, HTMLResponse, PlainTextResponse,
                               Response, StreamingResponse)
from pydantic import BaseModel

from ..qingyi import BRAND, QingyiTitleSigner, RatePolicy
from .. import qingyi_jobs as QJ
from urllib.parse import quote

from ..docx_exporter import export_items, generate_docx_for_item
from .. import high_value_essays

# ── Word 导出任务状态存储（内存，进程生命周期）───────────────────────────────
_DOCX_JOBS: Dict[str, Dict] = {}
_DOCX_JOBS_LOCK = threading.Lock()

router = APIRouter(prefix="/api/qy", tags=["qingyi"])

TITLE_PREFIX = f"【{BRAND}】"

# 赞助署名与联系信息。
# 按用户要求：只出现在工作台页面，**不写入任何文章正文**。
SPONSOR = {
    "line": "清一新教育-冠军一班-谢迪安友情资助",
    "support": {
        "label": "支持本计划 · 联系项目负责人",
        "wechat": "{微信号·待补}",
        "placeholder": True,
    },
    "business": {
        "label": "企业 AI 供应对接",
        "people": ["谢迪安", "陈冠宇"],
        "wechat": "{微信号·待补}",
        "placeholder": True,
    },
    "note": "署名与联系方式仅出现在本工作台页面，不写入任何文章正文。",
}

# 每日写入上限（防风控主闸）。用户口径：每天 120 篇，不要一次性全量上线。
# 网页上的「每日上限」选择会随部署包下发到执行器（perday.txt），此处为默认值。
DAILY_CAP = int(os.environ.get("QY_DAILY_CAP", "120"))

# 站点访问密钥（模块级单一来源）。执行器/启动脚本由服务端直接携带，
# 用户不需要知道也不需要输入它。
SITE_KEY = os.environ.get("QY_SITE_KEY", "guanjun2026")


# --------------------------------------------------------------------------- #
# AI 审核（DeepSeek）：由模型决定每篇加几处品牌词、加在哪里
# --------------------------------------------------------------------------- #
# 密钥来源：环境变量 DEEPSEEK_API_KEY 优先，其次 data/deepseek_key.txt（不入库）。
# 端点可用 QY_AI_URL / QY_AI_MODEL 覆盖（默认自建中转 156.225.31.92:7863）。
# 注意：deepseek-v4.1-flash 带思维链，思维链同样计入 max_tokens；
# 预算给小了 content 会被截成空串，导致审核静默回退内置规则。
DEEPSEEK_URL = os.environ.get(
    "QY_AI_URL", "http://156.225.31.92:7863/v1/chat/completions")
DEEPSEEK_MODEL = os.environ.get("QY_AI_MODEL", "deepseek-v4.1-flash")

AI_REVIEW_PROMPT = (
    "你在为一篇即将加入品牌词「清一新教育」的知乎文章做植入审核。\n"
    "品牌词加入方式（平台规则已固定，不可更改）：\n"
    "- 标题：在最前面加「【清一新教育】」\n"
    "- 正文：在句子末尾加署名式括注「（清一新教育）」，不删改任何原有文字\n"
    "\n"
    "你会收到：文章标题；正文纯文本（可能截断）；正文候选位置列表"
    "（每项含序号 idx、插入点前文 anchor、所在段落预览 para）。\n"
    "\n"
    "请只输出 JSON（不要 markdown 代码块、不要其他文字）：\n"
    '{"title_add": true, "picks": [{"idx": 0, "reason": "不超过18字的理由"}]}\n'
    "\n"
    "判定规则：\n"
    "- title_add：除非标题已含「清一/新教育」字样、或加了会明显语义混乱，否则为 true。\n"
    "- picks：按用户消息里给出的数量上限挑（宁少勿多，候选不够就少挑）。"
    "优先与教育/成长/学习/方法论相关的"
    "段落；首段与结尾更自然；避开引文、列表、代码、反问句。宁缺毋滥：正文短于 300 字"
    "或主题与教育完全无关时挑 0~1 个。\n"
    "- idx 必须来自候选列表；每个 pick 给不超过 18 字的 reason。"
)


def _load_ds_key() -> str:
    k = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if k:
        return k
    try:
        return Path("data/deepseek_key.txt").read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return ""


def _ai_review_one(cookie: str, aid: str, title: str,
                   want_body: bool, want_hits: int = 1) -> Dict[str, Any]:
    """单篇 AI 审核。任何失败都回退内置规则（used_ai=False），绝不阻塞建任务。

    返回: {ok, used_ai, title, title_add, picks:[{anchor,reason,para}],
           candidates, note}
    """
    import requests as _rq

    from .. import qy_content as qc

    signer = QingyiTitleSigner(cookie=cookie, backup_dir=Path("data/qyedu_backup"))
    draft = signer.get_article_draft(str(aid))
    body = draft.get("content") or ""
    t = (draft.get("title") or title or "").strip()

    # 候选池要比用户要的处数更大，AI 才有挑选余地
    _cap = int(getattr(qc, "_MAX_BODY_HITS", 1) or 1)
    want_hits = max(1, min(int(want_hits or 1), _cap))
    cands = qc.scan_scenes(body, limit=max(4, want_hits))
    cand_list = [{"idx": i, "anchor": c.anchor, "para": c.para_text[:90]}
                 for i, c in enumerate(cands)]

    fallback = {
        "ok": True, "used_ai": False, "title": t, "title_add": True,
        "picks": ([{"anchor": c.anchor, "reason": c.reason,
                    "para": c.para_text[:90]} for c in cands[:want_hits]]
                  if want_body else []),
        "candidates": cand_list,
        "note": "AI 审核不可用，已用内置规则挑选（与既往行为一致）。",
    }

    key = _load_ds_key()
    if not key:
        return fallback

    try:
        plain = re.sub(r"\s+", " ", qc._ANY_TAG_RE.sub("", body)).strip()
        cand_txt = "\n".join(
            f"- idx={c['idx']} anchor={c['anchor']!r} para={c['para']}"
            for c in cand_list) or "（无可植入候选）"
        user_msg = (f"文章标题：{t}\n\n正文（纯文本）：\n{plain[:3500]}\n\n"
                    f"候选位置列表：\n{cand_txt}\n\n"
                    f"本次最多挑 {want_hits} 个位置（候选不够就少挑，宁缺毋滥）。")
        resp = _rq.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": AI_REVIEW_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.2,
                "reasoning_effort": "low",
                "max_tokens": 8000,
                "response_format": {"type": "json_object"},
                "stream": False,
            },
            timeout=180,
        )
        resp.raise_for_status()
        _j = resp.json()
        _ch = _j["choices"][0]
        content = (_ch["message"].get("content") or "").strip()
        if not content:
            raise RuntimeError(
                "AI 返回空内容（finish_reason=%s，思维链吃满 max_tokens）"
                % _ch.get("finish_reason"))
        content = re.sub(r"^```(?:json)?|```$", "", content.strip(),
                         flags=re.M).strip()
        data = json.loads(content)
        title_add = bool(data.get("title_add", True))
        picks: List[Dict[str, Any]] = []
        for p in (data.get("picks") or [])[:want_hits]:
            try:
                idx = int(p.get("idx"))
            except Exception:  # noqa: BLE001
                continue
            if 0 <= idx < len(cands):
                c = cands[idx]
                picks.append({"anchor": c.anchor,
                              "reason": str(p.get("reason") or "")[:40],
                              "para": c.para_text[:90]})
        return {
            "ok": True, "used_ai": True, "title": t, "title_add": title_add,
            "picks": picks, "candidates": cand_list,
            "note": ("AI 已审核" if picks
                     else "AI 已审核：本文正文无需植入"),
        }
    except Exception as exc:  # noqa: BLE001
        fallback["note"] = (f"AI 审核失败（{type(exc).__name__}），"
                            "已用内置规则兜底。")
        return fallback


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #

class InspectReq(BaseModel):
    cookie: str
    cap: int = 0
    include_pins: bool = True
    include_answers: bool = True


class PlanReq(BaseModel):
    cookie: str
    ids: List[str] = []
    types: List[str] = ["article"]


class CreateJobReq(BaseModel):
    items: List[Dict[str, Any]]
    policy: Optional[Dict[str, Any]] = None
    mode: str = "local"
    action_mode: str = "replace_content"  # "replace_content" (法律/国学经典替换) 或 "brand_signature" (品牌词)
    preset: str = "random_all"            # "random_all", "law", "classics", "custom"
    custom_title: str = ""
    custom_content: str = ""
    # 每篇固定 2 处：标题 1 处 + 正文 1 处
    title: bool = True
    inject_body: bool = True
    body_hits: int = 1


class ExportDocxReq(BaseModel):
    cookie: str
    items: List[Dict[str, Any]] = []


class ScanScenesReq(BaseModel):
    """「全面检索可加入场景」——只读扫描，不写入任何内容。"""
    cookie: str = ""
    id: str
    hits: int = 1


class AiReviewReq(BaseModel):
    """单篇 AI 审核请求（只读：拉正文 + 调模型，不写入知乎）。"""
    cookie: str
    id: str
    title: str = ""
    want_body: bool = True
    want_hits: int = 1        # 本篇文章期望的正文植入处数（1~5）


class BundleReq(BaseModel):
    """部署包下载：cookie 可选（部署器会自动读取本机登录）。"""
    cookie: str = ""
    per_day: int = 0          # 网页上的「每日上限」选择，随包下发


class WorkerClaimReq(BaseModel):
    worker_id: str
    mode: str = "local"


class WorkerItemReq(BaseModel):
    job_id: str
    record: Dict[str, Any]


class WorkerLogReq(BaseModel):
    job_id: str
    message: str


class WorkerFinishReq(BaseModel):
    job_id: str
    summary: Optional[Dict[str, Any]] = None


class HeartbeatReq(BaseModel):
    job_id: str
    worker_id: str


# --------------------------------------------------------------------------- #
# Discovery (read-only)
# --------------------------------------------------------------------------- #

@router.post("/inspect")
def qy_inspect(req: InspectReq):
    """只读枚举：看看这个账号名下有哪些内容、哪些已带品牌词。"""
    cookie = (req.cookie or "").strip()
    if not cookie:
        raise HTTPException(status_code=400, detail="请提供知乎登录凭证")

    signer = QingyiTitleSigner(cookie=cookie,
                               backup_dir=Path("data/qyedu_backup"))
    try:
        me = signer.verify()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"凭证校验失败：{exc}")

    articles = signer.list_articles(cap=req.cap)
    art_diag = dict(getattr(signer, "last_diag", {}) or {})
    pins = signer.list_pins(cap=req.cap) if req.include_pins else []
    pin_diag = dict(getattr(signer, "last_diag", {}) or {}) if req.include_pins else {}
    answers = signer.list_answers(cap=req.cap) if req.include_answers else []
    ans_diag = dict(getattr(signer, "last_diag", {}) or {}) if req.include_answers else {}

    def _stat(rows: List[Dict[str, Any]]) -> Dict[str, int]:
        branded = sum(1 for r in rows if r.get("has_brand"))
        return {"total": len(rows), "branded": branded,
                "pending": len(rows) - branded}

    items: List[Dict[str, Any]] = []
    for r in articles + pins + answers:
        r_rand = high_value_essays.get_essay_by_preset(r["id"], "random_all")["title"]
        r_law = high_value_essays.get_essay_by_preset(r["id"], "law")["title"]
        r_cla = high_value_essays.get_essay_by_preset(r["id"], "classics")["title"]
        items.append({
            "id": r["id"],
            "type": r["type"],
            "kind_label": r["kind_label"],
            "title": r["title"],
            "title_after": r["title"] if r.get("has_brand")
                           else f"{TITLE_PREFIX}{r['title']}",
            "replacement_titles": {
                "random_all": r_rand,
                "law": r_law,
                "classics": r_cla,
            },
            "has_brand": r.get("has_brand", False),
            "url": r.get("url", ""),
            "created": r.get("created"),
            "updated": r.get("updated"),
            "voteup_count": r.get("voteup_count") or 0,
            "comment_count": r.get("comment_count") or 0,
            "excerpt": r.get("excerpt", ""),
            "editable": r["type"] == "article",
            "note": r.get("note", ""),
        })

    # 交叉校验：账号自报的篇数 vs 实际枚举到的。对不上就是「被挡了」而不是「真没有」，
    # 必须说清楚 —— 否则用户只看到一排 0，分不清是空账号还是请求失败。
    warn: List[str] = []
    _self_art = me.get("articles_count")
    if isinstance(_self_art, int) and _self_art > 0 and not articles:
        warn.append("账号自报 %d 篇文章，但一篇都没取到（%s）"
                    % (_self_art, art_diag.get("error") or "原因未知"))
    if art_diag.get("failed"):
        warn.append("有 %d 页没取到（偏移 %s），结果可能不全"
                    % (len(art_diag["failed"]), art_diag["failed"][:8]))
    if art_diag.get("error") and articles:
        warn.append("部分页失败：%s" % art_diag["error"])

    return {
        "ok": True,
        "brand": BRAND,
        "title_prefix": TITLE_PREFIX,
        "scope": "title_and_body",
        "author": me,
        "stats": {
            "articles": _stat(articles),
            "pins": _stat(pins),
            "answers": _stat(answers),
        },
        "items": items,
        "items_count": len(items),
        "warning": "；".join(warn),
        "diag": {"articles": art_diag, "pins": pin_diag, "answers": ans_diag},
    }


# --------------------------------------------------------------------------- #
# Job orchestration
# --------------------------------------------------------------------------- #

def _normalise_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """补齐条目里的 url / kind_label，避免下游报告出现空链接。"""
    out: List[Dict[str, Any]] = []
    for raw in items or []:
        it = dict(raw or {})
        it["url"] = _item_url(it) if not str(it.get("url") or "").strip() else it["url"]
        out.append(it)
    return out



@router.post("/export/docx")
def qy_export_docx(req: ExportDocxReq):
    """启动后台多线程 Word 导出任务，立即返回 job_id。
    前端通过 GET /export/docx/progress/{job_id} SSE 轮询进度，
    完成后 GET /export/docx/download/{job_id} 取文件。
    """
    import uuid
    cookie = (req.cookie or "").strip()
    if not cookie:
        raise HTTPException(status_code=400, detail="请提供知乎登录凭证")
    if not req.items:
        raise HTTPException(status_code=400, detail="未选择任何条目")
    signer = QingyiTitleSigner(cookie=cookie, backup_dir=Path("data/qyedu_backup"))
    try:
        signer.verify()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"凭证校验失败：{exc}")

    job_id = str(uuid.uuid4())[:12]
    state = {
        "id": job_id,
        "status": "running",       # running | done | error
        "total": len(req.items),
        "done": 0,
        "failed": 0,
        "logs": [],                # list of log strings shown in UI
        "started_at": time.time(),
        "finished_at": None,
        "filename": None,
        "data": None,              # bytes – filled when done
        "media_type": None,
        "error": None,
    }
    with _DOCX_JOBS_LOCK:
        _DOCX_JOBS[job_id] = state

    def _run(items, state):
        """Background thread: generate docx(s) with per-item concurrency."""
        import zipfile, io as _io, concurrent.futures
        # 时间模块必须先绑定再用：Python 里 import 就是赋值语句，只要函数体内
        # 出现过这行导入，该名字就属于本函数的局部作用域；在它真正执行之前引用
        # 就会抛 UnboundLocalError。原来这行写在 L594，而 L575 拼装导出报告时
        # 已经用到了它 —— 于是「多篇导出」必崩在打包那一步：任务永远停在
        # running，下载接口永远 404。单篇走另一个分支，所以完全看不出来。
        import datetime as _dt
        from ..docx_exporter import generate_docx_for_item
        # 评论抓取：旧实现里这一句从来不存在，所以 Word 里只有评论「数量」
        # 那个数字，一条评论正文都没有，UI 却写着「包含原图与评论下载」。
        from ..comment_fetch import fetch_comments

        results = {}     # item index -> (fname, bytes)
        errors  = {}
        notes   = {}     # item index -> 评论取回情况简述

        def _one(idx_item):
            idx, it = idx_item
            iid  = str(it.get("id") or "")
            itype = str(it.get("type") or "article")
            title = it.get("title") or ""
            meta  = {
                "id": iid, "type": itype, "title": title,
                "voteup_count":  it.get("voteup_count", 0),
                "comment_count": it.get("comment_count", 0),
                "url": it.get("url") or (
                    f"https://zhuanlan.zhihu.com/p/{iid}"
                    if itype == "article"
                    else f"https://www.zhihu.com/answer/{iid}"
                ),
            }
            t0 = time.time()
            try:
                if itype == "article":
                    draft = signer.get_article_draft(iid)
                    title = draft.get("title") or title
                    meta["title"] = title
                    meta["author_name"] = (draft.get("author") or {}).get("name") or ""
                    cts = draft.get("created") or draft.get("created_time")
                    if cts:
                        import datetime
                        meta["created_formatted"] = datetime.datetime.fromtimestamp(cts).strftime("%Y-%m-%d %H:%M:%S")
                    content_html = draft.get("content") or ""
                elif itype == "answer":
                    ar = signer.s.get(
                        f"https://www.zhihu.com/api/v4/answers/{iid}"
                        "?include=content,voteup_count,comment_count,created_time,question",
                        timeout=15)
                    if ar.status_code == 200:
                        adata = ar.json()
                        q = adata.get("question") or {}
                        meta["title"] = f"回答：{q.get('title') or title}"
                        content_html = adata.get("content") or ""
                        meta["voteup_count"]  = adata.get("voteup_count", meta["voteup_count"])
                        meta["comment_count"] = adata.get("comment_count", meta["comment_count"])
                        meta["author_name"] = (adata.get("author") or {}).get("name") or ""
                        cts = adata.get("created_time")
                        if cts:
                            import datetime
                            meta["created_formatted"] = datetime.datetime.fromtimestamp(cts).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        content_html = ""
                else:
                    content_html = ""

                # ---- 评论：真抓，并且如实汇报取回比例 ----
                note = ""
                try:
                    cm = fetch_comments(
                        signer.s, itype, iid,
                        nominal_count=int(meta.get("comment_count") or 0))
                    meta["_comments"] = cm
                    if cm.get("error"):
                        note = f"评论抓取出错：{cm['error']}"
                    elif (cm.get("nominal") is not None
                          and cm["fetched"] < cm["nominal"]):
                        note = (f"评论 {cm['fetched']}/{cm['nominal']}"
                                f"（知乎游标分页限制，未取满）")
                    else:
                        note = f"评论 {cm['fetched']} 条"
                except Exception as cexc:  # noqa: BLE001
                    meta["_comments"] = {}
                    note = f"评论抓取异常：{type(cexc).__name__}: {cexc}"

                data = generate_docx_for_item(meta, content_html, session=signer.s)
                elapsed = round(time.time() - t0, 1)
                safe = re.sub(r'[/\\:*?"<>|]', "_", meta["title"])[:50].strip() or f"{itype}_{iid}"
                return idx, safe, data, elapsed, None, note
            except Exception as exc:
                return idx, None, None, None, str(exc)[:120], ""

        # Concurrency: 4 threads (safe for Zhihu rate limits)
        max_workers = min(4, len(items))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_one, (i, it)): i for i, it in enumerate(items)}
            for fut in concurrent.futures.as_completed(futures):
                idx, fname, data, elapsed, err, note = fut.result()
                if err:
                    errors[idx] = err
                    with _DOCX_JOBS_LOCK:
                        state["failed"] += 1
                        state["done"]   += 1
                        state["logs"].append(f"✗ [{items[idx].get('title','')[:30]}] 失败：{err}")
                else:
                    results[idx] = (fname, data)
                    if note:
                        notes[idx] = note
                    with _DOCX_JOBS_LOCK:
                        state["done"] += 1
                        elapsed_total = time.time() - state["started_at"]
                        done_n = state["done"]
                        speed  = round(done_n / elapsed_total, 2) if elapsed_total > 0 else 0
                        eta = round((state["total"] - done_n) / speed, 0) if speed > 0 else 0
                        state["logs"].append(
                            f"✓ [{items[idx].get('title','')[:28]}…] {elapsed}s"
                            + (f" · {note}" if note else "")
                            + f" — 速率 {speed} 篇/s，ETA {int(eta)}s"
                        )

        # Pack results
        if not results:
            state["status"] = "error"
            state["error"]  = "所有条目均生成失败"
            state["finished_at"] = time.time()
            return

        if len(results) == 1:
            idx = list(results.keys())[0]
            fname, data = results[idx]
            state["filename"]   = fname + ".docx"
            state["data"]       = data
            state["media_type"] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            import zipfile, io as _zio
            zbuf = _zio.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i in sorted(results.keys()):
                    fname, data = results[i]
                    zf.writestr(f"{i+1:03d}_{fname}.docx", data)
                # 失败条目与评论取回情况必须随包交付 ——
                # 不能只活在浏览器的进度条里，关掉页面就没了。
                _rep = [
                    "知乎内容导出报告",
                    "生成时间：%s" % _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "请求 %d 篇，成功 %d 篇，失败 %d 篇"
                    % (state["total"], len(results), len(errors)),
                    "",
                ]
                if errors:
                    _rep.append("【失败条目】")
                    for i in sorted(errors):
                        _rep.append("  · %s  %s"
                                    % (str(items[i].get("title", ""))[:40],
                                       errors[i]))
                    _rep.append("")
                if notes:
                    _rep.append("【评论取回情况】")
                    for i in sorted(notes):
                        _rep.append("  · %s  %s"
                                    % (str(items[i].get("title", ""))[:40],
                                       notes[i]))
                zf.writestr("_导出报告.txt", "\n".join(_rep))
            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            state["filename"]   = f"知乎内容导出_Word_{ts}.zip"
            state["data"]       = zbuf.getvalue()
            state["media_type"] = "application/zip"

        state["status"]      = "done"
        state["finished_at"] = time.time()
        total_time = round(state["finished_at"] - state["started_at"], 1)
        state["logs"].append(
            f"✅ 全部完成！共 {len(results)} 篇成功"
            + (f"，{len(errors)} 篇失败" if errors else "")
            + f"，总耗时 {total_time}s"
        )

    threading.Thread(target=_run, args=(req.items, state), daemon=True).start()
    return {"ok": True, "job_id": job_id, "total": len(req.items)}


@router.get("/export/docx/progress/{job_id}")
def qy_export_docx_progress(job_id: str):
    """SSE 流：实时推送每篇 Word 导出进度（done/total/speed/ETA/log）。"""
    def _stream():
        import json as _json
        last_log_idx = 0
        while True:
            with _DOCX_JOBS_LOCK:
                state = _DOCX_JOBS.get(job_id)
            if state is None:
                yield f"data: {_json.dumps({'error': '任务不存在'}, ensure_ascii=False)}\n\n"
                return
            
            elapsed = time.time() - state["started_at"]
            done_n  = state["done"]
            speed   = round(done_n / elapsed, 2) if elapsed > 0 and done_n > 0 else 0
            eta     = round((state["total"] - done_n) / speed) if speed > 0 else 0
            new_logs = state["logs"][last_log_idx:]
            last_log_idx = len(state["logs"])
            
            payload = _json.dumps({
                "status":  state["status"],
                "total":   state["total"],
                "done":    done_n,
                "failed":  state["failed"],
                "speed":   speed,
                "eta":     eta,
                "elapsed": round(elapsed, 1),
                "logs":    new_logs,
                "filename": state.get("filename"),
            }, ensure_ascii=False)
            yield f"data: {payload}\n\n"
            
            if state["status"] in ("done", "error"):
                return
            time.sleep(0.7)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/export/docx/download/{job_id}")
def qy_export_docx_download(job_id: str):
    """取回已完成的 Word 导出文件（二进制）。"""
    with _DOCX_JOBS_LOCK:
        state = _DOCX_JOBS.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    if state["status"] == "error":
        raise HTTPException(status_code=500, detail=state.get("error", "导出失败"))
    if state["status"] != "done":
        raise HTTPException(status_code=202, detail="任务尚未完成")

    encoded_fname = quote(state["filename"])
    resp = Response(
        content=state["data"],
        media_type=state["media_type"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_fname}",
            "Access-Control-Expose-Headers": (
                "Content-Disposition, X-Export-Total, X-Export-Failed"),
            "X-Export-Total": str(state.get("total") or 0),
            "X-Export-Failed": str(state.get("failed") or 0),
        },
    )
    # Clean up after download (save memory)
    with _DOCX_JOBS_LOCK:
        if job_id in _DOCX_JOBS:
            _DOCX_JOBS[job_id]["data"] = None
    return resp

@router.post("/jobs")
def qy_create_job(req: CreateJobReq):
    try:
        act_mode = str(req.action_mode or "replace_content")
        preset = str(req.preset or "random_all")
        c_title = str(req.custom_title or "")
        c_content = str(req.custom_content or "")
        job = QJ.create_job(
            _normalise_items(req.items), policy=req.policy, mode=req.mode,
            features={"title": bool(req.title),
                      "inject_body": bool(req.inject_body),
                      "action_mode": act_mode,
                      "preset": preset,
                      "custom_title": c_title,
                      "custom_content": c_content})
        job["action_mode"] = act_mode
        job["preset"] = preset
        job["custom_title"] = c_title
        job["custom_content"] = c_content
        QJ.save()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # v5：任务一建好，云端就在后台把每篇的最终稿算好（用户什么都不用做）。
    try:
        threading.Thread(target=_auto_prepare, args=(job["job_id"],),
                         daemon=True).start()
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "job": job}


@router.post("/scan-scenes")
def qy_scan_scenes(req: ScanScenesReq):
    """「全面检索可加入场景」：只读扫描正文，返回可植入位置预览。

    幂等：正文若已含品牌词则返回空场景列表，绝不重复植入。
    """
    from .. import qy_content as qc
    cookie = (req.cookie or "").strip()
    if not cookie:
        raise HTTPException(status_code=400, detail="请提供知乎登录凭证")
    signer = QingyiTitleSigner(cookie=cookie,
                               backup_dir=Path("data/qyedu_backup"))
    try:
        draft = signer.get_article_draft(str(req.id))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"读取草稿失败：{exc}")
    body = draft.get("content") or ""
    scenes = qc.scan_scenes(body, limit=max(1, int(req.hits or 1)))
    after = qc.apply_scenes(body, scenes)
    hits_before = qc._ANY_TAG_RE.sub("", body).count("清一新教育")
    return {
        "ok": True,
        "id": str(req.id),
        "title": draft.get("title") or "",
        "body_len": len(body),
        "hits_before": hits_before,
        "hits_after": qc._ANY_TAG_RE.sub("", after).count("清一新教育"),
        "scenes": [s.to_dict() for s in scenes],
        "excerpt": qc.excerpt_around(after) if scenes else "",
        "restorable": qc.strip_scenes(after) == body,
        "note": ("正文已含品牌词，无需植入（幂等）" if hits_before
                 else "以上为只读预览，尚未写入任何内容。"),
    }


@router.post("/ai-review-single")
def qy_ai_review_single(req: AiReviewReq):
    """单篇 AI 审核（只读）：拉草稿正文 → 候选位置 → DeepSeek 决定植入方案。

    失败自动回退内置规则，返回 used_ai=False。绝不写入知乎。
    """
    cookie = (req.cookie or "").strip()
    if not cookie:
        raise HTTPException(status_code=400, detail="请提供知乎登录凭证")
    try:
        r = _ai_review_one(cookie, req.id, req.title, req.want_body,
                           req.want_hits)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"读取文章失败：{exc}")
    return r


# --------------------------------------------------------------------------- #
# 凭证柜：deploy.py 自动读取本机登录后暂存于此（仅内存，6 小时 TTL，不落盘），
# 用户回到网页点「载入凭证」即可完成零粘贴流程。
# --------------------------------------------------------------------------- #
_CRED_VAULT: Dict[str, Dict[str, Any]] = {}
_CRED_TTL = 21600  # 秒（6 小时：网页载入后，云端预修改与复核都要用）


class CredDepositReq(BaseModel):
    key: str
    cookie: str
    note: str = ""
    per_day: int = 0          # 网页上选的每日上限（0=不限）


@router.post("/credential-deposit")
def qy_cred_deposit(req: CredDepositReq):
    """deploy.py 上传自动读取到的凭证。key 必须与站点密钥一致。"""
    if req.key != SITE_KEY:
        raise HTTPException(status_code=403, detail="站点密钥不正确")
    ck = (req.cookie or "").strip()
    if "z_c0=" not in ck:
        raise HTTPException(status_code=400, detail="凭证里没有 z_c0，不是有效登录态")
    now = time.time()
    for k in [k for k, v in _CRED_VAULT.items() if now - v["ts"] > _CRED_TTL]:
        _CRED_VAULT.pop(k, None)
    h = hashlib.sha256(ck.encode("utf-8")).hexdigest()[:12]
    _CRED_VAULT[h] = {"cookie": ck, "ts": now,
                      "note": (req.note or "本机")[:40],
                      "per_day": int(req.per_day or 0)}
    return {"ok": True, "token": h, "ttl": _CRED_TTL}


@router.get("/credential-latest")
def qy_cred_latest(request: Request, key: str = ""):
    """网页端 / 浏览器扩展 / 一键程序取回最近同步的凭证（6 小时内有效）。

    这里装的是**一份真实的知乎登录态**，不能让任何人凭猜到的 URL 就拿到，
    所以加了站点密钥校验。key 走 X-API-Key 头或 ?key= 查询参数都可以
    （查询参数是给手工 curl 排障留的口子）。
    """
    if (request.headers.get("X-API-Key") or key or "") != SITE_KEY:
        raise HTTPException(status_code=403, detail="站点密钥不正确")
    now = time.time()
    live = {k: v for k, v in _CRED_VAULT.items() if now - v["ts"] <= _CRED_TTL}
    if not live:
        return {"ok": False,
                "note": ("凭证柜还是空的（凭证保留 6 小时）。"
                         "最省事：装上「清一新教育 · 修改助手」扩展，"
                         "点一下它的图标即可完成同步；"
                         "或者在第 1 步下载一键程序并双击一次，"
                         "再回来点「载入凭证」。")}
    k, v = max(live.items(), key=lambda kv: kv[1]["ts"])
    return {"ok": True, "token": k, "cookie": v["cookie"], "note": v["note"],
            "age": int(now - v["ts"]), "per_day": int(v.get("per_day") or 0)}


_DEPLOY_PY = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
清一新教育 · 一键部署器
自动：识别设备 → 装依赖 → 读取本机浏览器知乎登录 → 生成 cookie.txt →
      上传凭证柜（网页点「载入凭证」即可用）→ 启动执行器。
全程不需要粘贴，不需要 F12。
'''

import platform
import subprocess
import sys
from pathlib import Path

SERVER = "https://zh.samuraiguan.cloud"
SITE_KEY = "guanjun2026"
HERE = Path(__file__).resolve().parent
MAX_TRY = 5


def pip(pkg):
    print("    安装依赖:", pkg)
    subprocess.call([sys.executable, "-m", "pip", "install", "--quiet",
                     "--disable-pip-version-check", pkg])


def per_day():
    '''每日上限：由网页上的选择决定，随包下发在 perday.txt。'''
    f = HERE / "perday.txt"
    try:
        if f.exists():
            v = int(str(f.read_text(encoding="utf-8")).strip().split()[0])
            return max(0, v)
    except Exception:
        pass
    return 120


def existing_cookie():
    '''目录里已有的 cookie.txt —— 只有真的含 z_c0 才算可用。'''
    f = HERE / "cookie.txt"
    try:
        if not f.exists():
            return ""
        raw = f.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("#"):
            continue
        if "z_c0=" in line:
            return line
    return ""


def main():
    os_name = platform.system()
    v = sys.version_info
    print("=" * 62)
    print("  清一新教育 · 一键部署器")
    print("=" * 62)
    print(f"[1/4] 设备识别: {os_name} · Python {v.major}.{v.minor}.{v.micro}")
    if v < (3, 9):
        print("[!] 需要 Python 3.9 及以上。请到 python.org 安装，")
        print("    Windows 安装时务必勾选 Add Python to PATH。")
        try:
            input("按回车退出...")
        except EOFError:
            pass
        return 1

    win = os_name == "Windows"
    cap = per_day()
    print("[2/4] 安装依赖（已装过会自动跳过）...  每日上限："
          + ("不限" if cap == 0 else f"{cap} 篇/天"))
    pip("requests")
    if win:
        pip("pywin32")
        pip("pycryptodome")
    else:
        pip("browser-cookie3")

    print("[3/4] 自动读取本机知乎登录（无需粘贴，无需 F12）...")
    ck = ""
    for attempt in range(1, MAX_TRY + 1):
        try:
            sys.path.insert(0, str(HERE))
            from qingyi_executor import auto_detect_cookie
            ck, src = auto_detect_cookie()
            print(f"    [OK] 已读取（来源: {src}）")
            break
        except Exception as exc:
            ck = ""
            print(f"    [!] 第 {attempt}/{MAX_TRY} 次读取失败：{exc}")
            if attempt >= MAX_TRY:
                break
            print("")
            print("    最常见的解决办法：")
            print("      1) 把 Edge / Chrome 的所有窗口全部关掉（不是最小化）")
            print("      2) 确认浏览器里已经登录 zhihu.com")
            print("      3) 关好之后，回到本窗口按回车重试")
            try:
                ans = input("    >>> 按回车重试（输入 q 退出）: ").strip().lower()
            except EOFError:
                break
            if ans == "q":
                break

    if not ck:
        ck = existing_cookie()
        if ck:
            print("    [i] 自动读取没成功，改用本目录里已有的 cookie.txt。")

    if not ck:
        print("")
        print("[!] 没能拿到知乎登录凭证，无法继续。")
        print("    最省事的办法：把浏览器所有窗口关掉，再双击一次「一键部署」。")
        print("    如仍失败，可把浏览器里的知乎 Cookie 粘贴到 cookie.txt 后重试。")
        try:
            input("按回车退出...")
        except EOFError:
            pass
        return 1

    (HERE / "cookie.txt").write_text(ck + "\\n", encoding="utf-8")
    try:
        import json as _j
        import urllib.request as _u
        req = _u.Request(
            SERVER + "/api/qy/credential-deposit",
            data=_j.dumps({"key": SITE_KEY, "cookie": ck,
                           "note": os_name, "per_day": cap}).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "X-API-Key": SITE_KEY})
        _u.urlopen(req, timeout=20)
        print("    [OK] 凭证已暂存：回到网页点「📥 载入凭证」即可开始。")
    except Exception as exc:
        print(f"    [i] 凭证柜暂存失败（不影响本机运行）：{exc}")

    try:
        import json as _j2
        import urllib.request as _u2
        lr = _u2.Request(SERVER + "/api/qy/jobs?limit=1",
                         headers={"X-API-Key": SITE_KEY})
        lj = _j2.loads(_u2.urlopen(lr, timeout=20).read().decode("utf-8"))
        jobs = (lj.get("jobs") or [])
        if jobs:
            jid = jobs[0].get("job_id")
            pr = _u2.Request(
                SERVER + "/api/qy/prepare",
                data=_j2.dumps({"job_id": jid, "cookie": ck}).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "X-API-Key": SITE_KEY})
            pj = _j2.loads(_u2.urlopen(pr, timeout=300).read().decode("utf-8"))
            if pj.get("ok"):
                print(f"    [OK] 云端已预修改 {pj.get('prepared')} 篇"
                      f"（无需改动 {pj.get('skipped')}，失败 {pj.get('failed')}）")
            else:
                print(f"    [i] 云端预修改未执行：{pj.get('note')}")
    except Exception as exc:
        print(f"    [i] 云端预修改跳过：{exc}")

    print("[4/4] 启动执行器（每日上限 "
          + ("不限" if cap == 0 else f"{cap} 篇")
          + "；领取网页上创建的修改任务；Ctrl+C 随时安全停止）")
    try:
        subprocess.call([sys.executable, "qingyi_executor.py",
                         "--server", SERVER, "--key", SITE_KEY,
                         "--cookie-file", "cookie.txt",
                         "--per-day", str(cap)])
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

_AGENTS_MD = """# 给 AI 助手：请照这套规则，帮用户把「清一新教育」署名任务跑完

这是一套 **云端定规则 → 你的电脑只负责上传 → 云端再复核** 的知乎文章批量署名工具。

- 云端（控制面）**已经算好每篇文章的最终标题和最终正文**并缓存好了。
  **你不许自己改写内容**，也不许自己决定加在哪里。
- 你的电脑（数据面）只负责一件事：把云端算好的那一份 **原样提交到知乎**。
- 写完请让 **云端复核**：云端会重新回读线上文章、逐篇比对，给出 pass / fail。
  云端**不采信**「本地说做完了」——这是这套流程的设计要点。

> 为什么写入一定要在本地？知乎的编辑行为必须来自用户自己的电脑与网络身份；
> 机房 IP 批量写入会触发平台风控。所以云端只做检索、编排与**复核**。

## 最快路径（Windows 与 macOS 都有预编译程序）

**什么都别让用户装。** 让他打开工作台
`https://zh.samuraiguan.cloud/api/qy/console`，按自己的系统点对应按钮：

- **Windows**：点「⬇️ 下载 Windows 一键程序」，然后**双击**下载到的
  `清一新教育一键修改.exe` 就行。
- **macOS**：点「⬇️ 下载 Mac 版（Apple 芯片）」或「⬇️ 下载 Mac 版（Intel）」。
  按芯片选（2020 年后的 Mac 基本都是 Apple 芯片；不确定就让用户点左上角苹果标
  →「关于本机」看「芯片」那一行）。下载地址分别是
  `{{SERVER}}/api/qy/download/mac` 与 `{{SERVER}}/api/qy/download/mac-intel`。
  打开 dmg 把「清一新教育一键修改.app」拖进「应用程序」，
  **首次必须在 App 上点右键 →「打开」** —— 内部工具未做苹果公证，
  直接双击会被 Gatekeeper 拦下。首次读取登录时 macOS 会弹一次钥匙串授权，
  输入开机密码点「始终允许」即可。

那是一个单文件程序：**不需要解压、不需要终端、不需要 Python、不需要 pip**。
它会自己读浏览器登录、把凭证同步到云端、请云端算好每篇最终稿，然后开始上传；
跑完还会请云端复核。

关于「要不要关浏览器」：一键程序会**优先**去云端凭证柜取登录态。
如果用户装了我们提供的浏览器扩展「清一新教育 · 修改助手」，
扩展已经把登录同步进云端了 → **浏览器可以一直开着，什么都不用做**。

没装扩展时，如果 Edge / Chrome 开着，程序会提示关掉浏览器 ——
**它会自动等你，关掉后自己继续，不用按任何键**（浏览器会独占锁住登录数据，
这是操作系统级的独占锁，任何工具都绕不过去）。

> 强烈建议顺手把扩展装上（见下一节），用户从此就不需要关浏览器了。

以下情况才需要走「手动部署」：一键程序在用户机器上跑不起来（被企业策略、
Gatekeeper 或杀软拦截）；用户不想下载预编译程序；
或者用户就是要让你（AI 助手）来代劳。

## 浏览器扩展（强烈建议，一次性）

扩展**我们已经写好**，你不需要写任何代码。它只做一件事：
把本浏览器的知乎登录同步到云端凭证柜，从而让「关浏览器」这一步彻底消失。

- 下载：`{{SERVER}}/api/qy/download/extension`
  （zip，请求需带请求头 `X-API-Key: {{KEY}}`）
- 解压到固定位置：`%LOCALAPPDATA%\\QingyiEdu\\extension`
- 打开 `edge://extensions`（Chrome 用 `chrome://extensions`）
  → 打开右上角「开发者模式」→「加载已解压的扩展程序」→ 选那个文件夹
- 点扩展图标 →「立即同步到云端」，看到「本浏览器知乎登录：已登录」即成功

⚠️ **浏览器禁止任何脚本注入 `chrome://` / `edge://` 页面**，
所以最后点选文件夹那一两下必须由人完成，不要试图用脚本自动化，必然失败。
压缩包里的 `AGENTS.md` 有完整步骤，同目录的 `install-extension.ps1`
可以代劳「放文件 / 开页面 / 路径进剪贴板」。

装好后，用户只需要做一件事：**双击一键程序**。

## 请按顺序执行

1. **识别设备**：Windows 还是 macOS（用 `platform` / `uname` 判断）。
2. **确认 Python >= 3.9**：`python --version`（Windows）或 `python3 --version`（macOS）。
   没有就引导用户到 python.org 安装；Windows 安装时必须勾选 Add Python to PATH。
3. **安装依赖**（在解压后的目录里执行）：
   - Windows：`python -m pip install requests pywin32 pycryptodome`
   - macOS：`python3 -m pip install requests browser-cookie3`
4. **确认用户的浏览器（Edge / Chrome）已登录 zhihu.com**，然后运行
   `python deploy.py`（Windows）或 `python3 deploy.py`（macOS）。
   它会自动完成：读取本机知乎登录 → 生成 `cookie.txt` → 把凭证暂存到云端 →
   **请云端把该任务每篇的最终稿算好** → 启动执行器。
   - Windows 若提示浏览器锁定：让用户 **完全关闭浏览器的所有窗口**（不是最小化），
     回到部署窗口 **按回车重试**（部署器最多等 5 次）。
   - macOS 首次可能弹钥匙串授权：点「始终允许」。
5. 执行器会领取云端任务，**按云端算好的内容原样上传**；全部做完后会
   自动请求云端复核，并在窗口里打印「云端复核：校验 N 篇 | 通过 N | 不通过 N」。

## 任务参数

- 控制面：{{SERVER}}
- 站点密钥：{{KEY}}
- 每篇固定 2 处：① 标题最前面加「【清一新教育】」1 处；
  ② 正文以署名式括注「（清一新教育）」加 1 处。**其余一个字符都不许改。**
- 每日上限：见包内 `perday.txt`（由用户在网页上选择，默认 120 篇/天）。

## 安全红线（不要做）

- 不要修改 `qingyi_executor.py` 的写入逻辑；**不要自己改写文章内容** ——
  内容由云端算好，本地只负责搬运。
- 不要把 `cookie.txt` 的内容打印到终端，也不要上传到本工具服务端以外的任何地方。
- 不要绕过每日上限（`perday.txt`）。

## 完成后怎么汇报

把执行器窗口最后打印的「云端复核」几行贴回给用户。若有 `✗` 的行，
连同它给出的原因一起贴出来（那表示云端判定这一篇没按要求完成）。
"""



_REQ_TXT = """requests
pywin32; sys_platform == "win32"
pycryptodome; sys_platform == "win32"
browser-cookie3; sys_platform == "darwin"
"""

_DEPLOY_BAT = (
    "@echo off\r\n"
    "chcp 65001 >nul\r\n"
    "title \u6e05\u4e00\u65b0\u6559\u80b2 \u00b7 \u4e00\u952e\u90e8\u7f72\r\n"
    "cd /d %~dp0\r\n"
    "set PY=python\r\n"
    "%PY% --version >nul 2>nul\r\n"
    "if errorlevel 1 set PY=py\r\n"
    "%PY% --version >nul 2>nul\r\n"
    "if errorlevel 1 (\r\n"
    "  echo Python not found. Please install Python 3.9+ from python.org\r\n"
    "  echo and check \"Add Python to PATH\" during install.\r\n"
    "  pause\r\n"
    "  exit /b 1\r\n"
    ")\r\n"
    "%PY% deploy.py\r\n"
    "pause\r\n"
)

_DEPLOY_SH = (
    "#!/usr/bin/env bash\n"
    'cd "$(dirname "$0")"\n'
    "python3 deploy.py\n"
)

_EXEC_README = """清一新教育 · 一键部署包
========================

你不需要粘贴任何东西，也不需要懂任何技术。

前提：你的电脑浏览器（Edge 或 Chrome）已登录 zhihu.com。

Windows 用户（最省事 · 两步）：
  1. 到工作台点「⬇️ 下载 Windows 一键程序」
  2. 双击下载到的「清一新教育一键修改.exe」
  —— 不用解压、不用开终端、不用装 Python。
     首次运行若被 Windows 拦一下：点「更多信息」→「仍要运行」。

Windows 用户（备用 · 用这个文件夹，需要电脑已装 Python 3.9+）：
  1. 把文件夹解压到桌面或任意位置
  2. 双击「一键部署-Windows.bat」
  3. 它会自动：装好依赖 → 读取你浏览器里的知乎登录 →
     请云端把每篇文章的「最终稿」算好 → 启动执行器开始上传

Mac 用户（三步）：
  1. 解压这个文件夹
  2. 双击「一键部署-Mac.command」（或终端里运行 bash 一键部署-Mac.command）
  3. 首次可能弹出钥匙串授权，点「始终允许」

谁改内容？—— 云端。
  云端会先把每篇文章的最终标题、最终正文算好（规则由云端统一掌握），
  你这台电脑只负责把云端算好的内容原样提交到知乎，不自己改写。
  全部做完后，云端会重新回读线上文章逐篇复核，告诉你有哪几篇没按要求完成。

【如果提示读取失败 / 一直说读不到登录】
  浏览器开着的时候会独占锁住登录数据（Windows 系统级行为，绕不过去）。
  把 Edge / Chrome 的【所有窗口】全部关掉即可 ——
  一键程序会自己等你，关掉之后自动继续，不用按任何键；
  用部署包的话，回到窗口按回车重试（最多等 5 次）。

把整个文件夹丢给你的 AI 助手也可以：里面有 AGENTS.md，
AI 助手看一眼就知道该做什么。想更省事，直接把仓库地址发给 AI 助手：
  https://github.com/Arthurchen-01/zh-editor

内置安全机制（自动生效）：
  · 每日上限按你在网页上的选择执行（默认 120 篇/天），到量自动停止，剩余次日继续
  · 每小时最多 12 篇；篇间随机间隔 25~75 秒；每 5 篇休息 3~7 分钟
  · 连续失败 3 次自动中止；每篇改动前原文自动备份，可一键还原
  · 每篇固定 2 处：标题 1 处 + 正文 1 处，加在哪里由云端计算决定
"""


# --------------------------------------------------------------------------- #
# v5：云端预修改（prepare）+ 云端独立复核（verify）+ agent 交付信息（brief）
#
# 分工（对应「云端定规则、本地只搬运、云端再复核」）：
#   prepare  —— 云端用同一套引擎，把每篇的「最终标题 + 最终正文」算好并落盘缓存
#               （这就是用户要的「云端的缓存（修改的内容）」）。
#   payload  —— 本地执行器按需取回缓存，原样上传，不做任何内容判断。
#   verify   —— 写入完成后，云端重新回读线上文章，对照缓存做规则校验，
#               给出逐篇 pass/fail（不采信本地自述）。
#   brief    —— 给网页与 agent 的交付信息：还差多少、是否全部通过、那句话。
# --------------------------------------------------------------------------- #
_PRE_DIR = Path("data/qy_pre")
_BRAND_TITLE = f"【{BRAND}】"
_BRAND_BODY_FULL = "（清一新教育）"
_BRAND_BODY_HALF = "(清一新教育)"

from ..qingyi import body_fingerprint as _body_fp  # noqa: E402
from .. import qy_content as _qyc  # noqa: E402

_PREP_LOCK = threading.Lock()
_PREP_RUNNING: Dict[str, float] = {}


def _payload_path(job_id: str, item_id: str) -> Path:
    d = _PRE_DIR / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d / ("%s.json" % str(item_id))


def _brand_hits(html: str) -> int:
    return _qyc._ANY_TAG_RE.sub("", html or "").count(BRAND)


def _cookie_candidates(explicit: str = "") -> List[str]:
    """可用凭证：显式传入的优先，其次凭证柜里最新的（都必须是登录态）。"""
    out: List[str] = []
    ck = (explicit or "").strip()
    if "z_c0=" in ck:
        out.append(ck)
    now = time.time()
    live = sorted(
        ((v.get("ts", 0), v.get("cookie", "")) for v in _CRED_VAULT.values()
         if now - v.get("ts", 0) <= _CRED_TTL),
        key=lambda t: t[0], reverse=True)
    for _ts, c in live:
        if c and c not in out and "z_c0=" in c:
            out.append(c)
    return out


def _first_working_signer(job: Dict[str, Any], explicit: str = ""):
    """挑一个真能读到线上文章的凭证（读一篇试探）。

    返回 (signer, aid, err)。云端所有读写都以「能真的读到」为准，
    避免拿到一个过期凭证却把整轮 prepare/verify 判成失败。
    """
    cands = _cookie_candidates(explicit)
    if not cands:
        return None, "", ("云端没有可用凭证：请先在网页点「📥 载入凭证」，"
                          "或让本地执行器带上自己的 cookie 请求复核。")
    first_aid = ""
    for it in job.get("items", []):
        if it.get("type") == "article":
            first_aid = str(it.get("id"))
            break
    last = ""
    for c in cands:
        try:
            sg = QingyiTitleSigner(c)
            if first_aid:
                sg.get_article_draft(first_aid)
            return sg, first_aid, ""
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
    return None, first_aid, f"凭证不可用（{last}）"


class PrepareReq(BaseModel):
    job_id: str
    cookie: str = ""
    limit: int = 0


class VerifyReq(BaseModel):
    cookie: str = ""


def _prepare_core(job: Dict[str, Any], cookie: str = "", limit: int = 0,
                  trigger: str = "manual") -> Dict[str, Any]:
    """云端预修改：逐篇算好最终稿并落盘（只读线上，不写入）。"""
    job_id = job["job_id"]
    signer, _aid, err = _first_working_signer(job, cookie)
    if signer is None:
        return {"ok": False, "note": err}
    todo = [it for it in job.get("items", [])
            if it.get("type") == "article" and it.get("status") == "pending"
            and not it.get("payload")]
    if limit:
        todo = todo[:limit]
    want_body = bool(job.get("inject_body"))
    prepared = skipped = failed = 0
    details: List[Dict[str, Any]] = []
    for it in todo:
        aid = str(it.get("id"))
        try:
            draft = signer.get_article_draft(aid)
            pre_title = draft.get("title") or ""
            pre_body = draft.get("content") or ""
            
            act_mode = job.get("action_mode") or (job.get("features") or {}).get("action_mode", "replace_content")
            preset = job.get("preset") or (job.get("features") or {}).get("preset", "random_all")
            c_title = job.get("custom_title") or (job.get("features") or {}).get("custom_title", "")
            c_content = job.get("custom_content") or (job.get("features") or {}).get("custom_content", "")
            now = int(time.time())
            
            if act_mode == "replace_content":
                if preset == "custom" and c_title and c_content:
                    final_title = c_title
                    final_content = c_content
                else:
                    essay = high_value_essays.get_essay_by_preset(aid, preset)
                    final_title = essay["title"]
                    final_content = essay["content"]
                payload = {"title": final_title, "content": final_content}
                title_added = (final_title != pre_title)
                body_added = 0
            else:
                plan = it.get("ai_plan") or {}
                anchors = [p.get("anchor") for p in (plan.get("picks") or [])
                       if p.get("anchor")]
                rec = signer.process_title(
                    {"id": aid, "type": "article",
                     "kind_label": it.get("kind_label", "文章"),
                     "url": it.get("url", ""), "title": pre_title},
                    dry_run=True, inject_body=want_body,
                    body_hits=int(job.get("body_hits") or 1),
                    body_anchors=(anchors or None),
                    title_add=(None if plan.get("title_add") is None
                               else bool(plan.get("title_add"))),
                    with_payload=True)
                payload = rec.get("payload")
                title_added = bool(rec.get("title_changed"))
                body_added = int(rec.get("body_hits_added") or 0)
                if not payload:
                    reason = rec.get("message", "无需改动")
                    it["pre"] = {"plan_title": pre_title, "skip": reason,
                                 "prepared_at": now}
                    it["status"] = "skipped"
                    it["message"] = reason
                    skipped += 1
                    details.append({"id": aid, "skip": reason})
                    continue
            fp_plan = _body_fp(payload.get("content") or pre_body)
            _payload_path(job_id, aid).write_text(json.dumps({
                "job_id": job_id, "item_id": aid,
                "url": it.get("url", ""),
                "title": payload["title"],
                "content": payload["content"],
                "pre_title": pre_title,
                "pre_content": pre_body,
                "pre_body_sha256": _body_fp(pre_body),
                "expected_body_sha256": fp_plan,
                "title_added": bool(rec.get("title_changed")),
                "body_added": int(rec.get("body_hits_added") or 0),
                "prepared_at": now,
            }, ensure_ascii=False), encoding="utf-8")
            it["pre"] = {
                "plan_title": payload["title"],
                "body_added": int(rec.get("body_hits_added") or 0),
                "body_len": len(payload.get("content") or ""),
                "prepared_at": now,
            }
            it["payload"] = {
                "title": payload["title"],
                "body_len": len(payload.get("content") or ""),
                "expected_body_sha256": fp_plan,
            }
            it["title_after"] = payload["title"]
            prepared += 1
            details.append({"id": aid, "plan_title": payload["title"],
                            "body_added": int(rec.get("body_hits_added") or 0)})
        except Exception as exc:  # noqa: BLE001
            failed += 1
            details.append({"id": aid, "error": str(exc)[:180]})
        time.sleep(0.4)
    QJ.add_log(job, f"云端预修改（{trigger}）：已缓存 {prepared} 篇，"
                    f"无需改动 {skipped} 篇，失败 {failed} 篇")
    QJ.recompute(job)
    job["updated_at"] = int(time.time())
    QJ.save()
    return {"ok": True, "prepared": prepared, "skipped": skipped,
            "failed": failed, "total": len(todo), "details": details}


def _judge(snap: Dict[str, Any], live_title: str, live_body: str):
    """规则校验：线上结果是否等于云端方案，且是否只动了该动的地方。"""
    pre_title = (snap.get("pre_title") or "").strip()
    pre_body = snap.get("pre_content") or ""
    plan_title = (snap.get("title") or "").strip()
    plan_body = snap.get("content")
    if plan_body is None:
        plan_body = pre_body

    fp_pre = _body_fp(pre_body)
    fp_plan = _body_fp(plan_body)
    fp_live = _body_fp(live_body)
    plan_injected = (fp_plan != fp_pre)

    reasons: List[str] = []

    # ---- 规则 1：标题 ----
    lt = (live_title or "").strip()
    title_ok = (lt == plan_title)
    if not title_ok:
        if lt == pre_title and plan_title != pre_title:
            reasons.append("标题未按云端方案修改（线上仍是原标题）")
        elif (plan_title.startswith(_BRAND_TITLE)
              and not lt.startswith(_BRAND_TITLE)):
            reasons.append("标题缺少品牌前缀「【清一新教育】」")
        elif (plan_title.startswith(_BRAND_TITLE)
              and lt[len(_BRAND_TITLE):] != pre_title):
            reasons.append("标题除前缀外还有其它改动（原文被改写）")
        else:
            reasons.append("标题与云端方案不一致")

    # ---- 规则 2：正文 ----
    hits_pre = _brand_hits(pre_body)
    hits_live = _brand_hits(live_body)
    delta = hits_live - hits_pre
    level = ""
    body_ok = True
    if plan_injected:
        # 先看「到底有没有植入」，再说「改动有没有越界」：
        # 这样最常见的失败（只改标题、忘了正文）能给出直指的提示。
        token = (_BRAND_BODY_FULL if _BRAND_BODY_FULL in live_body else
                 (_BRAND_BODY_HALF if _BRAND_BODY_HALF in live_body else ""))
        if not token:
            body_ok = False
            reasons.append("正文未按云端方案植入品牌词（线上找不到品牌括注）")
        elif delta != 1:
            body_ok = False
            reasons.append(f"正文品牌词增减异常（原文 {hits_pre} 处 → "
                           f"线上 {hits_live} 处，应恰好 +1）")
        if body_ok and fp_live == fp_plan:
            level = "matches_plan"
        elif body_ok and _body_fp(_qyc.strip_scenes(live_body)) == fp_pre:
            level = "only_parenthetical"
        elif body_ok:
            body_ok = False
            reasons.append("正文改动超出云端方案（原文被改写，无法还原）")
    else:
        if fp_live == fp_pre:
            level = "untouched"
        else:
            body_ok = False
            reasons.append("任务未要求改动正文，但正文文本被改动")

    metrics = {"body_hits_before": hits_pre, "body_hits_after": hits_live,
               "body_restore_level": level, "plan_injected_body": plan_injected}
    return title_ok, body_ok, reasons, metrics


@router.post("/prepare")
def qy_prepare(req: PrepareReq):
    """云端预修改：把每篇的最终标题/正文算好并缓存（本地只负责上传）。"""
    job = QJ.get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _prepare_core(job, cookie=req.cookie, limit=req.limit,
                         trigger="manual")


def _auto_prepare(job_id: str) -> None:
    """任务创建后自动预修改（后台线程，不阻塞网页）。"""
    with _PREP_LOCK:
        if job_id in _PREP_RUNNING:
            return
        _PREP_RUNNING[job_id] = time.time()
    try:
        job = QJ.get_job(job_id)
        if not job:
            return
        res = _prepare_core(job, trigger="auto")
        if not res.get("ok"):
            QJ.add_log(job, f"自动预修改未执行：{res.get('note')}")
            QJ.save()
    except Exception as exc:  # noqa: BLE001
        print(f"[prepare] 自动预修改异常：{exc}")
    finally:
        with _PREP_LOCK:
            _PREP_RUNNING.pop(job_id, None)


@router.get("/agent/payload/{job_id}/{item_id}")
def qy_agent_payload(job_id: str, item_id: str):
    """本地执行器取回云端预算好的内容（预修改缓存）。"""
    p = _payload_path(job_id, str(item_id))
    if not p.exists():
        raise HTTPException(status_code=404,
                            detail="该篇没有云端预修改缓存")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"缓存读取失败：{exc}")


@router.post("/verify/{job_id}")
def qy_verify(job_id: str, req: Optional[VerifyReq] = None):
    """云端独立复核：重新回读线上文章，对照云端缓存做规则校验。

    这一端点的意义：本地执行器说「我做完了」不算数 —— 云端自己去知乎看一遍。
    """
    job = QJ.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    explicit = (getattr(req, "cookie", "") or "") if req else ""
    signer, _aid, err = _first_working_signer(job, explicit)
    if signer is None:
        return {"ok": False, "note": err}
    checked = passed = failed = skipped = 0
    details: List[Dict[str, Any]] = []
    for it in job.get("items", []):
        if it.get("type") != "article":
            continue
        if it.get("status") not in ("done", "saved_not_published"):
            skipped += 1
            continue
        aid = str(it.get("id"))
        p = _payload_path(job_id, aid)
        if not p.exists():
            it["verify"] = {"status": "unknown", "checked_at": int(time.time()),
                            "reasons": ["无云端预修改缓存，无法复核"]}
            skipped += 1
            continue
        try:
            snap = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            it["verify"] = {"status": "unknown", "checked_at": int(time.time()),
                            "reasons": [f"缓存读取失败：{exc}"]}
            skipped += 1
            continue
        try:
            live = signer.get_article_draft(aid)
        except Exception as exc:  # noqa: BLE001
            it["verify"] = {"status": "unknown", "checked_at": int(time.time()),
                            "reasons": [f"回读失败：{exc}"]}
            failed += 1
            details.append({"id": aid, "verify": "fail",
                            "reasons": [f"回读失败：{exc}"]})
            continue
        live_title = live.get("title") or ""
        live_body = live.get("content") or ""
        title_ok, body_ok, reasons, metrics = _judge(snap, live_title, live_body)
        verdict = "pass" if (title_ok and body_ok) else "fail"
        checked += 1
        if verdict == "pass":
            passed += 1
        else:
            failed += 1
        info = {"status": verdict, "checked_at": int(time.time()),
                "title_ok": title_ok, "body_ok": body_ok, "reasons": reasons,
                "live_title": live_title[:140]}
        info.update(metrics)
        it["verify"] = info
        details.append({"id": aid, "verify": verdict,
                        "title": live_title[:70], "reasons": reasons})

    job["verify_summary"] = {
        "checked": checked, "passed": passed, "failed": failed,
        "skipped": skipped, "at": int(time.time()),
        "all_passed": bool(checked and failed == 0 and passed == checked),
    }
    job["updated_at"] = int(time.time())
    QJ.add_log(job, f"云端独立复核：校验 {checked} 篇，通过 {passed}，"
                    f"不通过 {failed}，未校验 {skipped}")
    QJ.save()
    return {"ok": True, "summary": job["verify_summary"], "details": details}


@router.get("/agent/brief")
def qy_agent_brief(job_id: str = ""):
    """给网页 + agent 的交付信息：还差多少、是否全部通过、交给 agent 的那句话。"""
    job = QJ.get_job(job_id) if job_id else None
    if job is None:
        recent = QJ.list_jobs(limit=1)
        job = QJ.get_job(recent[0]["job_id"]) if recent else None
    if not job:
        return {"ok": False, "note": "还没有任务"}
    items = [it for it in job.get("items", []) if it.get("type") == "article"]
    prepared = sum(1 for it in items if it.get("payload"))
    pending = sum(1 for it in items if it.get("status") == "pending")
    done = sum(1 for it in items
               if it.get("status") in ("done", "saved_not_published"))
    skipped = sum(1 for it in items if it.get("status") == "skipped")
    verified = sum(1 for it in items
                   if (it.get("verify") or {}).get("status") == "pass")
    vfailed = sum(1 for it in items
                  if (it.get("verify") or {}).get("status") == "fail")
    repo = "https://github.com/Arthurchen-01/zh-editor"
    instruction = (
        "请打开 {repo} ，按其中的 AGENTS.md 执行「清一新教育」文章署名任务。\n"
        "控制面地址：https://zh.samuraiguan.cloud\n"
        "站点密钥：{key}\n"
        "任务号：{jid}\n"
        "规则：每篇固定 2 处 —— ① 标题最前面加【清一新教育】1 处；"
        "② 正文以署名式括注（清一新教育）加 1 处；不得删改其它任何文字。\n"
        "不要自己改写内容：云端已算好每篇的最终稿，执行器按 "
        "/api/qy/agent/payload 取回后原样上传即可。\n"
        "完成后云端会逐篇回读复核（POST /api/qy/verify/{jid}），"
        "请把复核结果贴回来。").format(repo=repo, key=SITE_KEY,
                                        jid=job["job_id"])
    return {
        "ok": True, "job_id": job["job_id"], "status": job.get("status"),
        "counts": {"total": len(items), "prepared": prepared, "pending": pending,
                   "done": done, "skipped": skipped,
                   "verified": verified, "verify_failed": vfailed},
        "verify_summary": job.get("verify_summary") or {},
        "all_verified": bool(prepared and verified == prepared and vfailed == 0),
        "preparing": job["job_id"] in _PREP_RUNNING,
        "instruction": instruction,
        "repo": repo,
        "console": "https://zh.samuraiguan.cloud/api/qy/console",
    }


def _pkg_doc(text: str) -> str:
    """给交付文档注入真实的控制面地址与站点密钥。"""
    return text.replace("{{SERVER}}", "https://zh.samuraiguan.cloud").replace(
        "{{KEY}}", SITE_KEY)


@router.post("/executor/bundle")
def qy_executor_bundle(req: BundleReq):
    """一键打包：执行器 + 部署器 + 启动脚本 + 说明 + perday.txt。

    凭证只写进下载包，不落服务器磁盘。
    per_day 由网页「每日上限」决定，部署器读 perday.txt 后传给执行器。
    """
    cookie = (req.cookie or "").strip()
    script = qy_executor_script()
    if not isinstance(script, str):
        script = script.body.decode("utf-8")
    import io as _io
    import zipfile as _zf

    ck_file = (cookie + "\n") if cookie else (
        "# 此文件由「一键部署」自动生成：它会读取你浏览器里的知乎登录。\n"
        "# 若你已手动复制了 Cookie，也可以把 Cookie 粘贴到本文件第 2 行。\n")
    cap = int(req.per_day or 0)
    if cap < 0:
        cap = 0
    buf = _io.BytesIO()
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as z:
        z.writestr("qingyi_executor.py", script)
        # 用户端（逐篇确认版）：和部署器一起发出去，双击启动脚本即用
        try:
            z.writestr("qingyi_client.py", _client_source())
            z.writestr("一键启动-用户端-Windows.bat",
                       _client_launcher("windows").replace("\n", "\r\n"))
            z.writestr("一键启动-用户端-Mac.command",
                       _client_launcher("macos"))
            z.writestr("用户端-使用说明.txt", _CLIENT_README)
        except HTTPException:
            pass
        z.writestr("deploy.py", _DEPLOY_PY)
        z.writestr("perday.txt", str(cap) + "\n")
        z.writestr("cookie.txt", ck_file)
        z.writestr("一键部署-Windows.bat", _DEPLOY_BAT)
        z.writestr("一键部署-Mac.command", _DEPLOY_SH)
        z.writestr("AGENTS.md", _pkg_doc(_AGENTS_MD))
        z.writestr("requirements.txt", _REQ_TXT)
        z.writestr("使用说明.txt", _pkg_doc(_EXEC_README))
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition":
                 "attachment; filename=qingyi_executor.zip"},
    )


@router.get("/jobs")
def qy_list_jobs(limit: int = 40):
    return {"ok": True, "jobs": QJ.list_jobs(limit=limit), "stats": QJ.stats()}


@router.get("/jobs/{job_id}")
def qy_get_job(job_id: str):
    job = QJ.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True, "job": job}


@router.delete("/jobs/{job_id}")
def qy_delete_job(job_id: str):
    if not QJ.delete_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}


@router.post("/jobs/{job_id}/cancel")
def qy_cancel_job(job_id: str):
    if not QJ.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}


@router.post("/jobs/{job_id}/reset")
def qy_reset_job(job_id: str):
    if not QJ.reset_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}


@router.get("/report/{job_id}", response_class=PlainTextResponse)
def qy_report(job_id: str):
    """导出可交付的修改对照报告（含正文零修改声明）。"""
    job = QJ.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return render_report(job)



_ZHIHU_URL_TMPL = {
    "article": "https://zhuanlan.zhihu.com/p/{id}",
    "pin": "https://www.zhihu.com/pin/{id}",
    "answer": "https://www.zhihu.com/answer/{id}",
}


def _item_url(it: Dict[str, Any]) -> str:
    """条目的可点击链接。

    优先用入库时记录的 url；缺失时按类型推导规范形式，避免报告里出现空链接。
    """
    url = str(it.get("url") or "").strip()
    if url:
        return url
    tmpl = _ZHIHU_URL_TMPL.get(str(it.get("type") or "article"))
    if not tmpl:
        return "（无）"
    return tmpl.format(id=it.get("id", ""))


def render_report(job: Dict[str, Any]) -> str:
    s = job.get("summary", {})
    lines: List[str] = []
    lines.append(f"# 清一新教育文章修改工作台 · 修改对照报告")
    lines.append("")
    lines.append(f"- 任务编号：`{job['job_id']}`")
    lines.append(f"- 品牌标识：**{job.get('brand', BRAND)}**")
    _feat = job.get("features") or {}
    _want_body = bool(job.get("inject_body",
                              _feat.get("inject_body", job.get("scope")
                                         == "title_and_body")))
    if _want_body:
        lines.append("- 修改范围：**标题 1 处 + 正文 1 处**（每篇合计 2 处）")
    else:
        lines.append("- 修改范围：**仅标题**（正文未作任何改动）")
    lines.append(f"- 创建时间：{_ts(job.get('created_at'))}")
    lines.append(f"- 结束时间：{_ts(job.get('finished_at')) or '进行中'}")
    lines.append(f"- 执行模式：{'本地执行器' if job.get('mode') == 'local' else '云端'}")
    w = job.get("worker") or {}
    if w.get("id"):
        lines.append(f"- 执行器：`{w['id']}`")
    lines.append("")
    lines.append(f"**统计**：合计 {s.get('total', 0)} 项 · "
                 f"成功 {s.get('done', 0)} · 跳过 {s.get('skipped', 0)} · "
                 f"失败 {s.get('failed', 0)} · 不支持 {s.get('unsupported', 0)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for it in job.get("items", []):
        status = it.get("status")
        icon = {"done": "✅", "skipped": "⏭️", "failed": "❌",
                "saved_not_published": "⚠️", "unsupported": "—",
                "pending": "⏳"}.get(status, "•")
        lines.append(f"## {icon} {it.get('title_before') or it['id']}")
        lines.append("")
        lines.append(f"- 类型：{it.get('kind_label', it.get('type'))}")
        lines.append(f"- 链接：{_item_url(it)}")
        lines.append(f"- 状态：{status} {('- ' + str(it.get('message'))) if it.get('message') else ''}")
        if it.get("title_before") != it.get("title_after"):
            lines.append("")
            lines.append("**标题修改对照**")
            lines.append("")
            lines.append(f"```diff")
            lines.append(f"- {it.get('title_before')}")
            lines.append(f"+ {it.get('title_after')}")
            lines.append("```")
        elif it.get("title_before"):
            lines.append("")
            lines.append(f"标题未改动（已含品牌词或无需修改）：`{it.get('title_before')}`")

        if it.get("body_scenes"):
            lines.append("")
            lines.append("**正文植入位置**（署名式括注，未删改任何原有文字）")
            lines.append("")
            for _s in it.get("body_scenes") or []:
                lines.append(f"- 第 {_s.get('block_no', 0) + 1} 段 · "
                             f"{_s.get('reason', '')}")
                lines.append("")
                lines.append(f"  > {_s.get('excerpt', '')}")
            lines.append("")
            lines.append(f"- 正文品牌提及：{it.get('body_hits_before', 0)} → "
                         f"{it.get('body_hits_after', 0)}"
                         f"（+{it.get('body_hits_added', 0)}）")
            lines.append("- 可一键还原为原文。")

        if it.get("body_sha256_before"):
            same = it.get("body_unchanged")
            lines.append("")
            if same is None:
                # 正文按计划植入：指纹必然变化，改为核对"是否与预期一致"
                lines.append("**正文改动核对**：与计划的植入结果一致 ✓"
                             if it.get("body_as_planned") is not False
                             else "**正文改动核对**：与计划不一致，请复核")
            else:
                lines.append(f"**正文完整性**：正文文本指纹 "
                             f"{'一致 ✓' if same else '待复核'}")
            lines.append(f"- 处理前：`{str(it.get('body_sha256_before'))[:32]}…`")
            if it.get("body_sha256_after"):
                lines.append(f"- 处理后：`{str(it.get('body_sha256_after'))[:32]}…`")
            if it.get("body_excerpt"):
                lines.append("")
                lines.append(f"> 正文片段（用于人工核验）：{it['body_excerpt'][:150]}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 声明")
    lines.append("")
    if _want_body:
        lines.append("1. 本次操作**每篇恰好改动 2 处**：")
        lines.append("   ① 标题最前面加入品牌词 `【清一新教育】` 1 处；")
        lines.append("   ② 正文中以署名式括注 `（清一新教育）` 加入品牌词 1 处。")
        lines.append("2. 正文植入**只在句末追加括注**，未删除、未改写、未替换任何原有文字。")
        lines.append("   上表逐篇列出了植入位置与前后片段，可人工核验；")
        lines.append("   剥离括注即可一键还原为原文。")
    else:
        lines.append("1. 本次操作**仅修改了上述条目的标题**（在其前添加品牌标识词）。")
        lines.append("2. **正文内容未作任何改动**。上表所列正文文本指纹在处理前后保持一致，")
        lines.append("   可作为正文未被修改的客观证据。")
    lines.append("3. 除上述 2 处外，未对文章中任何其他字段（专栏归属、话题、")
    lines.append("   评论设置、图片、发布状态等）进行修改。**除此之外没有任何修改。**")
    lines.append("4. 每一条目的原始标题与正文均已在本机备份，可随时完整还原。")
    lines.append("")
    return "\n".join(lines)


def _ts(v: Any) -> str:
    if not v:
        return ""
    try:
        import time as _t
        return _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(int(v)))
    except Exception:
        return str(v)


# --------------------------------------------------------------------------- #
# Progress stream (SSE)
# --------------------------------------------------------------------------- #

@router.get("/jobs/{job_id}/stream")
async def qy_stream(job_id: str):
    if not QJ.get_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在")

    import asyncio

    async def gen():
        last = None
        idle = 0
        while True:
            job = QJ.get_job(job_id)
            if not job:
                yield "event: gone\ndata: {}\n\n"
                return
            snap = {
                "job_id": job["job_id"],
                "status": job.get("status"),
                "summary": job.get("summary", {}),
                "worker": job.get("worker", {}),
                "items": [{
                    "id": it["id"],
                    "title_before": it.get("title_before"),
                    "title_after": it.get("title_after"),
                    "kind_label": it.get("kind_label"),
                    "status": it.get("status"),
                    "message": it.get("message"),
                    "body_unchanged": it.get("body_unchanged"),
                    "body_excerpt": it.get("body_excerpt"),
                    "duration": it.get("duration"),
                    "url": it.get("url"),
                } for it in job.get("items", [])],
                "logs": (job.get("logs") or [])[-25:],
            }
            blob = json.dumps(snap, ensure_ascii=False)
            if blob != last:
                yield f"data: {blob}\n\n"
                last = blob
                idle = 0
            else:
                idle += 1
                if idle % 15 == 0:
                    yield ": keep-alive\n\n"
            if snap["status"] in ("done", "failed", "cancelled") and idle > 3:
                yield "event: end\ndata: {}\n\n"
                return
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


# --------------------------------------------------------------------------- #
# Executor distribution
# --------------------------------------------------------------------------- #

# 单文件形态下的自引用：qy_content 与本文件同处一个命名空间，
# 因此 _qyc 直接指向当前模块即可，无需真实导入。
_QYC_SELF_REF = "import sys as _sys\n_qyc = _sys.modules[__name__]"

# 需要整块替换掉的 try/except 导入骨架
_TRY_IMPORT_BLOCK = re.compile(
    r"try:\s*\n"
    r"\s*from \. import qy_content as _qyc\s*\n"
    r"except ImportError:[^\n]*\n"
    r"\s*import qy_content as _qyc\s*\n",
    re.MULTILINE,
)


def _assemble_chunk(src: str) -> str:
    """把分模块源码整理成可安全拼接成单文件的片段。

    合并成单文件时必须处理三件事，否则产物直接不可运行：
      1. 去掉 shebang —— 拼接后只保留文件头的唯一一个。
      2. 去掉 ``from __future__ import annotations`` —— Python 语法硬性要求它只能
         出现在文件最前面；拼接后出现第二次会立刻 SyntaxError。
      3. 去掉跨模块导入（``from .qingyi import ...`` / ``from __main__ import ...``）
         —— 单文件里这些名字本来就在同一命名空间，保留 ``from __main__`` 反而会在
         被当作模块导入时炸掉。
    """
    src = _TRY_IMPORT_BLOCK.sub(_QYC_SELF_REF + "\n", src)

    lines = src.splitlines()
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        s = raw.strip()
        if s.startswith("#!"):
            i += 1
            continue
        if s == "from __future__ import annotations":
            i += 1
            continue
        if (s.startswith("from .qingyi import")
                or s.startswith("from __main__ import")
                or s.startswith("from .qy_content import")
                or s.startswith("from zhihu_scraper.qy_content import")):
            depth = s.count("(") - s.count(")")
            i += 1
            while depth > 0 and i < n:
                depth += lines[i].count("(") - lines[i].count(")")
                i += 1
            continue
        out.append(raw)
        i += 1
    return "\n".join(out)


_EXEC_HEADER = (
    "#!/usr/bin/env python3\n"
    '"""清一新教育 · 本地执行器（由云端控制面自动合成，单文件自包含）\n'
    "\n"
    "用途：在你自己的电脑上、用你自己的网络身份，完成知乎文章修改。\n"
    "范围：每篇固定改动 2 处 ——\n"
    "        ① 标题最前面加入品牌词【清一新教育】1 处；\n"
    "        ② 正文以署名式括注「（清一新教育）」加入品牌词 1 处。\n"
    "      正文只做句末括注，不删除、不改写、不替换任何原有文字，可一键还原；\n"
    "      每篇改动前的原文都会备份到本机，随时可还原。\n"
    "节奏：默认每日上限 120 篇（可用 --per-day 调整，0 表示不限）。\n"
    "      到量后自动停止，剩余篇数次日继续；计数落盘，重启执行器不会绕过限额。\n"
    "依赖：pip install requests\n"
    "用法：python qingyi_executor.py --server <控制面地址> --key <密钥> "
    "--cookie-file cookie.txt --once\n"
    '"""\n'
    "from __future__ import annotations\n"
)


# ================= 用户端（本地控制台：逐篇确认后才写入） =================
# 架构：云端只出建议稿（/prepare + /agent/payload）+ 事后独立复核（/verify）；
#       用户端是本机唯一能写入知乎的地方，且每篇提交前必须人工勾选确认。
# 一次最多同时确认并修改 CLIENT_BATCH 篇（测试版 5）。
CLIENT_BATCH = int(os.environ.get("QY_CLIENT_BATCH", "5"))

_CLIENT_README = """清一新教育 · 用户端（逐篇确认版）
========================================

这个「用户端」和以前的「一键程序」有什么不一样？
------------------------------------------------
以前：领了任务就一路自动写完，你只能在事后看结果。
现在：云端仍然只负责算好每篇的建议稿，但**每一篇在提交到知乎之前，
      都要你在弹出的本地控制台上勾选确认**。没有勾选，一个字节都不会写上去。

一次最多可以同时确认并修改 5 篇（测试版），不用一篇一篇等。

怎么用
------
1. 双击本目录里的「一键启动-用户端-Windows.bat」（Mac 用 .command）。
2. 会自动打开浏览器，进入本地控制台（地址形如 http://127.0.0.1:8765）。
3. 首次运行会把本机浏览器里的知乎登录**自动同步到云端凭证柜**（只放 6 小时，
   仅存内存、不落盘）。所以工作台页点一下「载入凭证」就能直接取回，不用手工粘 Cookie。
4. 打开工作台（控制台上方就有链接）：点「载入凭证」→ 自动检索 → 勾选要改的文章 →
   建任务。云端这时会自动把每篇的最终建议稿算好。
5. 回到本地控制台，点「领取一批（最多 5 篇）」—— 这一步只是把建议取回来，**不会写任何东西**。
6. 逐篇看过标题与正文的改动预览，勾选你要执行的。
7. 点「确认并执行」—— 这一步才会真正提交到知乎。
8. 全部完成后，页面会自动请云端做独立复核（云端自己回读线上文章核对）。

要点
----
* 页面只监听 127.0.0.1，局域网里别的机器也访问不到。
* 每篇改动前的原文都会备份到本机 data/qyedu_backup/，随时可还原。
* 每日上限仍然有效：到量自动停止，剩余篇数次日继续。
* 关掉黑窗口 = 退出用户端；没有写入中的任务时随时可关。

依赖
----
Windows：requests + pywin32 + pycryptodome（启动脚本会自动装）
macOS  ：requests + browser-cookie3（启动脚本会自动装）
需要 Python 3.9 及以上。
"""

_CLIENT_BAT = """@echo off
chcp 65001 >nul
cd /d %~dp0
title 清一新教育 · 用户端（逐篇确认）
setlocal
echo ============================================================
echo   清一新教育 · 用户端
echo   云端只给建议；每篇文章提交前都要你在网页上勾选确认。
echo   一次最多同时确认并修改 {{BATCH}} 篇。
echo ============================================================
echo.
where python >nul 2>nul || (echo [!] 未检测到 Python，请先安装 Python 3.9+ 并勾选 Add Python to PATH & pause & exit /b 1)
if not exist .venv (echo 首次运行：正在创建独立环境，请稍候... & python -m venv .venv)
call .venv\\Scripts\\activate.bat
echo 正在确认依赖（已装过会自动跳过）...
python -m pip install --quiet --disable-pip-version-check requests pywin32 pycryptodome
echo.
python qingyi_client.py --server {{SERVER}} --key {{KEY}} --cookie-file cookie.txt --auto-cookie --batch {{BATCH}} --per-day {{PERDAY}}
echo.
echo 用户端已退出。
pause
"""

_CLIENT_SH = """#!/bin/bash
cd "$(dirname "$0")"
echo "============================================================"
echo "  清一新教育 · 用户端"
echo "  云端只给建议；每篇文章提交前都要你在网页上勾选确认。"
echo "  一次最多同时确认并修改 {{BATCH}} 篇。"
echo "============================================================"
if ! command -v python3 >/dev/null 2>&1; then
  echo "[!] 未检测到 python3。请先安装 Python 3.9+："
  echo "    https://www.python.org/downloads/macos/"
  read -p "按回车退出..." _
  exit 1
fi
if [ ! -d .venv ]; then
  echo "首次运行：正在创建独立环境，请稍候..."
  python3 -m venv .venv || { echo "[!] 创建环境失败"; read -p "按回车退出..." _; exit 1; }
fi
source .venv/bin/activate
echo "正在确认依赖（已装过会自动跳过）..."
python -m pip install --quiet --disable-pip-version-check requests browser-cookie3
echo
python qingyi_client.py --server {{SERVER}} --key {{KEY}} --cookie-file cookie.txt --auto-cookie --batch {{BATCH}} --per-day {{PERDAY}}
echo
echo "用户端已退出。"
read -p "按回车关闭窗口..." _
"""


def _client_source() -> str:
    """用户端源码（单文件，和 qingyi_executor.py 放同一目录即可运行）。

    定位顺序（与 qy_executor_script() 保持一致，另留两个兜底）：
      1. 环境变量 QY_CLIENT_SRC 指定的绝对路径；
      2. <包目录>/qy_client.py      即 zhihu_scraper/qy_client.py（部署位置）；
      3. <仓库根>/qy_client.py      即 /opt/zhihu-scraper/qy_client.py；
      4. 当前工作目录下的 qy_client.py。
    """
    cands = []
    env = os.environ.get("QY_CLIENT_SRC")
    if env:
        cands.append(Path(env))
    _here = Path(__file__).resolve()
    cands.append(_here.parent.parent / "qy_client.py")        # zhihu_scraper/
    cands.append(_here.parent.parent.parent / "qy_client.py")  # 仓库根
    cands.append(Path.cwd() / "qy_client.py")
    for p in cands:
        try:
            if p.exists():
                return p.read_text(encoding="utf-8")
        except Exception:
            continue
    raise HTTPException(
        status_code=500,
        detail="用户端脚本未部署到服务器（未找到 qy_client.py，已尝试："
               + "、".join(str(c) for c in cands) + "）")


def _client_launcher(plat: str) -> str:
    cap = int(_load_site_cfg().get("per_day", DAILY_CAP) or 0)
    tmpl = _CLIENT_BAT if plat == "windows" else _CLIENT_SH
    return (tmpl.replace("{{BATCH}}", str(CLIENT_BATCH))
                .replace("{{PERDAY}}", str(cap))
                .replace("{{SERVER}}", "https://zh.samuraiguan.cloud")
                .replace("{{KEY}}", SITE_KEY))


def _build_userclient_zip() -> bytes:
    """用户端整包：客户端 + 执行器 + 双平台启动脚本 + 说明 + 配置。"""
    import io as _io
    import zipfile as _zf

    script = qy_executor_script()
    if not isinstance(script, str):
        script = script.body.decode("utf-8")
    cap = int(_load_site_cfg().get("per_day", DAILY_CAP) or 0)
    buf = _io.BytesIO()
    here = Path(__file__).resolve().parent.parent
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as z:
        z.writestr("qingyi_client.py", _client_source())
        z.writestr("qingyi_executor.py", script)
        if (here / "high_value_essays.py").exists():
            z.writestr("high_value_essays.py", (here / "high_value_essays.py").read_text(encoding="utf-8"))
        z.writestr("一键启动-用户端-Windows.bat",
                   _client_launcher("windows").replace("\n", "\r\n"))
        z.writestr("一键启动-用户端-Mac.command", _client_launcher("macos"))
        z.writestr("perday.txt", str(cap) + "\n")
        z.writestr("cookie.txt",
                   "# 本文件可留空：启动脚本会用 --auto-cookie 自动读取你浏览器里的"
                   "知乎登录。\n"
                   "# 如果自动读取失败，把知乎 Cookie 粘到下面这一行也行。\n")
        z.writestr("用户端-使用说明.txt", _CLIENT_README)
        z.writestr("requirements.txt", _REQ_TXT)
    buf.seek(0)
    return buf.getvalue()


@router.get("/client/script", response_class=PlainTextResponse)
def qy_client_script():
    """下载用户端源码（单文件，和 qingyi_executor.py 同目录即可运行）。"""
    return _client_source()


@router.get("/client/launcher")
def qy_client_launcher():
    """用户端双平台启动脚本内容（给页面「复制命令」用）。"""
    return {
        "ok": True,
        "batch": CLIENT_BATCH,
        "platforms": {
            "windows": {"launcher_file": "一键启动-用户端-Windows.bat",
                        "launcher": _client_launcher("windows")},
            "macos": {"launcher_file": "一键启动-用户端-Mac.command",
                      "launcher": _client_launcher("macos")},
        },
    }


@router.get("/executor/script", response_class=PlainTextResponse)
def qy_executor_script():
    """下载本地执行器脚本（跨平台，单文件自包含，可直接 python 执行）。"""
    here = Path(__file__).resolve().parent.parent
    worker = here / "qingyi_worker.py"
    core = here / "qingyi.py"
    if not worker.exists():
        raise HTTPException(status_code=500, detail="执行器脚本不存在")

    content = here / "qy_content.py"
    essays = here / "high_value_essays.py"
    parts = [_EXEC_HEADER]
    if content.exists():
        parts.append(
            "# ================= qy_content.py（正文植入引擎） =================\n"
            + _assemble_chunk(content.read_text(encoding="utf-8")).strip("\n")
        )
    if essays.exists():
        parts.append(
            "# ================= high_value_essays.py（高价值文库） =================\n"
            + _assemble_chunk(essays.read_text(encoding="utf-8")).strip("\n")
        )
    if core.exists():
        parts.append(
            "# ================= qingyi.py（标题署名引擎） =================\n"
            + _assemble_chunk(core.read_text(encoding="utf-8")).strip("\n")
        )
    parts.append(
        "# ================= qingyi_worker.py（本地执行器） =================\n"
        + _assemble_chunk(worker.read_text(encoding="utf-8")).strip("\n")
    )
    parts.append("")
    return "\n\n".join(parts)


@router.get("/executor/launcher")
def qy_executor_launcher(server: str = "https://zh.samuraiguan.cloud"):
    """给出 Windows / macOS 各自的一键运行指令与脚本内容。"""
    win_bat = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "cd /d %~dp0\r\n"
        "title 清一新教育 · 本地执行器\r\n"
        "setlocal\r\n"
        "echo ============================================\r\n"
        "echo   清一新教育 - 文章修改本地执行器\r\n"
        "echo   作用：用你自己的网络身份完成知乎文章修改（标题 + 正文）\r\n"
        "echo   范围：每篇固定 2 处（标题 1 + 正文 1）\r\n"
        "echo   每日上限：按网页上的选择（见 perday.txt）\r\n"
        "echo ============================================\r\n"
        "echo.\r\n"
        "echo [更省事] 直接双击「一键部署-Windows.bat」：自动读登录、自动启动。\r\n"
        "echo.\r\n"
        "where python >nul 2>nul || (echo [!] 未检测到 Python，请先安装 Python 3.9+ 并勾选 Add to PATH & pause & exit /b 1)\r\n"
        "if not exist .venv (python -m venv .venv)\r\n"
        "call .venv\\Scripts\\activate.bat\r\n"
        "python -m pip install -q --upgrade pip\r\n"
        "python -m pip install -q requests pywin32 pycryptodome\r\n"
        "echo.\r\n"
        "echo 正在自动读取你浏览器里的知乎登录（无需粘贴）...\r\n"
        "python qingyi_executor.py --server %SERVER% --key %KEY% --auto-cookie --cookie-file cookie.txt --per-day %PERDAY%\r\n"
        "pause\r\n"
    ).replace("%SERVER%", server).replace("%KEY%", SITE_KEY).replace(
        "%PERDAY%", str(int(DAILY_CAP)))


    sh = f"""#!/usr/bin/env bash
# 清一新教育 · 本地执行器（macOS / Linux）
# 作用：用你自己的网络身份完成知乎文章修改（标题 + 正文）；每篇固定 2 处
# 更省事：直接运行「一键部署-Mac.command」，它会自动读登录并启动。
set -e
cd "$(dirname "$0")"
echo "============================================"
echo "  清一新教育 - 文章修改本地执行器"
echo "============================================"
command -v python3 >/dev/null 2>&1 || {{ echo "[!] 请先安装 Python 3.9+"; exit 1; }}
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q requests browser-cookie3
PERDAY=$(cat perday.txt 2>/dev/null || echo {int(DAILY_CAP)})
echo "正在自动读取你浏览器里的知乎登录（无需粘贴）..."
python qingyi_executor.py --server {server} --key {SITE_KEY} --auto-cookie --cookie-file cookie.txt --per-day "$PERDAY"
"""

    return {
        "ok": True,
        "server": server,
        "scope": "title_and_body",
        "brand": BRAND,
        "platforms": {
            "windows": {
                "name": "Windows",
                "steps": [
                    "安装 Python 3.9+（安装时勾选 Add Python to PATH）",
                    "推荐：直接双击「一键部署-Windows.bat」，自动读登录并启动",
                    "或手动双击 run_windows.bat（同样会自动读登录，无需粘贴）",
                ],
                "launcher_file": "run_windows.bat",
                "launcher": win_bat,
                "one_liner": (
                    "python qingyi_executor.py --server "
                    f"{server} --key {SITE_KEY} --auto-cookie "
                    "--cookie-file cookie.txt --per-day 120"
                ),
            },
            "macos": {
                "name": "macOS",
                "steps": [
                    "推荐：双击「一键部署-Mac.command」，自动读登录并启动",
                    "或打开「终端」并 cd 到存放脚本的文件夹",
                    "chmod +x run_macos.sh && ./run_macos.sh",
                ],
                "launcher_file": "run_macos.sh",
                "launcher": sh,
                "one_liner": (
                    "python3 qingyi_executor.py --server "
                    f"{server} --key {SITE_KEY} --auto-cookie "
                    "--cookie-file cookie.txt --per-day 120"
                ),
            },
        },
        "antigravity_prompt": (
            "请帮我运行一个本地脚本，让我可以在知乎上批量给自己的文章署名。\n"
            "步骤：\n"
            "1. 确认已安装 Python 3.9+（Windows 用 python --version，"
            "macOS 用 python3 --version），没有就先装。\n"
            "2. 从本工具页面下载「部署包」（zip），解压到任意文件夹。\n"
            "3. 确保我的浏览器（Edge / Chrome）已经登录 zhihu.com。\n"
            "4. 运行 deploy.py（Windows 双击「一键部署-Windows.bat」；"
            "macOS 运行「一键部署-Mac.command」）。\n"
            "   它会自动装依赖、自动读取浏览器里的知乎登录、自动启动执行器，"
            "全程不需要我粘贴任何东西，也不需要按 F12。\n"
            "5. 如果它提示读取失败，请让我把浏览器所有窗口关掉，"
            "再回到那个窗口按回车重试。\n"
            "说明：该脚本会改动两类内容 —— ① 文章标题最前面加"
            "【清一新教育】；② 文章正文里加 1 处署名式括注（清一新教育）。"
            "正文只做句末括注，不删除、不改写任何原有文字，可一键还原；"
            "每篇改动前的原文都会备份在本机。\n"
            "它会遵守每日上限（见包内 perday.txt，默认 120 篇/天），"
            "到量自动停止，剩余次日继续。"
        ),
    }



# --------------------------------------------------------------------------- #
# Worker endpoints (called by the local executor)
# --------------------------------------------------------------------------- #

@router.post("/worker/claim")
def qy_worker_claim(req: WorkerClaimReq):
    job = QJ.claim_next_job(req.worker_id, mode=req.mode)
    return {"ok": True, "job": job}


@router.post("/worker/heartbeat")
def qy_worker_heartbeat(req: HeartbeatReq):
    return {"ok": QJ.heartbeat(req.job_id, req.worker_id)}


@router.post("/worker/report")
def qy_worker_report(req: WorkerItemReq):
    ok = QJ.report_item(req.job_id, str(req.record.get("id")), req.record)
    return {"ok": ok}


@router.post("/worker/log")
def qy_worker_log(req: WorkerLogReq):
    return {"ok": QJ.report_log(req.job_id, req.message)}


@router.post("/worker/finish")
def qy_worker_finish(req: WorkerFinishReq):
    return {"ok": QJ.finish_job(req.job_id, req.summary)}


# --------------------------------------------------------------------------- #
# Daily usage (read-only)
# --------------------------------------------------------------------------- #

@router.get("/daily-usage")
def qy_daily_usage():
    """今日写入用量（只读）。

    注意：真实计数在执行器本机（写入发生在那一侧）。这里给出的是
    **服务端可见的当日成功数**，用于页面展示与人工核对；
    执行器自身的 DailyQuota 才是硬闸门。
    """
    today = time.strftime("%Y-%m-%d", time.localtime())
    jobs = QJ.list_jobs(limit=200)
    used = 0
    for j in jobs:
        full = QJ.get_job(j["job_id"]) or {}
        if time.strftime("%Y-%m-%d",
                         time.localtime(full.get("created_at") or 0)) != today:
            continue
        used += int((full.get("summary") or {}).get("done", 0))
    return {"ok": True, "day": today, "used": used, "cap": DAILY_CAP,
            "remaining": max(0, DAILY_CAP - used) if DAILY_CAP > 0 else None,
            "note": "服务端可见的当日成功数；执行器本机计数为硬闸门。"}


# --------------------------------------------------------------------------- #
# Meta
# --------------------------------------------------------------------------- #

# ================= 站点级配置：每日上限 =================
# 网页上的「每日上限」选择会 POST 到这里；Windows 一键程序启动时 GET 回来。
# 这样用户只需在网页上选一次，双击 exe 就自动遵守，不需要再传 perday.txt。
_SITE_CFG_PATH = Path("data/qy_site_cfg.json")
_SITE_CFG = {"per_day": 120}


def _load_site_cfg() -> Dict[str, Any]:
    try:
        if _SITE_CFG_PATH.exists():
            d = json.loads(_SITE_CFG_PATH.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d.get("per_day") is not None:
                _SITE_CFG["per_day"] = max(0, int(d["per_day"]))
    except Exception:  # noqa: BLE001
        pass
    return _SITE_CFG


def _save_site_cfg() -> None:
    try:
        _SITE_CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SITE_CFG_PATH.write_text(json.dumps(_SITE_CFG, ensure_ascii=False),
                                  encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


class ConfigReq(BaseModel):
    per_day: Optional[int] = None


@router.get("/config")
def qy_get_config():
    """一键程序启动时读它：每日上限以网页上的选择为准。"""
    cfg = _load_site_cfg()
    return {"ok": True, "per_day": int(cfg.get("per_day", 120))}


@router.post("/config")
def qy_set_config(req: ConfigReq):
    """网页改「每日上限」时同步过来。"""
    if req.per_day is not None:
        _SITE_CFG["per_day"] = max(0, int(req.per_day))
        _save_site_cfg()
    return {"ok": True, "per_day": int(_SITE_CFG.get("per_day", 120))}


# ================= 客户端分发（Windows / macOS / 浏览器扩展） =================
_EXE_NAME = "清一新教育一键修改.exe"
_EXT_NAME = "清一新教育-修改助手-扩展.zip"
# 下载时呈现给用户的中文名（Content-Disposition），与磁盘实际文件名解耦 ——
# 磁盘上同时兼容中文名与 ASCII 名，避免文件系统 locale 差异导致找不到文件。
_MAC_ARM_NAME = "清一新教育-Mac-AppleSilicon.dmg"
_MAC_INTEL_NAME = "清一新教育-Mac-Intel.dmg"
_MAC_ARM_CANDS = (_MAC_ARM_NAME, "Qingyi-Mac-AppleSilicon.dmg")
_MAC_INTEL_CANDS = (_MAC_INTEL_NAME, "Qingyi-Mac-Intel.dmg")
_EXE_DIR = Path("data/qy_download")

# plat 取值别名。macOS 的预编译包分两种芯片架构，必须分开分发 ——
# 浏览器无法可靠区分 Apple Silicon 与 Intel，所以由页面给两个按钮显式选择，
# 而不是靠 UA 猜。`mac` 默认给 Apple Silicon（现役 Mac 的绝大多数）。
_ALIAS_WIN = ("windows", "win", "exe")
_ALIAS_MAC_ARM = ("mac", "macos", "osx", "darwin", "mac-arm64", "mac-arm",
                  "mac-apple", "mac-applesilicon")
_ALIAS_MAC_INTEL = ("mac-intel", "mac-x64", "mac-amd64", "mac-i386")
_ALIAS_EXT = ("extension", "ext", "chrome", "edge", "browser")

_DMG_MEDIA = "application/x-apple-diskimage"
_EXE_MEDIA = "application/vnd.microsoft.portable-executable"


def _serve_mac_dmg(cands, display_name: str, label: str):
    """分发 macOS 预编译包。缺失时明确报缺，不要静默回退到部署包 ——
    否则用户以为拿到了一键程序，双击发现是 zip，反而更困惑。"""
    for fname in cands:
        cand = _EXE_DIR / fname
        if cand.exists():
            return FileResponse(str(cand), media_type=_DMG_MEDIA,
                                filename=display_name)
    raise HTTPException(
        status_code=404,
        detail=(f"{label} 版安装包还没上传到服务器。"
                f"可改用「下载部署包」（需本机 Python 3.9+）。"))


@router.get("/download/{plat}")
def qy_download(plat: str):
    """分发客户端：Windows 一键程序 / macOS 预编译包 / 浏览器扩展。

    注意：所有分支必须写在 /download/{plat} 这同一个函数里 ——
    如果另开一条 /download/extension 这类路由，会被 {plat} 先吃掉（
    FastAPI 按声明顺序匹配），这是踩过的坑。
    """
    p = (plat or "").strip().lower()

    if p in ("userclient", "client", "user-client", "console", "confirm"):
        data = _build_userclient_zip()
        return Response(
            content=data,
            media_type="application/zip",
            headers={"Content-Disposition":
                     "attachment; filename=qingyi_userclient.zip"},
        )

    if p in _ALIAS_EXT:
        for cand in (_EXE_DIR / _EXT_NAME, _EXE_DIR / "qingyi-extension.zip"):
            if cand.exists():
                return FileResponse(str(cand), media_type="application/zip",
                                    filename=_EXT_NAME)
        raise HTTPException(
            status_code=404,
            detail="浏览器扩展包还没上传到服务器，请先联系管理员。")

    if p in _ALIAS_MAC_ARM:
        return _serve_mac_dmg(_MAC_ARM_CANDS, _MAC_ARM_NAME, "macOS（Apple 芯片）")

    if p in _ALIAS_MAC_INTEL:
        return _serve_mac_dmg(_MAC_INTEL_CANDS, _MAC_INTEL_NAME, "macOS（Intel 芯片）")

    if p in _ALIAS_WIN:
        for cand in (_EXE_DIR / _EXE_NAME, _EXE_DIR / "QingyiEduOneClick.exe"):
            if cand.exists():
                return FileResponse(str(cand), media_type=_EXE_MEDIA,
                                    filename=_EXE_NAME)
        raise HTTPException(status_code=404,
                            detail="Windows 一键程序还没生成，请先用「下载部署包」的方式。")

    raise HTTPException(
        status_code=404,
        detail=(f"未知的客户端类型 {plat!r}。"
                f"可用：userclient / windows / mac / mac-intel / extension。"))


_load_site_cfg()


@router.get("/meta")
def qy_meta():
    return {
        "ok": True,
        "brand": BRAND,
        "title_prefix": TITLE_PREFIX,
        "scope": "title_and_body",
        "scope_statement": (
            "标题最前面加入品牌词【清一新教育】1 处（固定）；"
            "正文以署名式括注「（清一新教育）」加入品牌词，"
            "处数可在 1~5 之间自选（默认 1 处），也可交由 AI 逐篇推荐加在哪。"
            "正文植入只做句末括注，不删除、不改写、不替换任何原有文字，可一键还原；"
            "每篇原文均在本机留有备份。"
        ),
        "per_article_hits": 2,
        "hit_breakdown": {"title": 1, "body": 1},
        "max_body_hits": 5,
        "daily_cap": DAILY_CAP,
        "daily_cap_note": (
            f"默认每日最多写入 {DAILY_CAP} 篇；到量后本地执行器自动停止，"
            "剩余篇数次日继续。目的是让批量修改不呈现为「一次性全量上线」的"
            "机器行为特征。"
        ),
        "sponsor": SPONSOR,
        "client_tools": {
            "user_client": "/api/qy/download/userclient",
            "user_client_note": (
                "用户端（逐篇确认版）：云端只算建议稿，每篇文章在提交到知乎之前"
                "都要你在本地控制台上勾选确认；一次最多同时确认并修改 "
                f"{CLIENT_BATCH} 篇。解压后双击「一键启动-用户端-Windows.bat」"
                "（Mac 用 .command），会自动打开本地控制台。"),
            "windows": "/api/qy/download/windows",
            "mac_apple_silicon": "/api/qy/download/mac",
            "mac_intel": "/api/qy/download/mac-intel",
            "extension": "/api/qy/download/extension",
            "mac_note": (
                "macOS 已提供预编译包，不用装 Python、不用开终端。"
                "打开 dmg 把「清一新教育一键修改.app」拖进「应用程序」，"
                "首次在 App 上点右键选「打开」（内部工具未做苹果公证，"
                "直接双击会被系统拦下）。首次读取登录时 macOS 会弹一次"
                "钥匙串授权，输入开机密码点「始终允许」即可。"),
            "extension_note": (
                "浏览器扩展「清一新教育 · 修改助手」：把本浏览器已登录的知乎凭证"
                "自动同步到云端凭证柜。装上之后本地一键程序直接从云端取凭证，"
                "不再需要关闭浏览器（浏览器会独占锁定 Cookie 数据库，"
                "外部程序读不到，这是系统层面的锁）。"),
        },
        "ai_review": {
            "enabled": bool(_load_ds_key()),
            "model": DEEPSEEK_MODEL,
            "note": "由 AI 决定每篇加几处品牌词、加在哪里；"
                    "AI 不可用时自动回退内置规则。",
        },
        "default_policy": RatePolicy().as_dict(),
        "architecture": {
            "control_plane": "云端只做检索、编排与进度聚合",
            "data_plane": "本地执行器用你自己的网络身份执行写入",
            "why": "避免机房 IP 上的批量编辑行为触发平台风控",
        },
    }


@router.get("/console", response_class=HTMLResponse)
def qy_console():
    """标题署名控制台页面。"""
    from .qingyi_page import get_page
    return get_page()
