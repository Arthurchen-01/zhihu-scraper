<div align="center">

# Zhihu-Scraper
**知乎本地归档，从未如此优雅**

<p>
  <img src="https://github.com/yuchenzhu-research/zhihu-scraper/actions/workflows/ci.yml/badge.svg" alt="CI Badge" />
  <img src="https://img.shields.io/static/v1?label=python&message=3.14%2B&color=3776AB&style=flat-square&logo=python&logoColor=white" alt="Python Badge" />
  <img src="https://img.shields.io/github/license/yuchenzhu-research/zhihu-scraper?style=flat-square" alt="License Badge" />
</p>

<p>
  <strong>简体中文</strong> · <a href="README_EN.md">English</a>
</p>

</div>

Zhihu-Scraper 是一个**本地优先**的抓取归档工具。输入一条链接，即可自动提取正文与元数据、下载原图，并原生地转换为高清 Markdown 和 SQLite 索引库长期保存。

它是面向命令行工作流的最佳搭档，拒绝云端绑定，数据彻底归属自己。

> [!WARNING]  
> 本项目仅用于学习、研究、个人归档与技术交流。请遵守服务条款、爬虫约束和当地法律法规。

> [!NOTE]
> 当前项目收束在 `v3.0.1-final`。后续不再承诺持续适配知乎接口、页面结构或风控变化；已导出的 Markdown、图片和 SQLite 数据仍是主要长期价值。

<br>

## 🚀 快速开始

先克隆仓库，并用一键脚本完成安装与本地运行目录初始化：

```bash
# 1. 克隆并进入目录
git clone https://github.com/yuchenzhu-research/zhihu-scraper.git && cd zhihu-scraper

# 2. 运行一键安装（自动创建虚拟环境与安装所有依赖）
./install.sh
```

### macOS / Linux

```bash
# macOS 默认常用 python3；本项目要求 Python 3.14+
python3 --version

# 安装脚本会创建 .venv，并尝试安装全局 zhihu 命令
./install.sh

# 当前终端 PATH 未刷新时，先用仓库内兜底入口
./zhihu check
./zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

如果重新打开终端后 `zhihu` 已可用，也可以直接运行：

```bash
zhihu
zhihu check
zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

### Windows

Windows 用户建议使用 PowerShell，并优先通过 WSL 或等价的 Python 3.14+ 环境运行：

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

### 配置 Cookie

安装脚本会从 `cookies.example.json` 创建 `.local/cookies.json`。如需登录态抓取，请在浏览器登录知乎后，把自己的 `z_c0` 和 `d_c0` 填入 `.local/cookies.json`，再运行：

```bash
./zhihu check
./zhihu fetch "https://www.zhihu.com/question/28696373/answer/2835848212"
```

## ✨ 核心能力

- **单链归档**：支持回答、问题页（Top 抓取）、专栏、创作者主页等当前已验证路径。
- **本地至上**：直接写出 `Markdown`文件、离线图片目录 (Images) 与 `SQLite`元数据。
- **协议优先**：默认走 API / HTML 协议路径，专栏等复杂页面可尝试浏览器回退。
- **增量监控**：`monitor` 命令可基于本地状态文件检查收藏夹新增内容。
- **Textual TUI**：提供全屏工作台、任务队列、最近结果、失败重试和语言切换。

## 🧭 命令速览

```bash
zhihu                         # 打开 Textual TUI 全屏工作台
zhihu fetch URL               # 抓取单条链接
zhihu fetch --file urls.txt   # 从文件批量抓取
zhihu creator PEOPLE_URL      # 归档创作者主页内容
zhihu monitor COLLECTION_ID   # 增量监控收藏夹
zhihu query KEYWORD           # 检索本地 SQLite 归档
zhihu interactive             # 显式打开交互式工作台
zhihu config                  # 查看当前配置
zhihu check                   # 检查本地运行环境
```

## 📚 详细文档与配置

想要了解每个命令的用法？

- 终端帮助：直接运行 `zhihu --help` 或 `zhihu [command] --help`
- 配置检查：运行 `zhihu check`，查看 Cookie、配置文件和浏览器依赖状态
- 维护者与代码代理请先阅读 [CONSTITUTION.md](CONSTITUTION.md) 与 [AGENTS.md](AGENTS.md)

<br>

<div align="center">
  <sub>Built with ❤️ by Yuchen Zhu Research.</sub>
</div>
