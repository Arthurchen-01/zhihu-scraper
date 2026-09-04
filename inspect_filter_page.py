import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
cookie_str = config.get("cookie", "").strip()

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
    context = browser.new_context()
    context.add_cookies(cookies)
    page = context.new_page()

    apis = []
    page.on("response", lambda res: apis.append({"url": res.url, "status": res.status}))

    page.goto("https://www.zhihu.com/settings/filter", wait_until="networkidle", timeout=30000)
    page.screenshot(path="outputs/filter_page.png", full_page=True)
    
    # Check all buttons and tabs
    tabs = page.query_selector_all("button, a, [role='tab']")
    print(f"Found {len(tabs)} interactive elements:")
    for t in tabs:
        txt = t.inner_text().strip()
        if txt:
            print(f"  [{t.evaluate('el => el.tagName')}] {txt}")

    # Check if there is "用户" or "黑名单" tab and click it
    user_tab = page.query_selector("text=用户") or page.query_selector("text=黑名单")
    if user_tab:
        print("Clicking user/blacklist tab...")
        user_tab.click()
        page.wait_for_timeout(3000)
        page.screenshot(path="outputs/filter_tab_clicked.png", full_page=True)

    browser.close()

print("Captured APIs:")
for a in apis:
    if "/api/" in a["url"]:
        print(f"  {a['status']} {a['url']}")
