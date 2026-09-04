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
    "Referer": "https://www.zhihu.com/",
    "x-requested-with": "fetch",
}

# Candidate Blacklist API endpoints on Zhihu
endpoints = [
    "https://www.zhihu.com/api/v4/settings/blocked_users",
    "https://www.zhihu.com/api/v4/members/me/blocks",
    "https://www.zhihu.com/api/v4/settings/blocks",
    "https://www.zhihu.com/api/v4/me/blocked_users",
]

for ep in endpoints:
    try:
        r = requests.get(ep, headers=headers, params={"offset": 0, "limit": 20}, timeout=5)
        print(f"Endpoint {ep} -> HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            items = data.get("data", []) if isinstance(data, dict) else data
            print(f"Found {len(items)} items in {ep}")
            if items:
                print("First item:", json.dumps(items[0], ensure_ascii=False)[:300])
    except Exception as e:
        print(f"Endpoint {ep} failed: {e}")
