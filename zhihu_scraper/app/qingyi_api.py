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

import json
import os
import platform
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import (HTMLResponse, PlainTextResponse, Response,
                               StreamingResponse)
from pydantic import BaseModel

from ..qingyi import BRAND, QingyiTitleSigner, RatePolicy
from .. import qingyi_jobs as QJ

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
DAILY_CAP = 120


# --------------------------------------------------------------------------- #
# AI 审核（DeepSeek）：由模型决定每篇加几处品牌词、加在哪里
# --------------------------------------------------------------------------- #
# 密钥来源：环境变量 DEEPSEEK_API_KEY 优先，其次 data/deepseek_key.txt（不入库）。
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

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
    "- picks：从候选中挑 0~2 个最适合的句末位置。优先与教育/成长/学习/方法论相关的"
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
                   want_body: bool) -> Dict[str, Any]:
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

    cands = qc.scan_scenes(body, limit=4)  # 候选池已内置段落间隔约束
    cand_list = [{"idx": i, "anchor": c.anchor, "para": c.para_text[:90]}
                 for i, c in enumerate(cands)]

    fallback = {
        "ok": True, "used_ai": False, "title": t, "title_add": True,
        "picks": ([{"anchor": cands[0].anchor, "reason": cands[0].reason,
                    "para": cands[0].para_text[:90]}]
                  if (want_body and cands) else []),
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
                    f"候选位置列表：\n{cand_txt}")
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
                "max_tokens": 400,
                "response_format": {"type": "json_object"},
                "stream": False,
            },
            timeout=45,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?|```$", "", content.strip(),
                         flags=re.M).strip()
        data = json.loads(content)
        title_add = bool(data.get("title_add", True))
        picks: List[Dict[str, Any]] = []
        for p in (data.get("picks") or [])[:2]:
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
    # 每篇固定 2 处：标题 1 处 + 正文 1 处
    title: bool = True
    inject_body: bool = True
    body_hits: int = 1


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


class BundleReq(BaseModel):
    """一键执行器打包下载：把当前凭证写进包里的 cookie.txt。"""
    cookie: str


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
    pins = signer.list_pins(cap=req.cap) if req.include_pins else []
    answers = signer.list_answers(cap=req.cap) if req.include_answers else []

    def _stat(rows: List[Dict[str, Any]]) -> Dict[str, int]:
        branded = sum(1 for r in rows if r.get("has_brand"))
        return {"total": len(rows), "branded": branded,
                "pending": len(rows) - branded}

    items: List[Dict[str, Any]] = []
    for r in articles + pins + answers:
        items.append({
            "id": r["id"],
            "type": r["type"],
            "kind_label": r["kind_label"],
            "title": r["title"],
            "title_after": r["title"] if r.get("has_brand")
                           else f"{TITLE_PREFIX}{r['title']}",
            "has_brand": r.get("has_brand", False),
            "url": r.get("url", ""),
            "created": r.get("created"),
            "updated": r.get("updated"),
            "voteup_count": r.get("voteup_count"),
            "comment_count": r.get("comment_count"),
            "excerpt": r.get("excerpt", ""),
            "editable": r["type"] == "article",
            "note": r.get("note", ""),
        })

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


@router.post("/jobs")
def qy_create_job(req: CreateJobReq):
    try:
        job = QJ.create_job(
            _normalise_items(req.items), policy=req.policy, mode=req.mode,
            features={"title": bool(req.title),
                      "inject_body": bool(req.inject_body)})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
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
    scenes = qc.scan_scenes(body, limit=1)
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
        r = _ai_review_one(cookie, req.id, req.title, req.want_body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"读取文章失败：{exc}")
    return r


_EXEC_BAT = (
    "@echo off\r\n"
    "chcp 65001 >nul\r\n"
    "cd /d %~dp0\r\n"
    "echo [1/2] Checking Python and dependency (requests)...\r\n"
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
    "%PY% -c \"import requests\" >nul 2>nul\r\n"
    "if errorlevel 1 %PY% -m pip install requests\r\n"
    "echo [2/2] Starting executor. Press Ctrl+C to stop safely.\r\n"
    "%PY% qingyi_executor.py --server https://zh.samuraiguan.cloud "
    "--key guanjun2026 --cookie-file cookie.txt\r\n"
    "pause\r\n"
)

_EXEC_SH = (
    "#!/usr/bin/env bash\n"
    'cd "$(dirname "$0")"\n'
    'python3 -c "import requests" 2>/dev/null || pip3 install requests\n'
    "python3 qingyi_executor.py --server https://zh.samuraiguan.cloud "
    "--key guanjun2026 --cookie-file cookie.txt\n"
)

_EXEC_README = (
    "清一新教育 · 本地执行器 一键包\n"
    "================================\n\n"
    "包里已经带好了一切：执行器脚本、你的知乎凭证（cookie.txt）、一键启动脚本。\n"
    "不需要再粘贴任何东西。\n\n"
    "Windows 用户：\n"
    "  1. 把整个文件夹解压到任意位置（比如桌面）\n"
    "  2. 双击「一键启动-Windows.bat」\n"
    "  3. 看到进度即可；按 Ctrl+C 或直接关窗口可随时安全停止\n\n"
    "Mac 用户：\n"
    "  1. 解压后打开「终端」，cd 到这个文件夹\n"
    "  2. 运行:  bash 一键启动-Mac.command\n\n"
    "内置安全机制（自动生效，无需配置）：\n"
    "  · 每天最多 120 篇，到量自动停止，剩余次日继续\n"
    "  · 每小时最多 12 篇；篇与篇之间随机间隔 25~75 秒\n"
    "  · 每连续 5 篇休息 3~7 分钟；连续失败 3 次自动中止\n"
    "  · 每篇改动前原文自动备份到本机，可一键还原\n"
    "  · 每篇固定改动 2 处：标题 1 处 + 正文 1 处（AI 审核决定位置）\n\n"
    "首次运行需要联网安装 requests（自动完成，几秒钟）。\n"
)


@router.post("/executor/bundle")
def qy_executor_bundle(req: BundleReq):
    """一键打包：qingyi_executor.py + cookie.txt + 一键启动脚本 + 说明。

    凭证只写进下载包，不落服务器磁盘。
    """
    cookie = (req.cookie or "").strip()
    if not cookie:
        raise HTTPException(status_code=400,
                            detail="请先在第 1 步粘贴知乎凭证（或点一键获取）")
    script = qy_executor_script()
    if not isinstance(script, str):
        script = script.body.decode("utf-8")
    import io as _io
    import zipfile as _zf

    buf = _io.BytesIO()
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as z:
        z.writestr("qingyi_executor.py", script)
        z.writestr("cookie.txt", cookie)
        z.writestr("一键启动-Windows.bat", _EXEC_BAT)
        z.writestr("一键启动-Mac.command", _EXEC_SH)
        z.writestr("使用说明.txt", _EXEC_README)
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


@router.get("/executor/script", response_class=PlainTextResponse)
def qy_executor_script():
    """下载本地执行器脚本（跨平台，单文件自包含，可直接 python 执行）。"""
    here = Path(__file__).resolve().parent.parent
    worker = here / "qingyi_worker.py"
    core = here / "qingyi.py"
    if not worker.exists():
        raise HTTPException(status_code=500, detail="执行器脚本不存在")

    content = here / "qy_content.py"
    parts = [_EXEC_HEADER]
    if content.exists():
        parts.append(
            "# ================= qy_content.py（正文植入引擎） =================\n"
            + _assemble_chunk(content.read_text(encoding="utf-8")).strip("\n")
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
        "setlocal\r\n"
        "echo ============================================\r\n"
        "echo   清一新教育 - 文章修改本地执行器\r\n"
        "echo   作用：用你自己的网络身份完成知乎文章修改（标题 + 正文）\r\n"
        "echo   范围：每篇 2 处（标题 1 + 正文 1）；每日上限 120 篇\r\n"
        "echo ============================================\r\n"
        "echo.\r\n"
        "where python >nul 2>nul || (echo [!] 未检测到 Python，请先安装 Python 3.9+ 并勾选 Add to PATH & pause & exit /b 1)\r\n"
        "if not exist .venv (python -m venv .venv)\r\n"
        "call .venv\\Scripts\\activate.bat\r\n"
        "python -m pip install -q --upgrade pip\r\n"
        "python -m pip install -q requests\r\n"
        "echo.\r\n"
        "set /p QYKEY=请输入站点访问密钥: \r\n"
        "set /p QYCOOKIE=请粘贴知乎凭证（或直接回车，稍后从 cookie.txt 读取）: \r\n"
        "if \"%QYCOOKIE%\"==\"\" (\r\n"
        "  if exist cookie.txt (\r\n"
        "    python qingyi_executor.py --server %SERVER% --key %QYKEY% --cookie-file cookie.txt\r\n"
        "  ) else (\r\n"
        "    echo [!] 未找到 cookie.txt，请把知乎凭证保存为 cookie.txt 后重试\r\n"
        "    pause\r\n"
        "    exit /b 1\r\n"
        "  )\r\n"
        ") else (\r\n"
        "  python qingyi_executor.py --server %SERVER% --key %QYKEY% --cookie \"%QYCOOKIE%\"\r\n"
        ")\r\n"
        "pause\r\n"
    ).replace("%SERVER%", server)

    sh = f"""#!/usr/bin/env bash
# 清一新教育 · 标题署名本地执行器（macOS / Linux）
# 作用：用你自己的网络身份完成知乎文章修改（标题 + 正文）；每日上限 120 篇
set -e
echo "============================================"
echo "  清一新教育 - 标题署名本地执行器"
echo "============================================"
command -v python3 >/dev/null 2>&1 || {{ echo "[!] 请先安装 Python 3.9+"; exit 1; }}
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q requests
read -r -p "请输入站点访问密钥: " QYKEY
if [ -f cookie.txt ]; then
  COOKIE_ARG="--cookie-file cookie.txt"
else
  read -r -p "请粘贴知乎凭证: " QYCOOKIE
  COOKIE_ARG="--cookie $QYCOOKIE"
fi
python qingyi_executor.py --server {server} --key "$QYKEY" $COOKIE_ARG
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
                    "新建一个文件夹，保存 qingyi_executor.py 与 cookie.txt",
                    "双击 run_windows.bat 启动",
                ],
                "launcher_file": "run_windows.bat",
                "launcher": win_bat,
                "one_liner": (
                    "python qingyi_executor.py --server "
                    f"{server} --key <你的密钥> --cookie-file cookie.txt"
                ),
            },
            "macos": {
                "name": "macOS",
                "steps": [
                    "打开「终端」",
                    "cd 到存放脚本的文件夹",
                    "chmod +x run_macos.sh && ./run_macos.sh",
                ],
                "launcher_file": "run_macos.sh",
                "launcher": sh,
                "one_liner": (
                    "python3 qingyi_executor.py --server "
                    f"{server} --key <你的密钥> --cookie-file cookie.txt"
                ),
            },
        },
        "antigravity_prompt": (
            "请帮我运行一个本地脚本。步骤：\n"
            "1. 确认已安装 Python 3.9+（Windows 用 python --version，"
            "macOS 用 python3 --version），没有就先装。\n"
            "2. 在当前目录执行 pip install requests。\n"
            "3. 把 https://zh.samuraiguan.cloud 首页提供的『本地执行器』"
            "下载为 qingyi_executor.py。\n"
            "4. 把知乎登录凭证保存为同目录下的 cookie.txt。\n"
            "5. 运行：python qingyi_executor.py --server "
            f"{server} --key <站点访问密钥> --cookie-file cookie.txt\n"
            "说明：该脚本只会修改知乎文章的标题，不会改动正文。"
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

@router.get("/meta")
def qy_meta():
    return {
        "ok": True,
        "brand": BRAND,
        "title_prefix": TITLE_PREFIX,
        "scope": "title_and_body",
        "scope_statement": (
            "每篇文章固定改动 2 处：标题最前面加入品牌词【清一新教育】1 处；"
            "正文以署名式括注「（清一新教育）」加入品牌词 1 处。"
            "正文植入只做句末括注，不删除、不改写、不替换任何原有文字，可一键还原；"
            "每篇原文均在本机留有备份。"
        ),
        "per_article_hits": 2,
        "hit_breakdown": {"title": 1, "body": 1},
        "daily_cap": DAILY_CAP,
        "daily_cap_note": (
            f"默认每日最多写入 {DAILY_CAP} 篇；到量后本地执行器自动停止，"
            "剩余篇数次日继续。目的是让批量修改不呈现为「一次性全量上线」的"
            "机器行为特征。"
        ),
        "sponsor": SPONSOR,
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
