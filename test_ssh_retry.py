import paramiko
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

SERVER_IP = "38.76.206.7"
SERVER_PORT = 22
SERVER_USER = "root"
SERVER_PASS = "39TF6xMH52yC"

for attempt in range(1, 6):
    try:
        print(f"📡 连接 SSH (尝试 {attempt}/5, banner_timeout=60s)...")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(SERVER_IP, port=SERVER_PORT, username=SERVER_USER, password=SERVER_PASS, timeout=30, banner_timeout=60, auth_timeout=30)
        print("✅ SSH 连接成功！")
        stdin, stdout, stderr = client.exec_command("uname -a && uptime")
        print(stdout.read().decode("utf-8"))
        client.close()
        break
    except Exception as e:
        print(f"⚠️ 失败: {e}")
        time.sleep(3)
