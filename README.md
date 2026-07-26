<div align="center">

<img src="https://socialify.git.ci/yuchenzhu-research/zhihu-scraper/image?description=1&font=Inter&language=1&name=1&owner=1&pattern=Solid&stargazers=1&theme=Auto" alt="Zhihu-Scraper 项目卡片" width="720" />

# Zhihu-Scraper

**把知乎链接保存成你真正拥有的本地资料库**

<p>
  <img src="https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg" alt="CI Badge" />
  <img src="https://img.shields.io/static/v1?label=python&message=3.14%2B&color=3776AB&style=flat-square&logo=python&logoColor=white" alt="Python Badge" />
  <img src="https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper?style=flat-square" alt="License Badge" />
</p>

<p>
  <strong>简体中文</strong> · <a href="README_EN.md">English</a>
</p>

</div>

Zhihu-Scraper 是一个**本地优先**的知乎抓取与归档工具。你只需要粘贴链接，它会把正文、元数据和图片整理成本地 Markdown 文件，并同步写入 SQLite 索引，之后可以离线阅读、搜索、备份或迁移。

> [!WARNING]
> 本项目仅用于学习、研究、个人归档与技术交流。请遵守服务条款、爬虫约束和当地法律法规。

> [!NOTE]
> 当前项目收束在 `v3.0.1-final`。后续不承诺持续适配知乎接口、页面结构或风控变化；已经导出的 Markdown、图片和 SQLite 数据是长期价值。

## 你会得到什么

| 输出 | 用处 | 默认位置 |
| --- | --- | --- |
| Markdown | 像普通笔记一样阅读、编辑、同步 | `data/entries/` |
| Images | 原文图片离线保存，Markdown 可直接引用 | 每篇内容的 `images/` |
| SQLite | 本地检索、去重、二次分析 | `data/zhihu.db` |

## 三分钟开始

### 1. 安装

```bash
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git
cd zhihu-scraper
./install.sh
```

macOS / Linux 用户先确认 Python 版本：

```bash
python3 --version  # 需要 Python 3.14+
```

Windows 用户建议使用 PowerShell，并优先通过 WSL 或等价的 Python 3.14+ 环境运行：

```powershell
py -3.14 --version
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[full]"
.\.venv\Scripts\python -m playwright install chromium
New-Item -ItemType Directory -Force .local | Out-Null
if (!(Test-Path .local\cookies.json)) { Copy-Item cookies.example.json .local\cookies.json }
.\.venv\Scripts\python cli\app.py check
```

### 2. 检查环境

```bash
./zhihu check
```

如果重新打开终端后 `zhihu` 命令已经可用，也可以直接运行：

```bash
zhihu check
```

### 3. 保存第一条链接

```bash
./zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

需要登录态内容时，先在浏览器登录知乎，把自己的 `z_c0` 和 `d_c0` 填入 `.local/cookies.json`，再运行 `zhihu check`。

## 日常怎么用

日常入口是 CLI 命令：

```bash
zhihu fetch URL               # 抓取单条链接
zhihu fetch --file urls.txt   # 从文件批量抓取
zhihu query KEYWORD           # 检索本地 SQLite 归档
zhihu config                  # 查看当前配置
zhihu check                   # 检查本地运行环境
```

本地路径统一由 `config.yaml` 的 `local` 段控制：

```yaml
local:
  cookies_file: .local/cookies.json
  output_dir: data
```

`cookies_file` 和 `output_dir` 都支持绝对路径；相对路径会按项目根目录解析，适用于 macOS、Linux 和 Windows。

## 核心能力

- **协议优先**：默认走轻量 API / HTML 路径，专栏等复杂页面再启用浏览器回退。
- **本地优先**：正文、图片、索引都落在本机目录，不依赖云端服务保存。
- **失败可读**：HTTP 拦截、Cookie 缺失、内容不存在等情况会给出具体提示。
- **可调用 API**：核心归档逻辑已经包装成公共 Python API，方便给网页端、移动端或自动化脚本复用。

## 给开发者：直接调用归档逻辑

```python
from zhihu_scraper import ArchiveOptions, archive_url_sync

result = archive_url_sync(
    "https://www.zhihu.com/question/28696373/answer/2835848212",
    ArchiveOptions(output_dir="data", download_images=True),
)

print(result.success)
```

异步服务可以直接用：

```python
from zhihu_scraper import ArchiveOptions, archive_url

result = await archive_url(
    "https://www.zhihu.com/question/28696373",
    ArchiveOptions(question_limit=3),
)
```

多平台移植建议：

| 平台 | 推荐接入方式 |
| --- | --- |
| Web 后端 | 在 FastAPI / Django 中调用 `await archive_url(...)`，前端只展示结果 |
| 桌面端 | Electron / Tauri / PySide 调同步包装 `archive_url_sync(...)` |
| 移动端 | App 调自己的后端接口，由后端复用本项目 API，不把 Cookie 放进移动包 |
| 自动化 | 定时任务调用 `archive_urls_sync(...)` |

## 更多入口

- 终端帮助：`zhihu --help` 或 `zhihu [command] --help`
- 配置检查：`zhihu check`
- 维护者与代码代理：先阅读 [AGENTS.md](AGENTS.md)

<div align="center">
  <sub>Local-first archive tool by Yuchen Zhu Research.</sub>
</div>
