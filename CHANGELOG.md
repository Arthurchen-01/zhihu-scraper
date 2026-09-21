# Changelog

版本号规则：小版本 = +0.1（新增能力/工具）；大版本 = +1（数据契约/交付格式不兼容）。
版本追溯自 v1.1.0 起（此前仓库从未打过 tag，`__version__` 一直停在占位值 "1.0.0"）。

## v1.1.0（2026-09-20）

### 上一版是什么样（before）

- 仓库**从未打过 tag**，没有 `VERSION`、没有 `CHANGELOG.md`；
  `zhihu_scraper/__init__.py` 的 `__version__ = "1.0.0"` 是初始占位值，从未随真实进度更新。
- 上一版代码 = 知乎全维爬虫内核（作者/专栏/文章/回答/想法/楼中楼评论/Playwright 长截图取证）
  + 交互式 Web 排查看板（`zhihu_scraper.app.web`）+ AI Skill 适配层，仅此而已。
- 清一新教育文章修改工作台的代码虽已逐轮提交（自基线 `5f50b8d` 起），但从未以版本形式发布过。

### 这次改了哪些（基线 5f50b8d → a25b185）

**91 个文件变更，+18058 / -17 行。** 核心新增 = 「清一新教育文章修改工作台」整套子系统，
架构为控制面/数据面分离：云端只计算与缓存、永不写知乎；写入永远在用户本机执行器完成；
云端再回读线上文章做独立复核。无数据契约变更 → 按口径定为小版本 1.0.0 → 1.1.0。

主要新增/修改文件（`git diff --numstat 5f50b8d..HEAD` 实测）：

| 文件 | 变更 | 说明 |
|---|---|---|
| `zhihu_scraper/app/qingyi_page.py` | +2416 | 工作台页面，v13.2 设计系统（六道闸门原子流、新手引导气泡、toast 轻提示） |
| `qingyi-workbench/验收报告.html` | +2286 | 交付验收报告（13 轮迭代、22 张截图记录） |
| `zhihu_scraper/app/qingyi_api.py` | +1935 | FastAPI 控制面 `/api/qy/*`（任务/审计/payload 下发/verify 复核/一键包下载，含 Mac 部署脚本） |
| `qingyi-workbench/patches/qingyi_executor.py` | +1421 | 本地执行器源码（Windows exe 内核，六道闸门 + 本地写入） |
| `zhihu_scraper/qingyi.py` | +880 | 云端任务调度核心 |
| `clients/qingyi_deploy.py` | +700 | 部署/打包客户端 |
| `zhihu_scraper/qingyi_worker.py` | +637 | 异步 worker |
| `qingyi-workbench/patches/_upgrade_report_ui.py` | +663 | 验收报告 UI 升级脚本 |
| `清一新教育文章修改工作台_总控与需求交接.md` | +491 | 需求总控文档（唯一入口） |
| `zhihu_scraper/qingyi_jobs.py` | +438 | 任务状态机 |
| `qingyi-workbench/patches/_upgrade_page_ui.py` | +420 | 工作台页面 UI 升级脚本 |
| `zhihu_scraper/qy_content.py` | +259 | 终稿内容生成 |
| `zhihu_scraper/app/web.py` | +131/-17 | 看板接入清一入口；修复根页面三处 JS 语法错误导致的整页报废（Vue 无法挂载，页面裸模板 + 弹窗糊脸），加固 v-cloak + 启动兜底横幅 + 门禁「这是干嘛的」说明卡 |
| `qingyi-workbench/`（其余） | — | 17 张验收截图 + 30 个补丁/同步/推送脚本 |
| `qingyi_extension/`（扩展） | — | 浏览器扩展配套（`background.js` +249 起） |

本版本号提交本身：新增 `VERSION`（1.1.0）与 `CHANGELOG.md`（本文件），`README.md` 头部加版本行，
`zhihu_scraper/__init__.py` 的 `__version__` 由占位 "1.0.0" 对齐为 "1.1.0"。
