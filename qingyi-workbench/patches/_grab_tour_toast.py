# -*- coding: utf-8 -*-
"""把远端 qingyi_page.py 里 tour / toast 相关片段抓回本地分析。"""
import subprocess, re, io, sys
sys.stdout.reconfigure(encoding='utf-8')

PY = r"C:\Users\s990uma\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
REMOTE = "/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py"
LOCAL = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35\_remote_qingyi_page.py"

def ssh(cmd):
    r = subprocess.run(["ssh", "server3", cmd], capture_output=True)
    return r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

out, err = ssh("cat %s" % REMOTE)
if not out:
    print("FETCH_FAIL", err[:500]); sys.exit(1)
open(LOCAL, "w", encoding="utf-8", newline="").write(out)
print("bytes:", len(out.encode("utf-8")), "lines:", out.count("\n")+1)

# 统计 style 块
for m in re.finditer(r"<style[^>]*>", out):
    print("STYLE at", m.start(), out[m.start():m.start()+60].replace("\n"," "))
print("--- markers ---")
for kw in ["v13", "tour", "toast", "引导", "提示"]:
    hits = [m.start() for m in re.finditer(re.escape(kw), out)]
    print(kw, len(hits))
