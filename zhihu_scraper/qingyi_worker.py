#!/usr/bin/env python3
"""清一新教育 · 本地执行器 (Local Executor).

在「你自己的电脑」上运行，用本机网络身份完成知乎标题写入。

为什么需要它
------------
把 200+ 篇标题改写从机房 IP 上一次性打出去，是平台风控最敏感的形态。
云端控制面只做检索与编排；真正的写操作交给本执行器，走你日常使用的
网络与设备，行为特征与"本人手动逐篇修改"一致。

工作方式
--------
    1. 轮询云端控制面，领取待执行任务
    2. 逐篇：读取原标题 → 计算新标题 → 写入 → 发布 → 回读校验
    3. 每篇结束立即上报云端（进度条即时更新）
    4. 全程记录正文文本哈希，作为"正文零修改"的证据

用法
----
    python -m zhihu_scraper.qingyi_worker \
        --server https://zh.samuraiguan.cloud \
        --key <站点访问密钥> \
        --cookie-file cookie.txt \
        --once

也可常驻运行（去掉 --once），它会自己等任务。
"""

from __future__ import annotations

import argparse
import json
import random
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .qingyi import (
    BRAND, QingyiTitleSigner, RateGovernor, RatePolicy,
)

WORKER_VERSION = "1.0.0"
_STOP = False


def _sig(_signum, _frame):  # noqa: ANN001
    global _STOP
    _STOP = True
    print("\n[!] 收到中断信号，将在当前条目完成后停止。")


signal.signal(signal.SIGINT, _sig)
try:
    signal.signal(signal.SIGTERM, _sig)
except Exception:
    pass


# --------------------------------------------------------------------------- #
# Control-plane client
# --------------------------------------------------------------------------- #

class ControlPlane:
    """Thin client for the cloud control plane (read-mostly)."""

    def __init__(self, server: str, api_key: str, timeout: int = 30) -> None:
        self.base = server.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"qingyi-local-executor/{WORKER_VERSION}",
        })
        self.timeout = timeout

    def _req(self, method: str, path: str, **kw) -> Optional[Dict[str, Any]]:
        url = f"{self.base}{path}"
        try:
            r = self.s.request(method, url, timeout=self.timeout, **kw)
        except Exception as exc:  # noqa: BLE001
            print(f"[!] 网络错误 {method} {path}: {exc}")
            return None
        if r.status_code == 401:
            print("[!] 云端拒绝：访问密钥无效。请用 --key 传入站点密钥。")
            return None
        if r.status_code >= 400:
            print(f"[!] {method} {path} -> HTTP {r.status_code} {r.text[:160]}")
            return None
        try:
            return r.json()
        except Exception:
            return {"raw": r.text[:400]}

    def claim(self, worker_id: str, mode: str = "local") -> Optional[Dict[str, Any]]:
        res = self._req("POST", "/api/qy/worker/claim",
                        json={"worker_id": worker_id, "mode": mode})
        if not res:
            return None
        return res.get("job")

    def heartbeat(self, job_id: str, worker_id: str) -> None:
        self._req("POST", "/api/qy/worker/heartbeat",
                  json={"job_id": job_id, "worker_id": worker_id})

    def report_item(self, job_id: str, record: Dict[str, Any]) -> None:
        self._req("POST", "/api/qy/worker/report",
                  json={"job_id": job_id, "record": record})

    def log(self, job_id: str, msg: str) -> None:
        self._req("POST", "/api/qy/worker/log",
                  json={"job_id": job_id, "message": msg})

    def finish(self, job_id: str, summary: Dict[str, Any]) -> None:
        self._req("POST", "/api/qy/worker/finish",
                  json={"job_id": job_id, "summary": summary})


# --------------------------------------------------------------------------- #
# Executor
# --------------------------------------------------------------------------- #

class LocalExecutor:
    def __init__(self, cp: ControlPlane, cookie: str,
                 backup_dir: Optional[Path] = None,
                 policy: Optional[RatePolicy] = None,
                 daily_path: Optional[Path] = None) -> None:
        self.cp = cp
        self.worker_id = self._make_worker_id()
        self.policy = policy or RatePolicy()
        self.signer = QingyiTitleSigner(
            cookie=cookie,
            backup_dir=backup_dir or Path("data/qyedu_backup"),
            policy=self.policy,
        )
        self.governor = RateGovernor(self.policy, daily_path=daily_path)

    @staticmethod
    def _make_worker_id() -> str:
        import platform
        import socket
        host = "unknown"
        try:
            host = socket.gethostname()[:18]
        except Exception:
            pass
        return f"{host}-{platform.system().lower()}-{random.randint(1000, 9999)}"

    # ---------------- preflight ---------------- #

    def preflight(self) -> Dict[str, Any]:
        print("=" * 68)
        print("本地执行器启动前自检")
        print("=" * 68)
        print(f"  执行器 ID : {self.worker_id}")
        info = self.signer.verify()
        print(f"  账号      : {info.get('name')} ({info.get('url_token')})")
        print(f"  文章 / 想法: {info.get('articles_count')} / {info.get('pins_count')}")
        print(f"  备份目录  : {self.signer.backup_dir}")
        print(f"  每日限额  : {self.governor.daily.describe()}"
              f"（上限 {self.policy.per_day} 篇/天，到量自动停止）")
        print("=" * 68)
        return info

    # ---------------- main loop ---------------- #

    def run_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        job_id = job["job_id"]
        items = job.get("items", [])
        todo = [it for it in items
                if it.get("status") == "pending" and it.get("type") == "article"]
        others = [it for it in items if it.get("type") != "article"]

        print(f"[任务] {job_id} | 待处理 {len(todo)} 篇"
              f"{f'（另有 {len(others)} 项非文章类型，跳过）' if others else ''}")
        body_note = ("每篇 2 处：标题 1 处 + 正文 1 处"
                     if job.get("inject_body") else "仅标题，正文不动")
        self.cp.log(job_id, f"本地执行器 {self.worker_id} 已开始，"
                            f"待处理 {len(todo)} 篇（{body_note}）")

        for it in others:
            rec = {
                "id": it["id"], "status": "unsupported",
                "message": it.get("kind_label", "内容") + " 不支持标题注入"
                           + ("（回答标题由问题决定）" if it.get("type") == "answer"
                              else "（想法无独立标题）"),
                "title_before": it.get("title_before", ""),
                "title_after": it.get("title_before", ""),
                "title_changed": False,
            }
            self.cp.report_item(job_id, rec)

        ok = skipped = failed = 0
        started = time.time()

        for idx, it in enumerate(todo, 1):
            if _STOP:
                self.cp.log(job_id, "收到中断信号，停止后续处理")
                break

            # ---- 每日总量闸门（防风控主闸） ----
            # 到量即停，剩余条目留到明天继续；不做任何"偷偷绕过"的处理。
            if self.governor.daily.exhausted():
                msg = (f"已达每日上限（{self.policy.per_day} 篇/天），"
                       f"为保护账号本轮停止；剩余 "
                       f"{len(todo) - idx + 1} 篇请明天再执行。")
                print(f"[日限] {msg}")
                self.cp.log(job_id, msg)
                break

            # rolling-hour quota
            wait_h = self.governor.hourly_wait()
            if wait_h > 0:
                print(f"[配额] 已达到每小时 {self.policy.per_hour} 篇上限，"
                      f"等待 {wait_h / 60:.1f} 分钟后继续…")
                self.cp.log(job_id,
                            f"达到每小时上限，等待 {wait_h / 60:.1f} 分钟")
                end = time.time() + wait_h
                while time.time() < end and not _STOP:
                    time.sleep(min(15, end - time.time()))
                    self.cp.heartbeat(job_id, self.worker_id)
                if _STOP:
                    break

            self.cp.heartbeat(job_id, self.worker_id)
            self.signer.rotate_identity()

            print(f"\n[{idx}/{len(todo)}] {it['id']}")
            print(f"   原标题: {it.get('title_before', '')[:70]}")
            print(f"   目标  : {it.get('title_after', '')[:70]}")

            item_started = time.time()
            plan = it.get("ai_plan") or {}
            rec = self.signer.process_title(
                it, dry_run=False, publish=True,
                inject_body=bool(job.get("inject_body")),
                body_hits=int(job.get("body_hits") or 1),
                body_anchors=[p.get("anchor") for p in (plan.get("picks") or [])
                              if p.get("anchor")],
                title_add=(None if plan.get("title_add") is None
                           else bool(plan.get("title_add"))))
            rec["id"] = it["id"]

            if rec.get("status") == "done":
                ok += 1
                self.governor.note_success()
                if rec.get("body_unchanged") is None:
                    flag = f"正文植入 {rec.get('body_hits_added', 0)} 处"
                elif rec.get("body_unchanged"):
                    flag = "正文哈希一致 ✓"
                else:
                    flag = "正文哈希待复核"
                print(f"   → 成功：{rec.get('message')} [{flag}]"
                      f" ({rec.get('duration')}s)")
            elif rec.get("status") == "skipped":
                skipped += 1
                self.governor.note_success()
                print(f"   → 跳过：{rec.get('message')}")
            else:
                failed += 1
                n = self.governor.note_failure()
                print(f"   → 失败：{rec.get('message')}")
                if self.governor.should_abort():
                    print(f"[!] 连续 {n} 次失败，出于账号安全考虑立即中止。")
                    self.cp.log(job_id,
                                f"连续 {n} 次失败，已自动中止以保护账号")
                    self.cp.report_item(job_id, rec)
                    break
                bf = self.governor.backoff_seconds()
                print(f"   退避等待 {bf:.0f} 秒后重试下一篇…")
                time.sleep(bf)

            self.cp.report_item(job_id, rec)

            if idx < len(todo) and not _STOP:
                gap = self.governor.next_gap()
                nxt = time.time() + gap
                print(f"   … 自然间隔 {gap:.0f} 秒")
                while time.time() < nxt and not _STOP:
                    time.sleep(min(10, max(0.5, nxt - time.time())))
                    self.cp.heartbeat(job_id, self.worker_id)

        summary = {
            "worker_id": self.worker_id,
            "ok": ok, "skipped": skipped, "failed": failed,
            "elapsed": round(time.time() - started, 1),
            "interrupted": _STOP,
            "daily": {
                "limit": self.policy.per_day,
                "used": self.governor.daily._used,
                "remaining": self.governor.daily.remaining(),
                "text": self.governor.daily.describe(),
            },
        }
        self.cp.finish(job_id, summary)
        print("\n" + "=" * 68)
        print(f"[任务完成] {job_id}")
        print(f"  成功 {ok} | 跳过 {skipped} | 失败 {failed} | "
              f"耗时 {summary['elapsed']}s")
        print("=" * 68)
        return summary

    # ---------------- polling ---------------- #

    def serve(self, once: bool = False, poll_interval: float = 20.0) -> None:
        self.preflight()
        print("[就绪] 正在等待云端任务…" if not once else "[单次] 只执行一轮")
        while not _STOP:
            job = self.cp.claim(self.worker_id, mode="local")
            if job:
                self.run_job(job)
                if once:
                    return
                continue
            if once:
                print("当前没有待执行任务。")
                return
            for _ in range(int(poll_interval * 2)):
                if _STOP:
                    return
                time.sleep(0.5)
        print("执行器已退出。")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _read_cookie(args: argparse.Namespace) -> str:
    if args.cookie:
        return args.cookie.strip()
    if args.cookie_file:
        p = Path(args.cookie_file)
        if not p.exists():
            raise SystemExit(f"凭证文件不存在：{p}")
        raw = p.read_text(encoding="utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if "_xsrf=" in line and "z_c0=" in line:
                return line
        return raw.strip()
    raise SystemExit("请通过 --cookie 或 --cookie-file 提供知乎登录凭证。")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="清一新教育 · 本地执行器（标题 1 处 + 正文 1 处，每篇合计 2 处）")
    ap.add_argument("--server", default="https://zh.samuraiguan.cloud",
                    help="云端控制面地址")
    ap.add_argument("--key", default=None,
                    help="站点访问密钥（默认读环境变量 QY_API_KEY）")
    ap.add_argument("--cookie", default=None, help="知乎凭证字符串")
    ap.add_argument("--cookie-file", default=None,
                    help="含知乎凭证的文件路径")
    ap.add_argument("--backup-dir", default=None, help="备份目录")
    ap.add_argument("--once", action="store_true", help="只执行一轮后退出")
    ap.add_argument("--poll", type=float, default=20.0, help="轮询间隔（秒）")
    ap.add_argument("--gap-min", type=float, default=None, help="最小间隔秒数")
    ap.add_argument("--gap-max", type=float, default=None, help="最大间隔秒数")
    ap.add_argument("--per-hour", type=int, default=None, help="每小时上限")
    ap.add_argument("--per-day", type=int, default=None,
                    help="每日总量上限（默认 120，防风控主闸；0 表示不限）")
    ap.add_argument("--daily-file", default=None,
                    help="每日用量计数文件（默认 data/qy_daily_quota.json）")
    ap.add_argument("--max-items", type=int, default=None, help="本次最多处理篇数")
    ap.add_argument("--list-only", action="store_true",
                    help="只做资产枚举与预演，不写入")
    args = ap.parse_args(argv)

    import os
    api_key = args.key or os.environ.get("QY_API_KEY") or ""
    if not api_key:
        raise SystemExit("请通过 --key 或环境变量 QY_API_KEY 提供站点访问密钥。")

    cookie = _read_cookie(args)

    pol = RatePolicy()
    if args.gap_min is not None:
        pol.gap_min = args.gap_min
    if args.gap_max is not None:
        pol.gap_max = args.gap_max
    if args.per_hour is not None:
        pol.per_hour = args.per_hour
    if args.per_day is not None:
        pol.per_day = args.per_day
    if getattr(args, "max_items", None):
        pol.max_task_items = args.max_items

    cp = ControlPlane(args.server, api_key)
    ex = LocalExecutor(cp, cookie,
                       backup_dir=Path(args.backup_dir) if args.backup_dir else None,
                       policy=pol,
                       daily_path=(Path(args.daily_file)
                                   if getattr(args, "daily_file", None) else None))

    if args.list_only:
        info = ex.preflight()
        arts = ex.signer.list_articles()
        pend = [a for a in arts if not a["has_brand"]]
        print(f"文章合计 {len(arts)}，其中待注入 {len(pend)} 篇")
        for a in pend[:15]:
            print(f"   · {a['id']} | {a['title'][:64]}")
        if len(pend) > 15:
            print(f"   … 其余 {len(pend) - 15} 篇")
        print("\n提示：这是只读预演，未做任何修改。")
        return 0

    ex.serve(once=args.once, poll_interval=args.poll)
    return 0


if __name__ == "__main__":
    sys.exit(main())
