#!/usr/bin/env python3
"""创建 1 篇的最小任务，用于跑通「云端编排 → 本地写入 → 回执」全链路。"""
import json
import sys
import urllib.request

SERVER = "https://zh.samuraiguan.cloud"
KEY = "guanjun2026"
COOKIE_FILE = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35\qy_local\cookie.txt"

cookie = open(COOKIE_FILE, encoding="utf-8").read().strip()


def post(path, payload):
    req = urllib.request.Request(
        SERVER + path,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + KEY,
            "Content-Type": "application/json",
            # 必须带 UA：python-urllib 的默认 UA 会被前置防护直接 403
            "User-Agent": "qingyi-local-executor/1.0.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


# 1) 只读枚举
insp = post("/api/qy/inspect", {"cookie": cookie})
items = insp.get("items", [])
print("枚举统计:", json.dumps(insp.get("stats"), ensure_ascii=False))

# 2) 挑一篇「标题尚未含品牌词」的文章
target = None
for a in items:
    if a.get("type") != "article":
        continue
    t = a.get("title") or ""
    if "清一新教育" not in t:
        target = a
        break
if not target:
    print("没有待处理文章")
    sys.exit(0)

print("选中:", target.get("id"), "|", target.get("title"))

# 3) 建任务（1 篇）
job = post("/api/qy/jobs", {
    "cookie": cookie,
    "items": [{"id": target["id"], "type": "article", "title": target.get("title")}],
    "mode": "local",
    "features": {"title": True},
})
print("建任务:", json.dumps(job, ensure_ascii=False)[:400])
