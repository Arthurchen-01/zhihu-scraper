"""清一新教育 · 云端控制面：任务编排、进度聚合、本地执行器分发。

控制面（本模块，运行在 zh.samuraiguan.cloud）只负责：
  * 目标发现（只读枚举调用者本人的知乎资产）
  * 依据用户勾选结果创建任务
  * 聚合进度、渲染结果、留存"正文零修改"证据
  * 向本地执行器分发任务与执行脚本

数据面（本地执行器）负责真正的知乎写入，使编辑行为来自操作者自身网络身份，
而不是机房 IP —— 这是规避平台风控的关键。

任务状态机：
    pending  --claim-->  claimed --progress-->  running --finish-->  done
                                                            \\--> failed
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .qingyi import BRAND, RatePolicy

# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #

_DEFAULT_STORE = Path("data/qy_jobs.json")
_lock = threading.RLock()
_STORE: Dict[str, Any] = {"jobs": {}, "seq": 0}
_loaded_path: Optional[Path] = None

MAX_JOBS_KEPT = 120


def _store_path() -> Path:
    import os
    env = os.environ.get("QY_JOB_STORE")
    return Path(env) if env else _DEFAULT_STORE


def _load() -> None:
    global _STORE, _loaded_path
    p = _store_path()
    if _loaded_path == p:
        return
    _loaded_path = p
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "jobs" in data:
                _STORE = data
                return
    except Exception:
        pass
    _STORE = {"jobs": {}, "seq": 0}


def _save() -> None:
    p = _store_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(_STORE, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass


def save() -> None:
    """公开封装：把任务库落盘（控制面 API 用它保存预修改/复核结果）。"""
    _save()


def recompute(job: Dict[str, Any]) -> None:
    """公开封装：重算 summary（预修改把某些条目判为 skipped 后要用）。"""
    _recompute(job)


def _trim() -> None:
    jobs = _STORE.get("jobs", {})
    if len(jobs) <= MAX_JOBS_KEPT:
        return
    ordered = sorted(jobs.items(), key=lambda kv: kv[1].get("created_at", 0),
                     reverse=True)
    keep = dict(ordered[:MAX_JOBS_KEPT])
    _STORE["jobs"] = keep


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _now() -> int:
    return int(time.time())


def _new_job_id() -> str:
    _STORE["seq"] = int(_STORE.get("seq", 0)) + 1
    stamp = time.strftime("%Y%m%d", time.localtime())
    return f"qy{stamp}-{_STORE['seq']:03d}-{secrets.token_hex(2)}"


def _recompute(job: Dict[str, Any]) -> None:
    items = job.get("items", [])
    summary = {"total": len(items), "done": 0, "skipped": 0,
               "failed": 0, "unsupported": 0, "pending": 0}
    for it in items:
        st = it.get("status", "pending")
        if st in summary:
            summary[st] += 1
        elif st == "saved_not_published":
            summary["failed"] += 1
        else:
            summary["pending"] += 1
    job["summary"] = summary

    if job.get("status") in ("done", "failed", "cancelled"):
        return
    if summary["pending"] == 0:
        job["status"] = "done"
        job["finished_at"] = _now()
    elif job.get("status") in ("pending", "claimed"):
        pass


def add_log(job: Dict[str, Any], msg: str) -> None:
    logs = job.setdefault("logs", [])
    logs.append({"ts": _now(), "msg": msg})
    if len(logs) > 400:
        del logs[: len(logs) - 400]


# --------------------------------------------------------------------------- #
# Public API — control plane
# --------------------------------------------------------------------------- #

def create_job(items: List[Dict[str, Any]], policy: Optional[Dict[str, Any]] = None,
               mode: str = "local", created_by: str = "web",
               features: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a署名 task from the user's checkbox selection."""
    _load()
    with _lock:
        job_id = _new_job_id()

        # 开关必须在条目循环之前解析：循环里要用它判断是否预跳过
        feat = dict(features or {})
        want_title = bool(feat.get("title", True))
        want_body = bool(feat.get("inject_body", True))

        entries: List[Dict[str, Any]] = []
        for raw in items:
            iid = str(raw.get("id") or "").strip()
            if not iid:
                continue
            title_before = str(raw.get("title") or "")
            # AI 审核计划：title_add 决定标题是否加；picks 决定正文加在哪
            plan = raw.get("ai_plan") or None
            ai_picks = []
            if plan:
                for p in (plan.get("picks") or []):
                    if p and p.get("anchor"):
                        ai_picks.append({"anchor": p["anchor"],
                                         "reason": str(p.get("reason") or "")})
            ai_title_add = True
            if plan is not None and plan.get("title_add") is False:
                ai_title_add = False
            entries.append({
                "id": iid,
                "type": str(raw.get("type") or "article"),
                "kind_label": str(raw.get("kind_label") or "文章"),
                "url": str(raw.get("url") or ""),
                "title_before": title_before,
                "title_after": title_before if (BRAND in title_before
                                                or not ai_title_add)
                               else f"【{BRAND}】{title_before}",
                "has_brand": BRAND in title_before,
                "body_excerpt": str(raw.get("excerpt") or "")[:160],
                # 只有"标题已署名 且 无需正文植入"才预跳过
                "status": ("skipped"
                           if (BRAND in title_before and not want_body)
                           else "pending"),
                "message": ("标题已含品牌词" if BRAND in title_before
                            else ""),
                "body_sha256_before": "",
                "body_sha256_after": "",
                "body_unchanged": None,
                "body_hits_before": 0,
                "body_hits_after": 0,
                "body_hits_added": 0,
                "body_scenes": [],
                "ai_plan": ({"title_add": ai_title_add, "picks": ai_picks,
                             "used_ai": bool((plan or {}).get("used_ai"))}
                            if plan else None),
                "backup": "",
                "duration": 0.0,
                "updated_at": _now(),
            })

        if not entries:
            raise ValueError("未选择任何有效条目。")

        pol = RatePolicy().as_dict()
        if policy:
            for k, v in policy.items():
                if k in pol and v is not None:
                    try:
                        pol[k] = type(pol[k])(v)
                    except Exception:
                        pass

        job = {
            "job_id": job_id,
            "brand": BRAND,
            "scope": "title_and_body" if want_body else "title_only",
            # 每篇固定 2 处：标题 1 处 + 正文 1 处（正文幂等，不重复植入）
            "features": {"title": want_title, "inject_body": want_body,
                         "ai_review": any(e.get("ai_plan") for e in entries)},
            "title_feature": want_title,
            "inject_body": want_body,
            "body_hits": 1 if want_body else 0,
            "per_article_hits": 2 if (want_title and want_body) else 1,
            "created_at": _now(),
            "updated_at": _now(),
            "finished_at": None,
            "created_by": created_by,
            "mode": mode if mode in ("local", "cloud") else "local",
            "status": "pending",
            "policy": pol,
            "worker": {"id": None, "claimed_at": None, "last_seen": None},
            "items": entries,
            "logs": [],
            "summary": {},
        }
        add_log(job, f"任务已创建，共 {len(entries)} 项；执行模式："
                     f"{'本地执行器' if job['mode'] == 'local' else '云端执行'}")
        if job["features"].get("ai_review"):
            add_log(job, "已附 AI 审核计划：由 DeepSeek 决定每篇加几处、加在哪里；"
                         "执行器将按计划写入（AI 不可用的条目按内置规则）。")
        if want_body:
            add_log(job, "范围声明：每篇改动 2 处——标题加入品牌词 1 处；"
                         "正文以署名式括注加入品牌词 1 处（不删改任何原有文字，可一键还原）")
        else:
            add_log(job, "范围声明：仅修改标题，正文保持原样（记录正文文本哈希以自证）")
        _recompute(job)
        _STORE["jobs"][job_id] = job
        _trim()
        _save()
        return job


def list_jobs(limit: int = 40) -> List[Dict[str, Any]]:
    _load()
    with _lock:
        jobs = list(_STORE.get("jobs", {}).values())
    jobs.sort(key=lambda j: j.get("created_at", 0), reverse=True)
    out = []
    for j in jobs[:limit]:
        out.append({
            "job_id": j["job_id"],
            "status": j.get("status"),
            "mode": j.get("mode"),
            "created_at": j.get("created_at"),
            "updated_at": j.get("updated_at"),
            "summary": j.get("summary", {}),
            "worker_id": (j.get("worker") or {}).get("id"),
            "scope": j.get("scope"),
            "brand": j.get("brand"),
            "last_log": (j.get("logs") or [{}])[-1].get("msg", ""),
        })
    return out


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    _load()
    with _lock:
        return _STORE.get("jobs", {}).get(job_id)


def claim_next_job(worker_id: str, mode: str = "local") -> Optional[Dict[str, Any]]:
    """A local executor pulls the oldest pending job."""
    _load()
    with _lock:
        cands = [j for j in _STORE.get("jobs", {}).values()
                 if j.get("status") == "pending" and j.get("mode") == mode]
        if not cands:
            return None
        cands.sort(key=lambda j: j.get("created_at", 0))
        job = cands[0]
        job["status"] = "claimed"
        job["worker"] = {"id": worker_id, "claimed_at": _now(),
                         "last_seen": _now()}
        job["updated_at"] = _now()
        add_log(job, f"已被本地执行器 {worker_id} 领取")
        _save()
        return job


def heartbeat(job_id: str, worker_id: str) -> bool:
    _load()
    with _lock:
        job = _STORE.get("jobs", {}).get(job_id)
        if not job:
            return False
        w = job.setdefault("worker", {})
        w["last_seen"] = _now()
        w["id"] = worker_id
        job["updated_at"] = _now()
        if job.get("status") == "claimed":
            job["status"] = "running"
            add_log(job, "执行器开始处理条目")
        _save()
        return True


def report_item(job_id: str, item_id: str, record: Dict[str, Any]) -> bool:
    """Record the outcome of one item reported by the executor."""
    _load()
    with _lock:
        job = _STORE.get("jobs", {}).get(job_id)
        if not job:
            return False
        for it in job.get("items", []):
            if it["id"] != item_id:
                continue
            for k in ("status", "message", "title_after", "title_before",
                      "body_sha256_before", "body_sha256_after",
                      "body_unchanged", "body_excerpt", "backup", "duration",
                      # 正文植入明细
                      "body_hits_before", "body_hits_after", "body_hits_added",
                      "body_scenes", "body_as_planned", "body_restorable"):
                if k in record:
                    it[k] = record[k]
            it["title_changed"] = bool(
                record.get("title_changed", it.get("title_after") != it.get("title_before")))
            it["updated_at"] = _now()
            break
        job["updated_at"] = _now()
        _recompute(job)
        if job.get("status") in ("claimed", "running") and \
                job.get("summary", {}).get("pending", 0) == 0:
            job["status"] = "done"
            job["finished_at"] = _now()
        _save()
        return True


def report_log(job_id: str, msg: str) -> bool:
    _load()
    with _lock:
        job = _STORE.get("jobs", {}).get(job_id)
        if not job:
            return False
        add_log(job, msg)
        job["updated_at"] = _now()
        _save()
        return True


def finish_job(job_id: str, summary: Optional[Dict[str, Any]] = None) -> bool:
    _load()
    with _lock:
        job = _STORE.get("jobs", {}).get(job_id)
        if not job:
            return False
        _recompute(job)
        job["status"] = "done" if job.get("summary", {}).get("failed", 0) == 0 else "failed"
        job["finished_at"] = _now()
        job["updated_at"] = _now()
        if summary:
            job["worker_summary"] = summary
        add_log(job, f"任务结束：成功 {job['summary'].get('done', 0)}，"
                     f"跳过 {job['summary'].get('skipped', 0)}，"
                     f"失败 {job['summary'].get('failed', 0)}")
        _save()
        return True


def cancel_job(job_id: str) -> bool:
    _load()
    with _lock:
        job = _STORE.get("jobs", {}).get(job_id)
        if not job:
            return False
        job["status"] = "cancelled"
        job["updated_at"] = _now()
        add_log(job, "任务已被取消")
        _save()
        return True


def reset_job(job_id: str) -> bool:
    """Put a job back to pending so it can be re-run (idempotent, safe)."""
    _load()
    with _lock:
        job = _STORE.get("jobs", {}).get(job_id)
        if not job:
            return False
        for it in job.get("items", []):
            if it.get("status") in ("failed", "saved_not_published"):
                it["status"] = "pending"
                it["message"] = ""
        job["status"] = "pending"
        job["finished_at"] = None
        job["worker"] = {"id": None, "claimed_at": None, "last_seen": None}
        job["updated_at"] = _now()
        _recompute(job)
        add_log(job, "任务已重置为待执行")
        _save()
        return True


def delete_job(job_id: str) -> bool:
    _load()
    with _lock:
        if job_id in _STORE.get("jobs", {}):
            del _STORE["jobs"][job_id]
            _save()
            return True
        return False


def stats() -> Dict[str, Any]:
    _load()
    with _lock:
        jobs = list(_STORE.get("jobs", {}).values())
    return {
        "jobs": len(jobs),
        "pending": sum(1 for j in jobs if j.get("status") == "pending"),
        "running": sum(1 for j in jobs if j.get("status") in ("claimed", "running")),
        "done": sum(1 for j in jobs if j.get("status") == "done"),
        "failed": sum(1 for j in jobs if j.get("status") == "failed"),
    }
