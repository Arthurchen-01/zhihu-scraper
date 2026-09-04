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

    page.goto("https://www.zhihu.com/settings/filter", wait_until="networkidle", timeout=30000)

    # Find all edit buttons
    edit_buttons = page.query_selector_all("button:has-text('编辑')")
    print(f"Found {len(edit_buttons)} 编辑 buttons.")

    for i, btn in enumerate(edit_buttons):
        try:
            print(f"Clicking edit button #{i+1}...")
            btn.click()
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Failed to click button #{i+1}: {e}")

    page.screenshot(path="outputs/filter_expanded.png", full_page=True)

    # Extract all user links / text inside the expanded blocked lists
    items = page.query_selector_all("a[href*='/people/'], .BlockedUsers-item, [class*='UserItem'], [class*='member']")
    print(f"\nFound {len(items)} member elements after expanding:")
    for it in items:
        href = it.get_attribute("href") or ""
        text = it.inner_text().strip().replace("\n", " ")
        print(f"  Item: {text} -> {href}")

    browser.close()
