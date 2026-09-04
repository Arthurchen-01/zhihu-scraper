import requests
import json
import tarfile
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

SUPABASE_URL = "https://gvdkkvxkqadplvvlpmiw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd2ZGtrdnhrcWFkcGx2dmxwbWl3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTE0NDYzNCwiZXhwIjoyMDkwNzIwNjM0fQ.HQ-aw4S3wjV3dK8KWmpK0ErHBj0_KAQZhQkYIf4gHHM"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

LOCAL_DIR = Path(r"C:\Users\25472\Desktop\AI brain storming\工具栏\zhihu-black")
bundle_path = LOCAL_DIR / "zhihu_bundle.tar.gz"

files_to_pack = [
    "cloud_daemon.py",
    "cloud_web_server.py",
    "zhihu_client.py",
    "nlp_classifier.py",
    "author_tracer.py",
    "ai_deep_audit.py",
    "reporter.py",
    "config.json",
    "zhihu-monitor.service",
    "zhihu-web.service",
    "install_cloud.sh"
]

# Ensure all text files inside bundle have LF line endings
for f in files_to_pack:
    fp = LOCAL_DIR / f
    if fp.exists() and f.endswith((".py", ".sh", ".service", ".json")):
        content = fp.read_text(encoding="utf-8").replace("\r\n", "\n")
        fp.write_bytes(content.encode("utf-8"))

with tarfile.open(bundle_path, "w:gz") as tar:
    for f in files_to_pack:
        fp = LOCAL_DIR / f
        if fp.exists():
            tar.add(str(fp), arcname=f)

# 1. Upload bundle.tar.gz
up_headers_bin = {**headers, "Content-Type": "application/gzip", "x-upsert": "true"}
r_bin = requests.post(f"{SUPABASE_URL}/storage/v1/object/deploy/bundle.tar.gz", headers=up_headers_bin, data=bundle_path.read_bytes())
print("Bundle upload status:", r_bin.status_code)

bundle_url = f"{SUPABASE_URL}/storage/v1/object/public/deploy/bundle.tar.gz"

# 2. Write clean installer with pure LF
installer_lines = [
    "#!/bin/bash",
    "set -e",
    "",
    "echo \"🚀 [1/4] 创建并进入 /opt/zhihu-monitor 目录...\"",
    "mkdir -p /opt/zhihu-monitor /opt/zhihu-monitor/data /opt/zhihu-monitor/logs /opt/zhihu-monitor/outputs",
    "cd /opt/zhihu-monitor",
    "",
    "echo \"📦 [2/4] 下载全量代码套件...\"",
    f"curl -sSL -o bundle.tar.gz {bundle_url}",
    "tar -xzf bundle.tar.gz",
    "rm -f bundle.tar.gz",
    "chmod +x install_cloud.sh",
    "",
    "echo \"⚙️ [3/4] 初始化 Python 虚拟环境并安装依赖...\"",
    "if [ ! -d \".venv\" ]; then",
    "    python3 -m venv .venv",
    "fi",
    ".venv/bin/pip install --upgrade pip -q",
    ".venv/bin/pip install requests curl-cffi beautifulsoup4 lxml pandas openpyxl fastapi uvicorn -q",
    "",
    "echo \"🛡️ [4/4] 注册并启动 Systemd 7x24h 守护服务...\"",
    "cp zhihu-monitor.service /etc/systemd/system/zhihu-monitor.service",
    "cp zhihu-web.service /etc/systemd/system/zhihu-web.service",
    "",
    "systemctl daemon-reload",
    "systemctl enable --now zhihu-monitor.service",
    "systemctl enable --now zhihu-web.service",
    "",
    "systemctl restart zhihu-monitor.service",
    "systemctl restart zhihu-web.service",
    "",
    "echo \"\"",
    "echo \"======================================================================\"",
    "echo \"🎉 部署大功告成！知乎全网持续搜索守护进程已在后台 7x24 小时运行！\"",
    "echo \"🌐 实时 Web 大盘访问地址: http://38.76.206.7:8770\"",
    "echo \"📊 查看后台运行日志: journalctl -u zhihu-monitor -f\"",
    "echo \"======================================================================\"",
    ""
]

clean_installer = "\n".join(installer_lines)

# Upload run.sh with pure LF
up_headers_sh = {**headers, "Content-Type": "text/x-shellscript", "x-upsert": "true"}
r_sh = requests.post(f"{SUPABASE_URL}/storage/v1/object/deploy/run.sh", headers=up_headers_sh, data=clean_installer.encode("utf-8"))
print("Installer upload status:", r_sh.status_code)

# Verify
public_url = f"{SUPABASE_URL}/storage/v1/object/public/deploy/run.sh"
r_check = requests.get(public_url)
print("Has CR in script:", b"\r" in r_check.content)
print("Length:", len(r_check.content))
