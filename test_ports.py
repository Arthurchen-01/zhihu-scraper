import requests
import sys

sys.stdout.reconfigure(encoding="utf-8")

HOST = "38.76.206.7"
ports = [80, 443, 8765, 8766, 8998, 8999, 8000, 3000]

for p in ports:
    url = f"http://{HOST}:{p}" if p != 443 else f"https://{HOST}"
    try:
        r = requests.get(url, auth=("admin", "39TF6xMH52yC"), timeout=3)
        print(f"Port {p}: HTTP {r.status_code} ({len(r.text)} bytes)")
    except Exception as e:
        print(f"Port {p}: Failed ({type(e).__name__})")
