import base64
import tarfile
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

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

with tarfile.open(bundle_path, "w:gz") as tar:
    for f in files_to_pack:
        fp = LOCAL_DIR / f
        if fp.exists():
            tar.add(str(fp), arcname=f)

b64_content = base64.b64encode(bundle_path.read_bytes()).decode("ascii")

# Create a self-contained 1-click script for remote server
remote_script = f"""#!/bin/bash
set -e

echo "🚀 [1/4] 创建并进入 /opt/zhihu-monitor 目录..."
mkdir -p /opt/zhihu-monitor /opt/zhihu-monitor/data /opt/zhihu-monitor/logs /opt/zhihu-monitor/outputs
cd /opt/zhihu-monitor

echo "📦 [2/4] 解压全量代码套件..."
cat << 'EOF' | base64 -d > bundle.tar.gz
{b64_content}
EOF

tar -xzf bundle.tar.gz
rm -f bundle.tar.gz
chmod +x install_cloud.sh

echo "⚙️ [3/4] 初始化 Python 虚拟环境与安装依赖..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install requests curl-cffi beautifulsoup4 lxml pandas openpyxl fastapi uvicorn -q

echo "🛡️ [4/4] 注册并启动 Systemd 7x24h 守护服务..."
cp zhihu-monitor.service /etc/systemd/system/zhihu-monitor.service
cp zhihu-web.service /etc/systemd/system/zhihu-web.service

systemctl daemon-reload
systemctl enable --now zhihu-monitor.service
systemctl enable --now zhihu-web.service

systemctl restart zhihu-monitor.service
systemctl restart zhihu-web.service

echo ""
echo "======================================================================"
echo "🎉 部署大功告成！知乎全网持续搜索守护进程已在后台 7x24 小时运行！"
echo "🌐 实时 Web 大盘访问地址: http://38.76.206.7:8770"
echo "📊 查看后台运行日志: journalctl -u zhihu-monitor -f"
echo "======================================================================"
"""

out_script = LOCAL_DIR / "deploy_on_server.sh"
out_script.write_text(remote_script, encoding="utf-8")
print(f"✅ 生成独立部署脚本: {out_script} (大小: {out_script.stat().st_size / 1024:.1f} KB)")
