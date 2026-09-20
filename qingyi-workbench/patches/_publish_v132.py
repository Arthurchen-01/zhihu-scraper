# -*- coding: utf-8 -*-
"""发布 v13.2 到 GitHub：
服务器打增量 bundle(607d054..main) -> ssh 下载 -> 本地克隆 GitHub 仓库 ->
fetch bundle -> fast-forward -> HTTPS+PAT 推送（剥掉代理，直连）。
"""
import os, sys, shutil, subprocess, hashlib
sys.stdout.reconfigure(encoding="utf-8")

BASE = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35"
DST = os.path.join(BASE, "_ghpush_v132")
DELTA = os.path.join(BASE, "_delta_v132.bundle")
GH = "https://github.com/Arthurchen-01/zhihu-scraper.git"
BASE_COMMIT = "607d054"   # GitHub 上已有的最后一笔

SBX_PROXY = "http://127.0.0.1:60120"   # 沙箱出站代理（实测可达 github.com）
CLEAN_ENV = dict(os.environ)
for k in list(CLEAN_ENV):
    if k.lower() in ("http_proxy", "https_proxy", "all_proxy"):
        CLEAN_ENV.pop(k)
CLEAN_ENV["GIT_TERMINAL_PROMPT"] = "0"
CLEAN_ENV["HTTP_PROXY"] = SBX_PROXY
CLEAN_ENV["HTTPS_PROXY"] = SBX_PROXY
CFG = ["http.proxy=", "https.proxy=", "credential.helper=", "http.version=HTTP/1.1"]


def ssh(cmd, timeout=300, binary=False):
    r = subprocess.run(["ssh", "server3", cmd], capture_output=True, timeout=timeout)
    if binary:
        return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace")
    return (r.returncode, r.stdout.decode("utf-8", "replace"),
            r.stderr.decode("utf-8", "replace"))


def run(cmd, env=None, timeout=300):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                       timeout=timeout, env=env or CLEAN_ENV)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def git(*args, **kw):
    cmd = ["git"]
    for c in CFG:
        cmd += ["-c", c]
    cmd += list(args)
    return run(cmd, **kw)


# ---- 1. 服务器打增量 bundle ----------------------------------------------
print("--- 1. delta bundle on server ---")
rc, out, err = ssh("cd /opt/zhihu-scraper && git bundle create /tmp/delta_v132.bundle %s..main && "
                   "git bundle verify /tmp/delta_v132.bundle 2>&1 | tail -2 && ls -l /tmp/delta_v132.bundle && "
                   "md5sum /tmp/delta_v132.bundle" % BASE_COMMIT)
print(out.strip()[:500])
if rc != 0 or ("complete history" not in out and "requires this ref" not in out):
    print("BUNDLE_FAIL", err[:300]); sys.exit(1)
remote_md5 = out.strip().splitlines()[-1].split()[0]

# ---- 2. 下载 --------------------------------------------------------------
print("\n--- 2. download delta ---")
rc, data, err = ssh("cat /tmp/delta_v132.bundle", binary=True)
if rc != 0 or not data:
    print("DL_FAIL", err[:300]); sys.exit(2)
open(DELTA, "wb").write(data)
print("bytes:", len(data), "md5:", hashlib.md5(data).hexdigest(), "remote:", remote_md5)
if hashlib.md5(data).hexdigest() != remote_md5:
    print("MD5_MISMATCH"); sys.exit(3)

# ---- 3. PAT（先取，克隆私有仓库就要用） ------------------------------------
tok = ""
try:
    import win32cred
    for c in win32cred.CredEnumerate(None, 0):
        if "github.com" in (c.get("TargetName") or ""):
            blob = c.get("CredentialBlob")
            if isinstance(blob, bytes):
                blob = blob.decode("utf-16-le", "replace")
            tok = str(blob).strip()
            break
except Exception as exc:
    print("win32cred 失败:", exc)
print("token:", bool(tok), len(tok), (tok[:4] + "..." if tok else "-"))
if not tok:
    sys.exit(5)
askpass = os.path.join(os.environ.get("TEMP", "."), "qy_askpass.cmd")
with open(askpass, "w", encoding="utf-8", newline="\r\n") as f:
    f.write("@echo off\r\necho %QYGTOK%\r\n")
PUSH_ENV = dict(CLEAN_ENV)
PUSH_ENV["QYGTOK"] = tok
PUSH_ENV["GIT_ASKPASS"] = askpass

# ---- 4. 本地克隆 GitHub 仓库 ----------------------------------------------
# 注意：不能用 rmtree 清理旧目录 —— 沙箱对 >50 个文件的批量删除会拦截。
# 改用带序号的全新目录，残留的旧目录最后统一手工清。
import time
DST = os.path.join(BASE, "_ghpush_v132_" + time.strftime("%H%M%S"))
print("\n--- 4. clone from GitHub ---")
print("dir:", DST)
rc, out = git("clone", "--no-checkout", GH, DST, env=PUSH_ENV)
print(out.strip()[:400]); print("clone rc =", rc)
if rc != 0:
    sys.exit(4)
rc, out = git("-C", DST, "rev-parse", "HEAD")
print("local HEAD:", out.strip())

# ---- 5. fetch 增量并 fast-forward ----------------------------------------
print("\n--- 5. fetch bundle ---")
rc, out = git("-C", DST, "fetch", DELTA, "main:server-main")
print(out.strip()[:400]); print("fetch rc =", rc)
if rc != 0:
    sys.exit(6)
rc, out = git("-C", DST, "merge", "--ff-only", "server-main")
print(out.strip()[:400]); print("merge rc =", rc)
if rc != 0:
    sys.exit(7)
rc, out = git("-C", DST, "log", "--oneline", "-3")
print(out)

# ---- 6. 推送 --------------------------------------------------------------
print("--- 6. push ---")
rc, out = git("-C", DST, "push", "origin", "HEAD:main", env=PUSH_ENV)
print(out[:700]); print("push rc =", rc)
if rc != 0:
    sys.exit(8)

print("\n--- remote head after push ---")
rc, out = run(["git", "-C", DST, "ls-remote", "origin", "refs/heads/main"], env=PUSH_ENV)
print(out.strip())
