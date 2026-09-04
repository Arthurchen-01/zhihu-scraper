import json
import sys
from pathlib import Path
import requests

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

print("=== 1. 测试个人登录态 (/api/v4/me) ===")
try:
    r = requests.get("https://www.zhihu.com/api/v4/me", headers=headers, timeout=10)
    print(f"Status Code: {r.status_code}")
    if r.status_code == 200:
        me_data = r.json()
        print(f"登录成功! 用户名: {me_data.get('name')}, UID: {me_data.get('id')}, url_token: {me_data.get('url_token')}")
    else:
        print(f"响应内容: {r.text[:300]}")
except Exception as e:
    print(f"请求失败: {e}")

print("\n=== 2. 测试知乎搜索 (/api/v4/search_v3) ===")
try:
    params = {
        "t": "general",
        "q": "清一武道馆",
        "correction": 1,
        "offset": 0,
        "limit": 5,
    }
    r = requests.get("https://www.zhihu.com/api/v4/search_v3", headers=headers, params=params, timeout=10)
    print(f"Search Status Code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        items = data.get("data", [])
        print(f"搜索到 {len(items)} 条结果：")
        for idx, item in enumerate(items, 1):
            target = item.get("object", {})
            t_type = target.get("type", item.get("type", "unknown"))
            title = target.get("title") or target.get("question", {}).get("title") or "无标题"
            url = target.get("url", "")
            print(f"  [{idx}] [{t_type}] {title} ({url})")
    else:
        print(f"搜索接口返回: {r.text[:300]}")
except Exception as e:
    print(f"搜索请求失败: {e}")
