import socket
import sys

sys.stdout.reconfigure(encoding="utf-8")

HOST = "38.76.206.7"
ssh_ports = [22, 2222, 22022, 2022, 22222, 28022, 10022, 50022, 60022, 2200, 222, 8888, 9999, 9000, 5000, 8080]

for p in ssh_ports:
    try:
        s = socket.create_connection((HOST, p), timeout=2)
        s.settimeout(2)
        try:
            banner = s.recv(1024)
            print(f"Port {p}: OPEN -> Banner: {banner}")
        except Exception as e:
            print(f"Port {p}: OPEN (no banner / timeout: {e})")
        s.close()
    except Exception:
        pass
