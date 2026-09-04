import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
cookie_str = config.get("cookie", "").strip()

# Parse cookie string into playwright cookie dicts
cookies = []
for item in cookie_str.split(";"):
    if "=" in item:
        name, value = item.strip().split("=", 1)
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": ".zhihu.com",
            "path": "/"
        })

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0")
    context.add_cookies(cookies)
    page = context.new_page()

    blocked_api_calls = []

    page.on("response", lambda res: blocked_api_calls.append({"url": res.url, "status": res.status}) if "block" in res.url or "filter" in res.url or "member" in res.url else None)

    print("Navigating to https://www.zhihu.com/settings/filter ...")
    page.goto("https://www.zhihu.com/settings/filter", wait_until="networkidle", timeout=30000)

    print("Page title:", page.title())
    html = page.content()

    # Look for blocked user elements in DOM
    users = page.query_selector_all(".UserItem, .BlockedUsers-item, a[href*='/people/']")
    print(f"Found {len(users)} potential user links on page.")

    for u in users:
        href = u.get_attribute("href") or ""
        text = u.inner_text()
        if "/people/" in href:
            print(f"  User: {text.strip()} -> {href}")

    print("\nCaptured related API calls:")
    for call in blocked_api_calls:
        print(f"  {call['status']} {call['url']}")

    browser.close()
