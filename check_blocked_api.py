import json
import requests
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
cookie = config.get("cookie", "").strip()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cookie": cookie,
    "Referer": "https://www.zhihu.com/settings/filter",
    "x-requested-with": "fetch",
}

eps = [
    "https://www.zhihu.com/api/v4/settings/blocked_users",
    "https://www.zhihu.com/api/v4/members/chang-ge-yu-29/blocked_users",
    "https://www.zhihu.com/api/v4/members/8b90e40e0b48202f19be772117875c74/blocked_users",
    "https://www.zhihu.com/api/v4/me/blocks",
    "https://api.zhihu.com/settings/blocked_users",
    "https://www.zhihu.com/settings/filter",
]

for ep in eps:
    r = requests.get(ep, headers=headers, timeout=5)
    print(f"\n--- {ep} -> Status: {r.status_code} ---")
    print(f"Content-Type: {r.headers.get('content-type')}")
    print(f"Body: {r.text[:300]}")
