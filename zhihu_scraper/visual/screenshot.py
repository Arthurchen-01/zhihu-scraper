"""Zhihu Visual Archival & Playwright High-DPI Screenshot Engine."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("zhihu_scraper.visual.screenshot")


class VisualArchiver:
    """Takes high-DPI full-page screenshots with optional target keyword bounding boxes."""

    def __init__(self, cookie: str = "", headless: bool = True):
        self.cookie = cookie
        self.headless = headless

    def capture_screenshot(
        self,
        url: str,
        output_path: Path,
        highlight_keywords: Optional[List[str]] = None,
        timeout: int = 30000
    ) -> bool:
        """Capture high-resolution full-page screenshot of any Zhihu URL."""
        from playwright.sync_api import sync_playwright

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 960},
                device_scale_factor=2,  # Retina 2x high-DPI
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            )

            # Inject cookies
            if self.cookie:
                cookies_list = []
                for item in self.cookie.split(";"):
                    if "=" in item:
                        k, v = item.strip().split("=", 1)
                        cookies_list.append({"name": k, "value": v, "domain": ".zhihu.com", "path": "/"})
                if cookies_list:
                    try:
                        context.add_cookies(cookies_list)
                    except Exception as e:
                        logger.warning("Could not set cookies: %s", e)

            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                page.wait_for_timeout(2500)

                # Dismiss login / cookie dialogs if any
                page.evaluate("""() => {
                    const selectors = [
                        '.Modal-wrapper', '.Modal-backdrop', '.GlobalWriteV2-modal',
                        '.sign_in_modal', '.Modal-closeButton', '.OpenInAppButton'
                    ];
                    selectors.forEach(s => {
                        document.querySelectorAll(s).forEach(el => el.remove());
                    });
                    document.body.style.overflow = 'auto';
                }""")

                # Highlight keywords if provided
                if highlight_keywords:
                    kw_json = str(highlight_keywords)
                    page.evaluate(f"""() => {{
                        const kws = {kw_json};
                        const treeWalker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                        const nodes = [];
                        while (treeWalker.nextNode()) nodes.push(treeWalker.currentNode);
                        nodes.forEach(node => {{
                            kws.forEach(kw => {{
                                if (kw && node.nodeValue && node.nodeValue.includes(kw)) {{
                                    const parent = node.parentElement;
                                    if (parent && parent.tagName !== 'SCRIPT' && parent.tagName !== 'STYLE') {{
                                        parent.style.border = '2px solid #ef4444';
                                        parent.style.backgroundColor = 'rgba(239, 68, 68, 0.15)';
                                        parent.style.borderRadius = '4px';
                                        parent.style.padding = '2px';
                                    }}
                                }}
                            }});
                        }});
                    }}""")

                page.screenshot(path=str(output_path), full_page=True)
                logger.info("Saved screenshot to %s", output_path)
                return True
            except Exception as e:
                logger.error("Failed to capture screenshot for %s: %s", url, e)
                return False
            finally:
                context.close()
                browser.close()
