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

print("=== 3. 测试回答评论抓取 ===")
ans_id = "1921568775955776809"
url = f"https://www.zhihu.com/api/v4/comment_v5/answers/{ans_id}/root_comment"
params = {"limit": 10, "offset": ""}
r = requests.get(url, headers=headers, params=params, timeout=10)
print(f"Comments Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    comments = data.get("data", [])
    print(f"获取到 {len(comments)} 条主评论：")
    for idx, c in enumerate(comments, 1):
        author = c.get("author", {})
        author_name = author.get("name")
        author_id = author.get("id")
        author_url_token = author.get("url_token")
        content = c.get("content")
        child_count = c.get("child_comment_count", 0)
        print(f"  [{idx}] [{author_name} (token: {author_url_token})]: {content} (子评论: {child_count}条)")
        if child_count > 0:
            cid = c.get("id")
            c_url = f"https://www.zhihu.com/api/v4/comment_v5/comment/{cid}/child_comment"
            cr = requests.get(c_url, headers=headers, params={"limit": 5, "offset": ""}, timeout=10)
            if cr.status_code == 200:
                for sub_idx, sub in enumerate(cr.json().get("data", []), 1):
                    sub_author = sub.get("author", {}).get("name")
                    print(f"      └─ 楼中楼[{sub_idx}] [{sub_author}]: {sub.get('content')}")
else:
    print(f"获取评论失败: {r.text[:300]}")
