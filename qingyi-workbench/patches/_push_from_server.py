# -*- coding: utf-8 -*-
"""从服务器直接推 GitHub：
本地读 qy_local/_tok.tmp 的 PAT -> 传到 /tmp/qy_tok (600) ->
服务器 askpass 一次性推送 -> 删除服务器上的凭证痕迹 -> 验证远端 HEAD。
"""
import os, sys, subprocess, hashlib
sys.stdout.reconfigure(encoding="utf-8")

BASE = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35"
TOK_LOCAL = os.path.join(BASE, "qy_local", "_tok.tmp")
REPO = "/opt/zhihu-scraper"
GH = "https://github.com/Arthurchen-01/zhihu-scraper.git"


def ssh(cmd, inp=None, timeout=300, binary=False):
    if isinstance(inp, str):
        inp = inp.encode("utf-8")
    r = subprocess.run(["ssh", "server3", cmd], input=inp,
                       capture_output=True, timeout=timeout)
    if binary:
        return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace")
    return (r.returncode, r.stdout.decode("utf-8", "replace"),
            r.stderr.decode("utf-8", "replace"))


# ---- 1. 本地拿 PAT --------------------------------------------------------
tok = ""
if os.path.exists(TOK_LOCAL):
    tok = open(TOK_LOCAL, "r", encoding="ascii").read().strip()
if not tok:
    print("本地无 _tok.tmp，重新从凭据管理器提取")
    r = subprocess.run([sys.executable, os.path.join(BASE, "qy_gettok.py")],
                       capture_output=True, text=True, errors="replace", timeout=60)
    print(r.stdout, r.stderr)
    tok = open(TOK_LOCAL, "r", encoding="ascii").read().strip()
print("token:", bool(tok), len(tok), (tok[:4] + "..." if tok else "-"))
if not tok:
    sys.exit(1)

# ---- 2. 上传到服务器临时文件 ----------------------------------------------
rc, out, err = ssh("umask 077 && cat > /tmp/qy_tok", inp=tok, timeout=60)
rc, out, err = ssh("chmod 600 /tmp/qy_tok && md5sum /tmp/qy_tok && wc -c < /tmp/qy_tok")
print("server side:", out.strip(), "| local md5:", hashlib.md5(tok.encode()).hexdigest())
if hashlib.md5(tok.encode()).hexdigest() not in out:
    print("TOK_UPLOAD_MISMATCH"); sys.exit(2)

# ---- 3. 服务器 askpass + 推送 --------------------------------------------
rc, out, err = ssh(
    "printf '#!/bin/sh\\necho \"$(cat /tmp/qy_tok)\"\\n' > /tmp/qy_askpass.sh && "
    "chmod 700 /tmp/qy_askpass.sh && cd %s && "
    "GIT_ASKPASS=/tmp/qy_askpass.sh GIT_TERMINAL_PROMPT=0 git "
    "-c credential.helper= -c http.version=HTTP/1.1 "
    "push origin HEAD:main 2>&1 | tail -5; echo PUSH_RC=$?; "
    "rm -f /tmp/qy_askpass.sh /tmp/qy_tok; echo CLEANED" % REPO, timeout=300)
print(out.strip())
if "PUSH_RC=0" not in out or "CLEANED" not in out:
    print("PUSH_FAIL", err[:300]); sys.exit(3)

# ---- 4. 验证 --------------------------------------------------------------
rc, out, err = ssh("ls /tmp/qy_tok /tmp/qy_askpass.sh 2>&1; cd %s && git ls-remote origin refs/heads/main 2>&1 | tail -1" % REPO, timeout=120)
print("verify:", out.strip()[:300])
print("DONE")
