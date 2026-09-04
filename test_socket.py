import socket
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST = "38.76.206.7"
PORT = 22
USER = "root"
PASS = "39TF6xMH52yC"

# Test raw socket connection
print(f"1. Testing raw TCP socket to {HOST}:{PORT}...")
try:
    s = socket.create_connection((HOST, PORT), timeout=5)
    banner = s.recv(1024)
    print(f"Received raw banner: {banner}")
    s.close()
except Exception as e:
    print(f"Raw socket failed: {e}")

# Test with paramiko direct transport
print("\n2. Testing paramiko transport...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    t = paramiko.Transport(sock)
    t.start_client(timeout=10)
    t.auth_password(USER, PASS)
    if t.is_authenticated():
        print("Paramiko Transport authenticated successfully!")
        client = paramiko.SSHClient()
        client._transport = t
        stdin, stdout, stderr = client.exec_command("uptime")
        print("Output:", stdout.read().decode())
    t.close()
except Exception as e:
    print("Transport failed:", e)
