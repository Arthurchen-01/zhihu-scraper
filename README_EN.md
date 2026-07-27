<div align="center">

# Zhihu-Scraper

**Turn one Zhihu URL into a readable, portable local archive**

[![CI](https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper)

[简体中文](README.md) · **English**

</div>

Zhihu-Scraper is a local-first Zhihu archiver. Give it an article, answer, question, column, or standalone-video URL. It tries the lightweight HTTP/API path first, optionally falls back to a browser, normalizes the result, and writes Markdown, static HTML, SQLite, and local media.

The project serves developers studying an engineered crawler as well as non-technical users who let an agent such as Codex run the command. There is no TUI, cloud account, or frontend build system: the public surface is one CLI and one Python function.

> [!CAUTION]
> Use this project only for learning, research, and lawful personal archiving. Follow Zhihu's terms, robots rules, copyright and privacy obligations, and applicable law. Do not bypass paid, private, or unauthorized content; do not overload the service; and do not republish archives containing personal information without permission.

## Supported Targets

| Input URL | Archive behavior |
| --- | --- |
| `https://zhuanlan.zhihu.com/p/<article ID>` | One article, including its column references |
| `https://www.zhihu.com/question/<question ID>/answer/<answer ID>` | The specified answer |
| `https://www.zhihu.com/answer/<answer ID>` | The specified answer |
| `https://www.zhihu.com/question/<question ID>` | Paginated answers merged into one question document |
| `https://www.zhihu.com/column/<column token>` | A column directory and its articles |
| `https://www.zhihu.com/zvideo/<video ID>` | A standalone Zhihu video |

The content parser covers paragraphs, headings, lists, quotes, tables, code, links, images, animations, and TeX formulas. For a standalone video, it selects the rendition with the largest known dimensions. Interrupted downloads retain a `.part` file; archiving the same target again uses an HTTP Range request to resume and checks the final byte count when the server provides a length. A stale body image, animation, or cover does not destroy the text archive: remaining assets continue and structured warnings identify failures. Undownloaded remote media is shown as an ordinary link rather than an automatic browser request. Failure of a standalone video's primary file remains explicit and fatal.

Column collections, video embedded inside an article or answer, author profiles, search results, pins, favorites, and Yanxuan content are not supported.

## Installation

Python 3.12 or newer is required. Keep the project-specific `.venv` to avoid changing the system Python environment.

### macOS / Linux script

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
./scripts/install.sh
source .venv/bin/activate
```

The script installs both project dependencies and the managed Chromium browser. On Linux it also installs the browser's system libraries and may ask for a `sudo` password.

### Windows PowerShell script

```powershell
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
.\scripts\install.ps1
.\.venv\Scripts\Activate.ps1
```

The PowerShell script also installs the managed Chromium browser.

### uv

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
uv sync --locked
uv run playwright install chromium
uv run zhihu --help
```

On a fresh Linux system, use `uv run playwright install --with-deps chromium` so that browser system libraries are installed as well.

### Manual pip workflow

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m playwright install chromium
```

Playwright is a core runtime dependency because browser fallback is part of the reliable fetch path; the Chromium binary still needs a one-time installation command. A project-local virtual environment isolates dependencies and command entry points; it does not mean the crawler must run in a container.

On a fresh Linux system, use `python -m playwright install --with-deps chromium`.

## First Archive

Generate a settings file:

```bash
zhihu init
```

`init` creates `./settings.toml` by default and never overwrites an existing file. Other commands do **not** discover this file automatically, so pass it explicitly:

```bash
zhihu check -s settings.toml
zhihu fetch -s settings.toml "https://zhuanlan.zhihu.com/p/357892158"
```

Or use the built-in defaults without a settings file:

```bash
zhihu fetch "https://www.zhihu.com/zvideo/1666569497233207296"
```

Useful one-run overrides:

```bash
zhihu fetch -s settings.toml --comments URL
zhihu fetch -s settings.toml --no-media URL
zhihu fetch -s settings.toml --browser always URL
zhihu fetch -s settings.toml --cdp http://127.0.0.1:9222 URL
zhihu fetch -s settings.toml -o "/path/to/archive" URL
```

Command reference:

```bash
zhihu --help
zhihu fetch --help
zhihu check --help
zhihu init --help
```

## Configure Cookies Safely

Public content may work without authentication, but some endpoints require a valid session. The project reads JSON exported from a browser, either a simple object or a common list of `name` / `value` records. To avoid leaking unrelated credentials, list records are accepted only when their domain is explicitly `zhihu.com` or a subdomain; object form should contain Zhihu cookies only.

1. Export cookies only from your own signed-in Zhihu session, using a browser tool you trust.
2. Store the file somewhere that is neither synced nor committed. Inside this repository, `.local/cookies.json` is recommended; `.local/` is ignored by Git.
3. Put only the file path in `settings.toml`. Never put cookie values there.

Minimal object form (replace the angle-bracket placeholders locally, and never post the real values in an issue, chat, or log):

```json
{
  "z_c0": "<your z_c0 value>",
  "d_c0": "<your d_c0 value>"
}
```

Reference the file from `settings.toml`:

```toml
[network]
cookie_file = ".local/cookies.json"
```

Then verify both the required fields and the real session:

```bash
zhihu check -s settings.toml
```

To check a different file once:

```bash
zhihu check --cookie-file /private/path/cookies.json
```

On macOS/Linux, you can additionally run `chmod 600 .local/cookies.json`. Cookies are login credentials; if exposure is suspected, sign out the relevant Zhihu session and sign in again. `check` reports only field completeness and authentication status, never cookie values.

## `settings.toml`

`zhihu init` generates these defaults:

```toml
[archive]
output_dir = "知乎归档"
markdown = true
html = true
sqlite = true
pdf = false
comments = false
comment_roots = 10
comment_replies = 10
media_download = true

[network]
# cookie_file = ".local/cookies.json"
# proxy = "http://127.0.0.1:7890"
timeout = 30.0
retries = 3
page_size = 20

[browser]
fallback = "auto"
headless = false
# cdp_url = "http://127.0.0.1:9222"
```

Markdown, HTML, SQLite, and media downloads are enabled by default. PDF, comments, and proxy use are disabled. When comments are enabled, each content item stores up to 10 root comments in API return order and up to 10 replies for each root; smaller threads are kept in full. The 10/10 limits are configurable, and `--comments` enables them for one run. Disabling comments means “do not fetch them in this run”: a repeated archive preserves comments already stored in SQLite and the readable documents. Disabling media downloads likewise reuses local files that still exist.

`browser.fallback` accepts:

- `auto`: HTTP/API first, then browser when the request is blocked or the payload is invalid.
- `never`: HTTP/API only.
- `always`: use browser page state for the single target immediately.

Without CDP, the project tries system Chrome first and falls back to its managed Chromium; both use a project-owned persistent browser directory. With `cdp_url`, it can attach to an already signed-in local Chrome session. To protect the authenticated control channel, only HTTP/WebSocket endpoints on `localhost`, `127.0.0.1`, or `[::1]` are accepted.

`network.proxy` applies consistently to HTTP/API requests, the project-managed browser, and media downloads. An external CDP browser keeps its own proxy configuration. Requests and media downloads share the configured timeout and bounded retry policy, and logs redact cookies and proxy credentials.

## Local Output

All archived content shares one `zhihu.db` at the archive root. Only a whole column creates `内容/`:

```text
知乎归档/
├── zhihu.db
└── 机器学习/
    ├── 机器学习.md
    ├── 机器学习.html
    ├── 内容/
    │   ├── 一文归纳AI数据增强之法.md
    │   ├── 一文归纳AI数据增强之法.html
    │   └── RNN_LSTM_BPTT详细推导.md
    ├── media/
    └── assets/
```

The column-named files are complete, year-grouped directories and show `本栏目共 N 篇`. Each article page records its column membership, current archive origin, a directory link, and previous/next navigation.

A single article, answer, whole question, or standalone video uses the compact layout:

```text
知乎归档/
├── zhihu.db
└── Title/
    ├── Title.md
    ├── Title.html
    ├── media/
    └── assets/
```

Answers under a question become sections in one question document; they do not create `内容/`. `media/` is created only when downloadable media exists. When HTML is enabled, `assets/` contains the project's own local reading stylesheet. HTML is regenerated from normalized content and does not copy Zhihu's HTML, CSS, or JavaScript.

Original TeX is retained: Markdown uses `$…$` / `$$…$$`; HTML converts it to locally generated, browser-native MathML while keeping a safe trace expression in `data-tex`. No network-loaded KaTeX or MathJax is required. Generated MathML is stripped of link, event, and style attributes; malformed expressions safely fall back to readable TeX.

SQLite currently stores content, authors, columns, comments, media, and relations directly supported by source data. It is the archive data layer; it does not imply that search or graph queries already exist.

## Python API

```python
from pathlib import Path

from zhihu_scraper import ArchiveSettings, archive_url

report = archive_url(
    "https://zhuanlan.zhihu.com/p/357892158",
    ArchiveSettings(output_dir=Path("知乎归档")),
)

print(report.target.title)
print(report.receipt.entry_directory)
```

`archive_url(URL, settings) -> ArchiveReport` is the shared synchronous entry point for the CLI, agents, and future interfaces. The source, browser, and archive boundaries are injectable through `build_workflow` for tests and extensions.

## Three Platforms and Development

Fetching, normalization, rendering, and SQLite behavior are shared across Windows, macOS, and Linux. The platform adapter contains real differences such as browser locations, application-data directories, and safe filenames. CI covers Python 3.12, 3.13, and 3.14 on all three operating systems. Zhihu endpoints and anti-bot behavior can change at any time, so a green test suite cannot guarantee that every future URL will remain fetchable.

Set up a development environment:

```bash
uv sync --locked --extra dev
uv run playwright install chromium
```

Run the complete local quality gate:

```bash
PYTHONWARNINGS=error::ResourceWarning uv run pytest
uv run ruff check zhihu_scraper tests
uv run ruff format --check zhihu_scraper tests
uv run mypy zhihu_scraper
uv run python -m compileall -q zhihu_scraper
uv lock --check
uv run zhihu --help
```

Live Zhihu smoke tests are skipped by default and run only when a local cookie file is supplied explicitly:

```bash
ZHIHU_LIVE=1 ZHIHU_COOKIE_FILE=/private/path/cookies.json \
  uv run pytest tests/live/test_live_archive.py
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for module boundaries. Deferred PDF, keyword search, semantic search, and knowledge-graph work is tracked in [docs/FEATURE_TODO.md](docs/FEATURE_TODO.md). Raw JSON is not a user-facing archive format.

## References and License

The rebuild compared ideas from [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler), [CrawlerTutorial](https://github.com/NanmiCoder/CrawlerTutorial), [Ther-nullptr/zhihu-scraper](https://github.com/Ther-nullptr/zhihu-scraper), and [chenluda/zhihu-download](https://github.com/chenluda/zhihu-download). This repository independently maintains its implementation and tests; it does not vendor source from those projects.

Licensed under the [MIT License](LICENSE).
