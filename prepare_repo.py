"""Copy Master Deliverables into repository and generate comprehensive README.md."""

import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"C:\Users\25472\Desktop\AI brain storming\工具栏\zhihu-black")
DESKTOP_SRC = Path(r"C:\Users\25472\Desktop\清一武道馆")
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 复制核心报表
copy_targets = [
    "1_官方核心团队与保护白名单.xlsx",
    "2_全网真实黑子与侵权人知乎主页总汇表.xlsx",
    "和律师商定版-收集清黑文章链接汇总表-最终.xlsx"
]

for item in copy_targets:
    src = DESKTOP_SRC / item
    if src.exists():
        dst = DATA_DIR / item
        shutil.copyfile(src, dst)
        print(f"✓ 复制核心资产到仓库: {item}")

# 创建标准 README.md
readme_content = """# 🥋 知乎全网舆情监控、存证与黑子穿透系统 (Zhihu Scraper & Evidence Archiver)

针对知乎平台的 **7x24小时全网舆情监控、黑粉恶意言论爬取、楼中楼评论树穿透、高保真现场截图与法务标准卷宗归档** 一体化系统。

---

## 🌟 核心功能特性

1. **双轨数据采集引擎**：
   - **全网关键词地毯式扫描**：持续轮询品牌关键词、恶意暗语、缩写隐语；
   - **重点黑号定向主页穿透**：地毯式监控重点黑号名下全部专栏文章、问答、想法与互动跟帖。
2. **严密的安全白名单门禁**：
   - 内置创办人、核心教练、文人格斗主力运动员及排查战友白名单，100% 豁免防护，杜绝误伤己方宣传文章。
3. **闭环法务级存证取证**：
   - **文章全文留底**：DOM 树 + 原生 HTML + 纯文本 Markdown 永久落盘；
   - **盖楼评论树**：抓取并固化楼中楼全部嵌套回复 JSON；
   - **Playwright 高保真长截图**：真实浏览器渲染，自动用红方框（Bounding Box）高亮标注侵权段落；
   - **律师标准 Excel 出表**：自动对齐 8 列律师标准诉讼格式。
4. **云端 24h 守护与 Web 交互大盘**：
   - Linux 后台常驻 `systemd` 守护进程；
   - 8770 端口实时 Web 看板，支持一键导出 Excel/CSV 报表。

---

## 📂 仓库核心架构

```text
.
├── cloud_daemon.py             # 云端 7x24 小时监控守护主程序 (SQLite持久化)
├── cloud_web_server.py          # FastAPI 实时大盘看板 (端口 8770)
├── zhihu_client.py              # 知乎 API 与页面 DOM 解析核心客户端
├── nlp_classifier.py            # 语义负向分析与规则引擎
├── author_tracer.py             # 攻击者人物画像与关联追踪
├── ai_deep_audit.py             # AI 深度立场审计器
├── evidence_archiver.py         # 证据归档与律师 8 列格式导出引擎
├── batch_archive_fulltext_and_screenshots.py # Playwright 批量截图与全文留存
├── cloud_sync_service.py        # 云端至本地一键增量同步服务
├── zhihu-monitor.service        # Linux Systemd 爬虫守护单元
├── zhihu-web.service            # Linux Systemd Web 服务单元
├── config.json                  # 关键词、暗语、品牌词与 Cookie 配置
├── data/
│   ├── zhihu_monitor.db         # 【核心 SQLite 数据库】包含 567+ 条黑帖与 178 位嫌疑人画像
│   ├── 1_官方核心团队与保护白名单.xlsx
│   ├── 2_全网真实黑子与侵权人知乎主页总汇表.xlsx
│   └── 和律师商定版-收集清黑文章链接汇总表-最终.xlsx
└── install_cloud.sh             # Linux 服务器一键极速安装脚本
```

---

## 🚀 服务器一键部署指南

### 1. 克隆代码
```bash
git clone https://github.com/Arthurchen-01/zhihu-scraper.git
cd zhihu-scraper
```

### 2. 环境初始化 (推荐 uv 或 Python 3.10+)
```bash
pip install -r pyproject.toml  # 或 uv sync
playwright install chromium
playwright install-deps
```

### 3. 配置 Cookie 与关键词
编辑 `config.json`，填入最新的有效知乎 Cookie。

### 4. 启动后台常驻服务
```bash
# 前台调试运行
python cloud_web_server.py  # 启动 Web 大盘 (http://0.0.0.0:8770)
python cloud_daemon.py      # 启动 24h 监控爬虫

# 或使用 systemd 守护运行
sudo cp zhihu-monitor.service /etc/systemd/system/
sudo cp zhihu-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now zhihu-monitor zhihu-web
```

---

## 📊 当前数据库指标 (data/zhihu_monitor.db)
- **侵权证据明细**：567 条
- **锁定可疑黑号**：178 人
- **诉讼标准报表**：已完全对齐
"""

(ROOT / "README.md").write_text(readme_content, encoding="utf-8")
print("✅ README.md 编写完成！")
