import requests
import sys

sys.stdout.reconfigure(encoding="utf-8")

url = "http://38.76.206.7:8770"
try:
    r = requests.get(url, timeout=5)
    print(f"Web Dashboard {url} -> HTTP {r.status_code} ({len(r.text)} bytes)")
    
    r_stats = requests.get(f"{url}/api/stats", timeout=5)
    print(f"API Stats -> HTTP {r_stats.status_code}: {r_stats.text[:200]}")
except Exception as e:
    print(f"Failed: {e}")
