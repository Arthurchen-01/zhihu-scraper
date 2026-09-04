import paramiko
import socks
import socket
import sys

sys.stdout.reconfigure(encoding="utf-8")

HOST = "38.76.206.7"
PORT = 22
USER = "root"
PASS = "39TF6xMH52yC"

# Test through local proxy if any (127.0.0.1:7890 or 10808)
proxies = [
    ("Direct", None, None),
    ("Local Clash HTTP 7890", "127.0.0.1", 7890),
    ("Local Clash SOCKS 7890", "127.0.0.1", 7890),
    ("Local v2ray 10808", "127.0.0.1", 10808),
    ("Local v2ray 10809", "127.0.0.1", 10809),
]

for name, p_host, p_port in proxies:
    print(f"\n--- Testing connection via {name} ---")
    try:
        if p_host:
            sock = socks.socksocket()
            if "HTTP" in name:
                sock.set_proxy(socks.HTTP, p_host, p_port)
            else:
                sock.set_proxy(socks.SOCKS5, p_host, p_port)
            sock.settimeout(5)
            sock.connect((HOST, PORT))
        else:
            sock = socket.create_connection((HOST, PORT), timeout=5)
        
        t = paramiko.Transport(sock)
        t.start_client(timeout=5)
        t.auth_password(USER, PASS)
        if t.is_authenticated():
            print(f"SUCCESS with {name}!")
            client = paramiko.SSHClient()
            client._transport = t
            stdin, stdout, stderr = client.exec_command("uptime")
            print(stdout.read().decode())
            t.close()
            break
        t.close()
    except Exception as e:
        print(f"Failed via {name}: {e}")
