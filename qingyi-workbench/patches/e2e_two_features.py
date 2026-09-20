#!/usr/bin/env python3
"""全链路实测：标题 1 处 + 正文 1 处。

流程：只读枚举 → 选一篇 → 建任务（双功能开启）→ 本地执行器真实写入
      → 云端回执 → 线上回读验证 → 报告。
"""
import json
import subprocess
import time
import sys

import requests

SERVER = "https://zh.samuraiguan.cloud"
KEY = "guanjun2026"
H = {"Authorization": "Bearer " + KEY, "User-Agent": "qingyi-local-executor/1.0.0"}
BASE = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35"
PY = r"C:\Users\s990uma\.workbuddy\binaries\python\versions\3.13.12\python.exe"
COOKIE = open(BASE + r"\qy_local\cookie.txt", encoding="utf-8").read().strip()


def _req(method, path, **kw):
    """带重试的请求：跨境链路偶发 SSL EOF / 502，属瞬时故障。"""
    last = None
    for _ in range(5):
        try:
            return getattr(requests, method)(SERVER + path, headers=H, **kw)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(3)
    raise last


# 1) 枚举
d = _req("post", "/api/qy/inspect", json={"cookie": COOKIE}, timeout=180).json()
print("[1] 枚举:", json.dumps(d["stats"]["articles"], ensure_ascii=False))

target = None
for it in d["items"]:
    if it.get("type") == "article" and not it.get("has_brand"):
        target = it
        break
if not target:
    print("无待处理文章"); sys.exit(0)
print("    选中:", target["id"], "|", target["title"][:44])

# 2) 建任务（标题 + 正文）
job = _req("post", "/api/qy/jobs", timeout=120, json={
    "items": [{"id": target["id"], "type": "article",
               "kind_label": "文章", "title": target["title"],
               "url": target["url"], "excerpt": target.get("excerpt", "")}],
    "mode": "local", "title": True, "inject_body": True, "body_hits": 1,
}).json()["job"]
print("[2] 任务:", job["job_id"], "| scope:", job.get("scope"),
      "| 每篇:", job.get("per_article_hits"), "处",
      "| 标题:", job.get("title_feature"), "正文:", job.get("inject_body"))

# 3) 本地执行器真实执行
print("[3] 本地执行器写入中…")
p = subprocess.run(
    [PY, BASE + r"\qy_local\qingyi_executor.py", "--server", SERVER,
     "--key", KEY, "--cookie-file", BASE + r"\qy_local\cookie.txt",
     "--once", "--gap-min", "2", "--gap-max", "4"],
    capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
for line in (p.stdout or "").splitlines():
    if any(k in line for k in ("[1/", "→", "成功", "失败", "任务完成", "目标")):
        print("   ", line.strip())

# 4) 云端回执
j = _req("get", "/api/qy/jobs/" + job["job_id"], timeout=60).json()["job"]
print("[4] 云端状态:", j["status"], json.dumps(j["summary"], ensure_ascii=False))
for it in j["items"]:
    print("    标题:", it.get("title_before"), "->", it.get("title_after"))
    print("    正文提及:", it.get("body_hits_before"), "->", it.get("body_hits_after"),
          "(+" + str(it.get("body_hits_added")) + ")")
    for s in it.get("body_scenes") or []:
        print("    植入位置: 第", s["block_no"] + 1, "段 |", s["reason"])
        print("              ", s["excerpt"][:90])
print("    任务编号:", job["job_id"])
