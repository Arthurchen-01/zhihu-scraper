import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")

HOST = "38.76.206.7"
PORT = 22
USER = "root"
PASS = "39TF6xMH52yC"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {HOST}:{PORT} as {USER}...")
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)
    print("SSH connection successful!")
    
    stdin, stdout, stderr = ssh.exec_command("uname -a && uptime && free -h && df -h /")
    print(stdout.read().decode("utf-8"))
    
    stdin, stdout, stderr = ssh.exec_command("python3 --version || python --version")
    print("Python version:", stdout.read().decode("utf-8").strip())
    
    ssh.close()
except Exception as e:
    print("Connection failed:", e)
