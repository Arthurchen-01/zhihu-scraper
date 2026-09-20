# -*- coding: utf-8 -*-
"""盘点：qy_local 里哪些必须同步、哪些绝不能传、体积多少。"""
import io
import os
import re

BASE = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35\qy_local"

def walk(root):
    tot = 0
    items = []
    for dp, dns, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            items.append((os.path.relpath(p, BASE), sz))
            tot += sz
    return items, tot

items, tot = walk(BASE)
print("qy_local 合计 %.1f MB / %d 个文件" % (tot / 1048576.0, len(items)))

# 顶层分组
groups = {}
for rel, sz in items:
    top = rel.split(os.sep)[0]
    if os.sep not in rel:
        top = "(根目录文件)"
    groups[top] = groups.get(top, [0, 0])
    groups[top][0] += sz
    groups[top][1] += 1
print("\n--- 按顶层分组 ---")
for k, (s, n) in sorted(groups.items(), key=lambda x: -x[1][0]):
    print("  %-28s %8.2f MB  %4d 个" % (k, s / 1048576.0, n))

# shots 明细
shots = [(r, s) for r, s in items if r.startswith("shots" + os.sep)]
print("\n--- shots 合计 %.2f MB / %d 张 ---" % (sum(s for _, s in shots) / 1048576.0, len(shots)))

# 报告引用了哪些
rep = os.path.join(BASE, "验收报告.html")
html = io.open(rep, encoding="utf-8").read()
used = sorted(set(re.findall(r'src="(shots/[^"]+)"', html)))
print("报告引用 %d 张：" % len(used))
used_sz = 0
for u in used:
    p = os.path.join(BASE, u.replace("/", os.sep))
    sz = os.path.getsize(p) if os.path.exists(p) else 0
    used_sz += sz
    print("  %-34s %7.0f KB %s" % (u, sz / 1024.0, "" if sz else "<< 缺失"))
print("引用图片合计 %.2f MB" % (used_sz / 1048576.0))

# 敏感文件扫描
print("\n--- 敏感内容扫描（整个 qy_local）---")
PAT = {
    "站点密钥 guanjun2026": re.compile(r"guanjun2026"),
    "知乎 Cookie": re.compile(r"z_c0|_xsrf|d_c0=|SESSIONID"),
    "DeepSeek Key": re.compile(r"sk-[A-Za-z0-9]{16,}"),
    "GitHub Token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
}
TEXT_EXT = {".py", ".md", ".html", ".txt", ".json", ".js", ".css", ".bat", ".sh", ".yaml", ".yml", ".ini", ".cfg"}
for name, rx in PAT.items():
    hits = []
    for rel, sz in items:
        if os.path.splitext(rel)[1].lower() not in TEXT_EXT:
            continue
        try:
            t = io.open(os.path.join(BASE, rel), encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if rx.search(t):
            hits.append(rel)
    print("  %-24s -> %s" % (name, ", ".join(hits[:8]) if hits else "无"))
