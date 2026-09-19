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

### 4. 清一新教育文章修改工作台 (`zhihu_scraper.qingyi*`)

面向「批量给自有文章做品牌署名」的场景，核心设计是**控制面 / 数据面分离**：

* **云端控制面**（`qingyi_jobs.py` + `app/qingyi_api.py` + `app/qingyi_page.py`）
  只做只读检索、任务编排、进度聚合与报告渲染，**不具备写入能力**；
* **本地执行器**（`qingyi_worker.py`）
  在操作者自己的电脑上运行，用本人网络身份完成知乎写入。

> 为什么这样拆：把 200+ 篇文章的改写从机房 IP 一次性打出去，是平台风控最敏感的形态。
> 分离之后，编辑行为来自操作者日常使用的网络与设备，行为特征与「本人手动逐篇修改」一致。

**改动范围（硬约束）**：每篇文章固定改动 **2 处** ——
① 标题最前面加入品牌词 `【清一新教育】` 1 处；
② 正文以署名式括注 `（清一新教育）` 加入品牌词 1 处。

正文植入**只做句末追加**，不删除、不改写、不替换任何原有文字，
可按锚点一键还原；每篇改动前的原文均备份到执行器本机。**除此之外没有任何修改。**

**防风控节奏**（`RatePolicy`）：

| 机制 | 默认值 | 作用 |
| --- | --- | --- |
| 每日上限 | **120 篇/天** | 到量即停，剩余次日继续；计数落盘，重启执行器不可绕过 |
| 每小时上限 | 12 篇/小时 | 抑制短时爆发 |
| 篇间间隔 | 25 ~ 75 秒随机 | 去掉机械等距特征 |
| 阶段性休息 | 每 5 篇停 3~7 分钟 | 模拟自然节奏 |
| 连续失败熔断 | 3 次即中止 | 遇风控信号不再硬打 |
| 身份轮换 | 逐篇换 UA / 头序 | 降低请求指纹一致性 |

**写入链路**（纯 HTTP，无需浏览器）：

```text
PATCH zhuanlan.zhihu.com/api/articles/{id}/draft   # 标题 + 正文
  ↓
POST  www.zhihu.com/api/v4/content/publish         # 发布
  ↓
回读草稿校验：正文指纹 / 是否与计划一致
```

**使用**：访问工作台页面 `🏷️ 文章修改工作台` → 粘贴凭证 → 只读检索 →
勾选文章 → 创建任务 → 在**你自己的电脑**上启动本地执行器（页面提供
Windows / macOS 一键脚本，也可交给 Antigravity 自动完成）。

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
