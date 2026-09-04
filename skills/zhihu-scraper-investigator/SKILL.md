---
name: zhihu-scraper-investigator
description: Universal Zhihu Scraper & Target Investigator Skill. Use this skill whenever the user asks to scrape Zhihu articles, download columns, archive an author's answers/pins, extract nested comment trees, capture high-resolution Playwright screenshots, or perform targeted evidence gathering on any Zhihu user or topic.
---

# Zhihu Scraper & Target Investigator Skill

A comprehensive, production-grade toolkit and agent skill for inspecting, scraping, and archiving Zhihu content (Authors, Columns, Articles, Answers, Pins, and Nested Comment Trees).

---

## 🛠️ When to Use This Skill

Activate this skill whenever:
1. **Target Author Investigation**: The user gives a Zhihu profile URL (e.g. `https://www.zhihu.com/people/xxx`) and wants to list, audit, or archive their articles, answers, or pins.
2. **Column Archival**: The user provides a column URL (`https://zhuanlan.zhihu.com/...` or `/column/xxx`) to download all contained articles into Markdown/HTML.
3. **Comment Tree Extraction**: The user needs full nested楼中楼 (nested multi-level) comments for legal evidence or sentiment analysis.
4. **Visual Proof & Screenshots**: The user needs high-DPI full-page screenshots with optional highlighted keywords (bounding boxes) for legal or reporting purposes.
5. **Interactive Self-Service Web UI**: The user wants to run the visual web dashboard for classmates or team members to paste their cookie, inspect assets via a checklist, track real-time progress bars, and download a ZIP file.

---

## 🚀 Quick Execution Guide

### 1. Launching the Interactive Web UI
To start the visual web interface on port 8775:
```bash
python -m zhihu_scraper.app.web
# Opens http://localhost:8775 in browser
```

### 2. Inspecting an Author or Column (CLI / Python)
```python
from zhihu_scraper import ZhihuClient, AuthorScraper, ColumnScraper

client = ZhihuClient(cookie="YOUR_ZHIHU_COOKIE")

# Inspect author
author_scraper = AuthorScraper(client)
catalog = author_scraper.catalog_all_assets("https://www.zhihu.com/people/shou-qi-hei")
print("Author:", catalog["author"]["name"])
print("Found items:", len(catalog["items"]))
```

### 3. Downloading Articles, Answers & Comments
```python
from zhihu_scraper import ZhihuClient, ArticleScraper, CommentScraper
from pathlib import Path

client = ZhihuClient(cookie="YOUR_COOKIE")
art_scraper = ArticleScraper(client)
comment_scraper = CommentScraper(client)

# Save article markdown
art_data = art_scraper.scrape("1931445943309427470", save_dir=Path("./outputs/articles"))

# Save comment tree JSON
comments = comment_scraper.scrape_comment_tree(
    "article", "1931445943309427470", save_path=Path("./outputs/comments/comments_1931445943309427470.json")
)
```

### 4. High-DPI Visual Full-Page Screenshot with Playwright
```python
from zhihu_scraper import VisualArchiver
from pathlib import Path

archiver = VisualArchiver(cookie="YOUR_COOKIE")
archiver.capture_screenshot(
    url="https://zhuanlan.zhihu.com/p/1931445943309427470",
    output_path=Path("./outputs/screenshots/evidence.png"),
    highlight_keywords=["违规", "造谣", "侵权"]
)
```

---

## 📂 Multi-Agent & IDE Synchronization

This skill is designed to work seamlessly across:
- **Antigravity**: `~/.gemini/config/skills/zhihu-scraper-investigator`
- **Codex**: `~/.codex/skills/zhihu-scraper-investigator`
- **Cursor**: `~/.cursor/skills-cursor/zhihu-scraper-investigator`
- **Agents**: `~/.agents/skills/zhihu-scraper-investigator`

When switching to a new machine, simply run:
```bash
scripts/install_skills.bat   # Windows
# or
bash scripts/install_skills.sh # Linux / macOS
```
