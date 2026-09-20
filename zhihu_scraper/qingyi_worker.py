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

    def _req(self, method: str, path: str, quiet: bool = False,
             **kw) -> Optional[Dict[str, Any]]:
        url = f"{self.base}{path}"
        try:
            r = self.s.request(method, url, timeout=self.timeout, **kw)
        except Exception as exc:  # noqa: BLE001
            if not quiet:
                print(f"[!] 网络错误 {method} {path}: {exc}")
            return None
        if r.status_code == 401:
            print("[!] 云端拒绝：访问密钥无效。请用 --key 传入站点密钥。")
            return None
        if r.status_code >= 400:
            if not quiet:
                print(f"[!] {method} {path} -> HTTP {r.status_code} "
                      f"{r.text[:160]}")
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

    # ---- v5：云端预修改的取回 + 请云端独立复核 ---- #

    def payload(self, job_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """取回云端为该篇预算好的最终稿；没有缓存则返回 None（回退本地计算）。"""
        res = self._req(
            "GET", f"/api/qy/agent/payload/{job_id}/{item_id}", quiet=True)
        if not res or res.get("raw"):
            return None
        if res.get("title") is None or res.get("content") is None:
            return None
        return res

    def verify(self, job_id: str, cookie: str = "") -> Optional[Dict[str, Any]]:
        """请云端独立复核（云端自己去回读线上文章，不信本地自述）。"""
        return self._req("POST", f"/api/qy/verify/{job_id}",
                         json={"cookie": cookie or ""})

    def brief(self, job_id: str = "") -> Optional[Dict[str, Any]]:
        q = f"?job_id={job_id}" if job_id else ""
        return self._req("GET", f"/api/qy/agent/brief{q}", quiet=True)


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
            # v5：优先用云端已经算好的最终稿（本地只负责原样上传）。
            # 取不到云端缓存时才退回本地计算，保证老流程不被破坏。
            payload = self.cp.payload(job_id, it["id"])
            if payload:
                print(f"   云端方案: {str(payload.get('title', ''))[:70]}")
                rec = self.signer.apply_payload(it, payload, publish=True)
            else:
                rec = self.signer.process_title(
                    it, dry_run=False, publish=True,
                    inject_body=bool(job.get("inject_body")),
                    body_hits=int(job.get("body_hits") or 1),
                    body_anchors=[p.get("anchor")
                                  for p in (plan.get("picks") or [])
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

        # ---- v5：写入结束 → 请云端独立复核（云端重新回读线上文章做规则校验）----
        try:
            vres = self.cp.verify(job_id, self.signer.cookie)
            if vres and vres.get("ok"):
                vs = vres.get("summary") or {}
                print(f"\n[云端复核] 校验 {vs.get('checked', 0)} 篇 | "
                      f"通过 {vs.get('passed', 0)} | 不通过 {vs.get('failed', 0)}"
                      f" | 未校验 {vs.get('skipped', 0)}")
                for d in (vres.get("details") or []):
                    if d.get("verify") == "fail":
                        print(f"   ✗ {d.get('id')}："
                              f"{'；'.join(d.get('reasons') or [])}")
            elif vres:
                print(f"\n[云端复核] 未执行：{vres.get('note')}")
        except Exception as exc:  # noqa: BLE001
            print(f"[云端复核] 跳过（{exc}）")

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
    """读取凭证。读不到就返回空串（交给上层做自动读取兜底），不抛异常。

    两个历史坑：
      1. 部署包里的 cookie.txt 在没有凭证时只有注释行。旧实现把注释文本
         当成凭证返回，执行器于是拿着注释去请求知乎。
      2. 旧实现在这里 raise SystemExit，会把 --auto-cookie 的兜底路径
         整个挡住 —— 自动读取根本没机会执行。
    """
    if args.cookie:
        return args.cookie.strip()
    if args.cookie_file:
        p = Path(args.cookie_file)
        if not p.exists():
            return ""
        raw = p.read_text(encoding="utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("#"):
                continue
            if "z_c0=" in line:
                return line
        return ""
    return ""


def auto_detect_cookie():
    """从本机浏览器自动读取知乎登录凭证（用户零粘贴）。

    Windows: Edge / Chrome 的 Cookies 库（DPAPI + AES-GCM 解密）。
    macOS:   browser-cookie3（chrome/edge/firefox/safari 依次尝试）。
    返回 (cookie_str, source)；失败抛 RuntimeError（中文原因）。
    """
    import sys as _sys

    if _sys.platform == "win32":
        import base64 as _b64
        import json as _json
        import shutil as _shutil
        import sqlite3 as _sql
        import subprocess as _sub
        import tempfile as _tmpf
        from pathlib import Path as _P

        try:
            import win32crypt  # noqa: F401
            from Crypto.Cipher import AES  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "缺少解密组件（pywin32 / pycryptodome）。"
                "请在本目录运行：python -m pip install pywin32 pycryptodome")

        home = _P.home()
        browsers = [
            ("Edge", home / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"),
            ("Chrome", home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"),
        ]
        locked = []
        for b_name, user_data in browsers:
            if not user_data.exists():
                continue
            ls_path = user_data / "Local State"
            if not ls_path.exists():
                continue
            try:
                enc_key = _b64.b64decode(
                    _json.loads(ls_path.read_text(encoding="utf-8"))
                    ["os_crypt"]["encrypted_key"])[5:]
                key = win32crypt.CryptUnprotectData(enc_key, None, None, None, 0)[1]
            except Exception:
                continue
            for prof in ["Default"] + [f"Profile {i}" for i in range(1, 8)]:
                db = user_data / prof / "Network" / "Cookies"
                if not db.exists():
                    db = user_data / prof / "Cookies"
                if not db.exists():
                    continue
                tmp_path = None
                try:
                    with _tmpf.NamedTemporaryFile(delete=False,
                                                  suffix=".sqlite") as t:
                        tmp_path = _P(t.name)
                    try:
                        _shutil.copy2(db, tmp_path)
                    except PermissionError:
                        # 浏览器正在运行：用 Windows 自带 esentutl 复制锁定文件
                        r = _sub.run(["esentutl", "/y", str(db), "/d",
                                      str(tmp_path), "/o"],
                                     capture_output=True, timeout=60)
                        if r.returncode != 0 or not tmp_path.exists() \
                                or tmp_path.stat().st_size == 0:
                            raise
                    conn = _sql.connect(tmp_path)
                    rows = conn.execute(
                        "SELECT name, encrypted_value FROM cookies "
                        "WHERE host_key LIKE '%zhihu.com%'").fetchall()
                    conn.close()
                    cd = {}
                    for name, enc in rows:
                        try:
                            if enc[:3] in (b"v10", b"v11"):
                                nonce, ct, tag = enc[3:15], enc[15:-16], enc[-16:]
                                val = AES.new(key, AES.MODE_GCM, nonce=nonce
                                              ).decrypt_and_verify(ct, tag
                                              ).decode("utf-8", "ignore")
                            else:
                                val = win32crypt.CryptUnprotectData(
                                    enc, None, None, None, 0)[1].decode(
                                    "utf-8", "ignore")
                            if val:
                                cd[name] = val
                        except Exception:
                            pass
                    if "z_c0" in cd:
                        return ("; ".join(f"{k}={v}" for k, v in cd.items()),
                                f"{b_name}({prof})")
                except PermissionError:
                    locked.append(b_name)
                except Exception:
                    pass
                finally:
                    if tmp_path and tmp_path.exists():
                        try:
                            tmp_path.unlink()
                        except Exception:
                            pass
        if locked:
            raise RuntimeError(
                f"{'/'.join(sorted(set(locked)))} 正在运行并锁定了数据文件。"
                "请完全关闭浏览器后重试。")
        raise RuntimeError(
            "未在 Edge / Chrome 中找到知乎登录。请先用浏览器登录 zhihu.com 再重试。")

    if _sys.platform == "darwin":
        try:
            import browser_cookie3 as _bc3
        except ImportError:
            raise RuntimeError(
                "缺少 browser-cookie3。请运行：python3 -m pip install browser-cookie3")
        last_err = None
        for fn in ("chrome", "edge", "firefox", "safari"):
            try:
                jar = getattr(_bc3, fn)(domain_name=".zhihu.com")
                cd = {c.name: c.value for c in jar
                      if "zhihu" in (getattr(c, "domain", "") or "")}
                if "z_c0" in cd:
                    return ("; ".join(f"{k}={v}" for k, v in cd.items()), fn)
            except Exception as e:
                last_err = e
        raise RuntimeError(
            "未能从浏览器读取知乎登录（Mac 首次可能弹出钥匙串授权，请点「始终允许」）。"
            + (f"：{last_err}" if last_err else ""))

    raise RuntimeError("该系统暂不支持自动读取，请改用手动粘贴凭证。")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="清一新教育 · 本地执行器（标题 1 处 + 正文 1 处，每篇合计 2 处）")
    ap.add_argument("--server", default="https://zh.samuraiguan.cloud",
                    help="云端控制面地址")
    ap.add_argument("--key", default=None,
                    help="站点访问密钥（默认读环境变量 QY_API_KEY）")
    ap.add_argument("--cookie", default=None, help="知乎凭证字符串")
    ap.add_argument("--auto-cookie", action="store_true",
                    help="自动读取本机浏览器里的知乎登录（零粘贴；Windows 用 Edge/Chrome，"
                         "mac 用 browser-cookie3）")
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
    if getattr(args, "auto_cookie", False) and not cookie:
        print("凭证文件里没有可用登录态，改为自动读取本机浏览器登录…")
        for _attempt in range(1, 6):
            try:
                cookie, src = auto_detect_cookie()
                print(f"[OK] 已自动读取本机知乎登录（来源：{src}），无需粘贴。")
                break
            except Exception as exc:
                cookie = ""
                print(f"[!] 第 {_attempt}/5 次自动读取失败：{exc}")
                if _attempt >= 5:
                    break
                print("    请把 Edge / Chrome 的所有窗口全部关掉（不是最小化），"
                      "再按回车重试。")
                try:
                    _ans = input("    >>> 按回车重试（输入 q 退出）: ").strip().lower()
                except EOFError:
                    break
                if _ans == "q":
                    break
    if not cookie:
        raise SystemExit(
            "没有拿到知乎登录凭证，无法继续。\n"
            "  · 最省事的办法：双击「一键部署-Windows.bat」"
            "（Mac 用「一键部署-Mac.command」），它会自动读取浏览器里的登录并重试。\n"
            "  · 若提示浏览器锁定：把浏览器所有窗口全部关掉后再试一次。\n"
            "  · 也可以手动把知乎 Cookie 粘贴到 cookie.txt 里。")

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
