"""Deploy Zhihu Continuous Monitor to Cloud Server (38.76.206.7)
"""

from __future__ import annotations

import os
import sys
import tarfile
import time
from pathlib import Path
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

SERVER_IP = "38.76.206.7"
SERVER_PORT = 22
SERVER_USER = "root"
SERVER_PASS = "39TF6xMH52yC"
REMOTE_DIR = "/opt/zhihu-monitor"

LOCAL_DIR = Path(__file__).resolve().parent


def make_bundle(bundle_path: Path):
    print(f"📦 正在打包本地知乎云端监控套件为 {bundle_path.name}...")
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
    print(f"✅ 打包完成: 大小 {bundle_path.stat().st_size / 1024:.1f} KB")


def deploy():
    bundle = LOCAL_DIR / "zhihu_monitor_bundle.tar.gz"
    make_bundle(bundle)

    print(f"\n📡 正在连接云服务器 {SERVER_USER}@{SERVER_IP}:{SERVER_PORT}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connected = False
    for attempt in range(1, 6):
        try:
            client.connect(SERVER_IP, port=SERVER_PORT, username=SERVER_USER, password=SERVER_PASS, timeout=20, banner_timeout=60, auth_timeout=30)
            connected = True
            print("✅ SSH 连接成功！")
            break
        except Exception as e:
            print(f"⚠️ SSH 连接重试 ({attempt}/5): {e}")
            time.sleep(3)

    if not connected:
        print("\n❌ 远程 SSH 直连失败。")
        print("💡 提示：若本地开启了 TUN/透明代理模式，请在客户端将 38.76.206.7 加入直连白名单，或在云服务器控制台终端直接执行部署。")
        return 1

    try:
        sftp = client.open_sftp()
        print(f"📁 创建远程目录 {REMOTE_DIR}...")
        client.exec_command(f"mkdir -p {REMOTE_DIR} {REMOTE_DIR}/data {REMOTE_DIR}/logs {REMOTE_DIR}/outputs")
        
        remote_bundle = f"{REMOTE_DIR}/bundle.tar.gz"
        print(f"📤 上传部署包到 {remote_bundle}...")
        sftp.put(str(bundle), remote_bundle)
        sftp.close()

        print("⚙️ 正在远程解压并执行部署脚本...")
        stdin, stdout, stderr = client.exec_command(
            f"cd {REMOTE_DIR} && tar -xzf bundle.tar.gz && chmod +x install_cloud.sh && bash install_cloud.sh"
        )
        for line in stdout:
            print("  ", line.strip())

        err = stderr.read().decode()
        if err:
            print("[STDERR]:", err)

        print("\n🔍 检查服务运行状态...")
        stdin, stdout, stderr = client.exec_command("systemctl status zhihu-monitor zhihu-web --no-pager")
        print(stdout.read().decode())

        print("\n" + "=" * 60)
        print("🎉 云端持续监控系统部署完成！")
        print("🌐 Web 大盘访问地址: http://38.76.206.7:8770")
        print("=" * 60)

    finally:
        client.close()
        if bundle.exists():
            bundle.unlink()


if __name__ == "__main__":
    deploy()
