# -*- coding: utf-8 -*-
"""把 _patched_qingyi_page.py 上线：md5 漂移检查 -> 备份 -> 原子替换 -> 重启 -> 复核。"""
import subprocess, hashlib, sys, os
sys.stdout.reconfigure(encoding='utf-8')

HERE = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35"
SRC  = os.path.join(HERE, "_remote_qingyi_page.py")
DST  = os.path.join(HERE, "_patched_qingyi_page.py")
REMOTE_DIR = "/opt/zhihu-scraper/zhihu_scraper/app"
REMOTE = REMOTE_DIR + "/qingyi_page.py"

def md5(b): return hashlib.md5(b).hexdigest()

def ssh(cmd, stdin_data=None, timeout=180):
    if isinstance(stdin_data, str):
        stdin_data = stdin_data.encode("utf-8")
    r = subprocess.run(["ssh", "server3", cmd], input=stdin_data,
                       capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

local_src_md5 = md5(open(SRC, "rb").read())
local_new = open(DST, "rb").read()

# 1) 漂移检查：远端文件必须与本地基线一致
rc, out, err = ssh("md5sum " + REMOTE)
if rc != 0:
    print("SSH_FAIL", err[:400]); sys.exit(1)
remote_md5 = out.split()[0].strip()
print("remote md5 :", remote_md5)
print("base   md5 :", local_src_md5)
if remote_md5 != local_src_md5:
    print("DRIFT! 远端已变，停手，先重新拉取"); sys.exit(2)
print("no-drift OK")

# 2) 备份
rc, out, err = ssh("cp -a %s %s.bak-v132 && ls -l %s.bak-v132" % (REMOTE, REMOTE, REMOTE))
print("backup:", out.strip() or err.strip())

# 3) 上传到临时文件
rc, out, err = ssh("cat > /tmp/qy_page_v132.py", stdin_data=local_new)
if rc != 0:
    print("UPLOAD_FAIL", err[:400]); sys.exit(3)
rc, out, err = ssh("md5sum /tmp/qy_page_v132.py")
up_md5 = out.split()[0].strip() if out else ""
print("upload md5 :", up_md5, "expect", md5(local_new))
if up_md5 != md5(local_new):
    print("UPLOAD_CORRUPT"); sys.exit(4)

# 4) 远端语法检查 -> 原子替换 -> 重启
rc, out, err = ssh(
    "cd %s && python3 -m py_compile /tmp/qy_page_v132.py && echo COMPILE_OK "
    "&& mv /tmp/qy_page_v132.py %s && systemctl restart zhihu-scraper && echo RESTARTED"
    % (REMOTE_DIR, REMOTE))
print("deploy:", out.strip())
print("deploy_err:", err.strip()[:600])
if "COMPILE_OK" not in out or "RESTARTED" not in out:
    print("DEPLOY_FAIL"); sys.exit(5)

# 5) 复核：服务状态 / 远端 md5 / 标记 / 页面可访问
rc, out, _ = ssh("sleep 2; systemctl is-active zhihu-scraper; md5sum %s" % REMOTE)
print("post:", out.strip())
rc, out, _ = ssh("grep -c 'v13.2 · 引导与提示' %s; grep -c 'v13.2 · 引导与提示增强' %s; grep -c 'tour-dots' %s" % (REMOTE, REMOTE, REMOTE))
print("marks:", out.split())
rc, out, _ = ssh("curl -s -o /tmp/cons.html -w '%{http_code} %{size_download}' https://zh.samuraiguan.cloud/api/qy/console")
print("console:", out.strip())
rc, out, _ = ssh("grep -c 'tour-dots' /tmp/cons.html; grep -c 'qyToastDrain' /tmp/cons.html; grep -c 'clampTip' /tmp/cons.html; grep -c 'guanjun2026' /tmp/cons.html")
print("served html marks:", out.split())
print("ALL_DONE")
