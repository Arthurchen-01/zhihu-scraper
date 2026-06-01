<div align="center">

# Zhihu-Scraper
**Local-first Zhihu Archiving, More Elegant Than Ever**

<p>
  <img src="https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg" alt="CI Badge" />
  <img src="https://img.shields.io/static/v1?label=python&message=3.14%2B&color=3776AB&style=flat-square&logo=python&logoColor=white" alt="Python Badge" />
  <img src="https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper?style=flat-square" alt="License Badge" />
</p>

<p>
  <a href="README.md">简体中文</a> · <strong>English</strong>
</p>

</div>

Zhihu-Scraper is a **local-first** crawling and archiving tool. Paste a link, and it automatically extracts the main content, metadata, downloads images, and natively converts everything into high-quality Markdown and an SQLite index database for long-term storage.

It's the ultimate companion for command-line workflows—reject cloud lock-ins and keep complete ownership of your data locally.

> [!WARNING]  
> This project is strictly for learning, research, and personal archiving. Please comply with Terms of Service, crawler guidelines, and local laws.

> [!NOTE]
> This project is now closed at `v3.0.1-final`. Future compatibility with Zhihu API, page structure, or anti-bot changes is not guaranteed; exported Markdown, images, and SQLite data are the long-term deliverables.

<br>

## 🚀 Quick Start

Clone the repository, then run the installer to create the virtual environment and local runtime directory.

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper

# Creates .venv and installs dependencies automatically
./install.sh
```

### macOS / Linux

```bash
# macOS commonly uses python3, not python. This project requires Python 3.14+.
python3 --version

# The installer creates .venv and tries to install a global zhihu command.
./install.sh

# If the current shell has not picked up PATH yet, use the repo launcher.
./zhihu check
./zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

After opening a new shell, `zhihu` may be available globally:

```bash
zhihu
zhihu check
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

### Windows

On Windows, use PowerShell and prefer WSL or an equivalent Python 3.14+ environment:

```powershell
py -3.14 --version
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[full]"
.\.venv\Scripts\python -m playwright install chromium
New-Item -ItemType Directory -Force .local | Out-Null
if (!(Test-Path .local\cookies.json)) { Copy-Item cookies.example.json .local\cookies.json }
.\.venv\Scripts\python cli\app.py check
.\.venv\Scripts\python cli\app.py fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

### Configure Cookies

The installer creates `.local/cookies.json` from `cookies.example.json`. For authenticated scraping, log in to Zhihu in your browser, copy your own `z_c0` and `d_c0` values into `.local/cookies.json`, then run:

```bash
./zhihu check
./zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

## ✨ Core Features

- **Local Archiving Paths**: Supports individual answers, question pages (Top-N extraction), column articles, and creator profiles on the currently validated paths.
- **Local Supremacy**: Outputs directly to `Markdown` files, offline image directories (Images), and `SQLite` metadata.
- **Protocol First**: Uses protocol-first API / HTML paths, with browser fallback available for complex column pages.
- **Incremental Monitoring**: The `monitor` command can check collection updates with local state.
- **Textual TUI**: A full-screen workbench for queues, recent results, retry flow, and language switching.

## 🧭 Command Quick Reference

```bash
zhihu                         # Open the Textual TUI full-screen workbench
zhihu fetch URL               # Archive one link
zhihu fetch --file urls.txt   # Batch archive links from a file
zhihu creator PEOPLE_URL      # Archive creator profile content
zhihu monitor COLLECTION_ID   # Incrementally monitor a collection
zhihu query KEYWORD           # Search the local SQLite archive
zhihu interactive             # Explicitly open the interactive workbench
zhihu config                  # Show current configuration
zhihu check                   # Check the local runtime environment
```

## 📚 Documentation & Configuration

Want to understand the available CLI commands?

- Terminal Help: Run `zhihu --help` or `zhihu [command] --help`
- Config check: Run `zhihu check` to inspect Cookie, config file, and browser dependency status.
- Maintainers and coding agents should read [CONSTITUTION.md](CONSTITUTION.md) and [AGENTS.md](AGENTS.md) first.

<br>

<div align="center">
  <sub>Built with ❤️ by Yuchen Zhu Research.</sub>
</div>
