<div align="center">

<img src="https://socialify.git.ci/yuchenzhu-research/zhihu-scraper/image?description=1&font=Inter&language=1&name=1&owner=1&pattern=Solid&stargazers=1&theme=Auto" alt="Zhihu-Scraper project card" width="720" />

# Zhihu-Scraper

**Turn Zhihu links into a local knowledge archive you actually own**

<p>
  <img src="https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg" alt="CI Badge" />
  <img src="https://img.shields.io/static/v1?label=python&message=3.14%2B&color=3776AB&style=flat-square&logo=python&logoColor=white" alt="Python Badge" />
  <img src="https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper?style=flat-square" alt="License Badge" />
</p>

<p>
  <a href="README.md">简体中文</a> · <strong>English</strong>
</p>

</div>

Zhihu-Scraper is a **local-first** Zhihu archiving tool. Paste a link and it saves content, metadata, and images as local Markdown files, while also writing an SQLite index for offline reading, search, backup, and migration.

> [!WARNING]
> This project is strictly for learning, research, and personal archiving. Please comply with Terms of Service, crawler guidelines, and local laws.

> [!NOTE]
> This project is now closed at `v3.0.1-final`. Future compatibility with Zhihu API, page structure, or anti-bot changes is not guaranteed; exported Markdown, images, and SQLite data are the long-term deliverables.

## What You Get

| Output | Why it matters | Default location |
| --- | --- | --- |
| Markdown | Read, edit, and sync like normal notes | `data/entries/` |
| Images | Offline original images referenced by Markdown | Each entry's `images/` |
| SQLite | Local search, deduplication, and analysis | `data/zhihu.db` |

## Start in Three Minutes

### 1. Install

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
./install.sh
```

macOS / Linux users should check Python first:

```bash
python3 --version  # requires Python 3.14+
```

On Windows, use PowerShell and prefer WSL or an equivalent Python 3.14+ environment:

```powershell
py -3.14 --version
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[full]"
.\.venv\Scripts\python -m playwright install chromium
New-Item -ItemType Directory -Force .local | Out-Null
if (!(Test-Path .local\cookies.json)) { Copy-Item cookies.example.json .local\cookies.json }
.\.venv\Scripts\python cli\app.py check
```

### 2. Check Runtime

```bash
./zhihu check
```

After opening a new shell, the global `zhihu` command may also be available:

```bash
zhihu check
```

### 3. Archive One Link

```bash
./zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

For authenticated content, log in to Zhihu in your browser, copy your own `z_c0` and `d_c0` values into `.local/cookies.json`, then run `zhihu check`.

## Daily Use

The daily entry point is the CLI:

```bash
zhihu fetch URL               # Archive one link
zhihu fetch --file urls.txt   # Batch archive links from a file
zhihu query KEYWORD           # Search the local SQLite archive
zhihu config                  # Show current configuration
zhihu check                   # Check the local runtime environment
```

Local paths are controlled by the `local` section in `config.yaml`:

```yaml
local:
  cookies_file: .local/cookies.json
  output_dir: data
```

Both `cookies_file` and `output_dir` support absolute paths; relative paths are resolved from the project root on macOS, Linux, and Windows.

## Core Features

- **Protocol-first**: Uses a protocol-first API / HTML path first, with browser fallback for complex column pages.
- **Local-first**: Content, images, and indexes stay in local folders instead of a cloud account.
- **Readable failures**: HTTP blocks, missing cookies, and deleted/private content are surfaced with concrete hints.
- **Callable API**: The core archiving workflow is available as a public Python API for web, mobile, desktop, or automation layers.

## Developer API

```python
from zhihu_scraper import ArchiveOptions, archive_url_sync

result = archive_url_sync(
    "https://www.zhihu.com/question/28696373/answer/2835848212",
    ArchiveOptions(output_dir="data", download_images=True),
)

print(result.success)
```

Async services can call the same logic directly:

```python
from zhihu_scraper import ArchiveOptions, archive_url

result = await archive_url(
    "https://www.zhihu.com/question/28696373",
    ArchiveOptions(question_limit=3),
)
```

Multi-platform guidance:

| Platform | Recommended integration |
| --- | --- |
| Web backend | Call `await archive_url(...)` from FastAPI / Django; keep the frontend display-only |
| Desktop app | Use Electron / Tauri / PySide with `archive_url_sync(...)` |
| Mobile app | Call your own backend API; reuse this package on the backend and keep cookies out of the app bundle |
| Automation | Schedule `archive_urls_sync(...)` |

## More Entry Points

- Terminal help: `zhihu --help` or `zhihu [command] --help`
- Runtime check: `zhihu check`
- Maintainers and coding agents: read [CONSTITUTION.md](CONSTITUTION.md) and [AGENTS.md](AGENTS.md) first

<div align="center">
  <sub>Local-first archive tool by Yuchen Zhu Research.</sub>
</div>
