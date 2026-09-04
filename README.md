# 🥋 Zhihu Scraper & Target Investigator Toolkit
> **知乎全维信息爬虫、定向资产排查与高保真法务存证架构**  
> 纯净抓取内核 · 交互式Web自服务看板 · 跨环境 AI Skill (Codex / Cursor / Antigravity)

---

## 🌟 核心功能特性

### 1. 全维知乎信息抓取内核 (`zhihu_scraper`)
* 👤 **作者全资产编目 (`AuthorScraper`)**：输入任意知乎主页直链（如 `/people/xxx`），快速抓取其个人画像（获赞、粉丝、签名）并全量编目其名下的**所有专栏、所有文章、所有回答、所有想法**；
* 📚 **专栏文章全量下载 (`ColumnScraper`)**：输入专栏链接（`/column/xxx`），自动枚举内部全部文章，一键保存 Markdown 与纯文本；
* 📝 **正文格式洁净转换 (`ArticleScraper` / `AnswerScraper` / `PinScraper`)**：剥离噪音 DOM，保留排版、原图链接、代码块与元数据；
* 💬 **楼中楼多级评论树抓取 (`CommentScraper`)**：递归爬取根评论与子回复，导出树状 JSON，确保法务跟帖证据链完整；
* 📸 **Playwright 高保真长截图 (`VisualArchiver`)**：无头浏览器物理渲染，自动消除 Cookie 遮罩与弹窗，支持对目标敏感词自动添加**红色矩形方框（Bounding Box）**高亮标注。

### 2. 交互式 Web 排查看板 (`zhihu_scraper.app.web`)
专为团队协作与同学自服务设计：
1. **输入目标**：粘贴任意知乎个人主页或专栏链接；
2. **凭证隔离**：同学可粘贴自己的 Cookie 避开限流，亦可留空使用公共凭证；
3. **资产清单即时展示（Checklist）**：秒级返回该作者名下的全部文章与专栏列表，支持全选或按需单选；
4. **实时进度条与日志**：SSE 实时事件流，动态展示 `0% -> 100%` 进度与当前操作；
5. **一键 ZIP 打包下载**：任务完成后自动生成 ZIP 压缩包，内含所有选定文章的 Markdown、评论 JSON 与现场截图。

### 3. 通用 AI Agent Skill (`skills/zhihu-scraper-investigator`)
无缝兼容并已注入到以下 AI 编程与代理环境：
* **Antigravity** (`~/.gemini/config/skills/zhihu-scraper-investigator`)
* **Codex** (`~/.codex/skills/zhihu-scraper-investigator`)
* **Cursor** (`~/.cursor/skills-cursor/zhihu-scraper-investigator`)
* **Agents** (`~/.agents/skills/zhihu-scraper-investigator`)

> 换新电脑时，只需运行 `scripts/install_skills.bat`（Windows）或 `bash scripts/install_skills.sh`（Mac/Linux），一秒完成跨电脑 Skill 迁移！

---

## 📂 项目结构概览

```text
.
├── zhihu_scraper/                      # 核心 Python 爬虫框架
│   ├── client.py                       # 统一 HTTP 客户端（请求头轮换、重试、分页）
│   ├── scrapers/
│   │   ├── author.py                   # 作者信息与全资产枚举
│   │   ├── column.py                   # 专栏与专栏文章批量下载
│   │   ├── article.py                  # 单篇文章正文抓取
│   │   ├── answer.py                   # 问答内容抓取
│   │   ├── pin.py                      # 想法内容抓取
│   │   └── comment.py                  # 楼中楼嵌套评论树抓取
│   ├── visual/
│   │   └── screenshot.py               # Playwright 高清长截图与红框标注
│   └── app/
│       └── web.py                      # 自服务 Web 看板与进度条交互应用 (端口 8775)
├── skills/
│   └── zhihu-scraper-investigator/     # 通用 Agent Skill
│       ├── SKILL.md                    # 技能行为规范与指令提示词
│       └── scripts/
│           └── run_investigation.py    # Skill 命令行执行脚本
├── scripts/
│   ├── install_skills.bat              # Windows 一键将 Skill 注入全环境
│   ├── install_skills.sh               # Linux/macOS 一键注入脚本
│   └── run_web.bat                     # Windows 启动本地 Web 看板
├── cloud_daemon.py                     # 云端 7x24h 持续监控守护引擎
├── cloud_web_server.py                 # 云端监控大盘 (端口 8770)
├── config.example.json                 # 关键词与凭证配置示例
└── pyproject.toml                      # 依赖管理 (uv / pip)
```

---

## 🚀 快速上手

### 1. 启动 Web 交互界面
```bash
python -m zhihu_scraper.app.web
# 浏览器访问 http://localhost:8775
```

### 2. Python 代码直接调用
```python
from zhihu_scraper import ZhihuClient, AuthorScraper, ArticleScraper, VisualArchiver
from pathlib import Path

client = ZhihuClient(cookie="YOUR_COOKIE_HERE")

# 1. 检索作者名下所有专栏与文章
author_scraper = AuthorScraper(client)
catalog = author_scraper.catalog_all_assets("https://www.zhihu.com/people/shou-qi-hei")
print(f"找到 {len(catalog['items'])} 篇内容")

# 2. 抓取单篇文章正文与高清截图
art_scraper = ArticleScraper(client)
art_scraper.scrape("1931445943309427470", save_dir=Path("./outputs/articles"))

visual = VisualArchiver(cookie="YOUR_COOKIE_HERE")
visual.capture_screenshot(
    "https://zhuanlan.zhihu.com/p/1931445943309427470",
    output_path=Path("./outputs/screenshots/evidence.png"),
    highlight_keywords=["违规", "造谣"]
)
```

### 3. 跨电脑一键安装 Skill
在任何新设备上克隆本仓库后执行：
```bash
scripts/install_skills.bat       # Windows
# 或
bash scripts/install_skills.sh   # Linux / macOS
```
Codex、Cursor 与 Antigravity 即可立刻识别并启用该 Skill！
