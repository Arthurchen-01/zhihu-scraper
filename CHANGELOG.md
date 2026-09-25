# Changelog

版本号规则：小版本 = +0.1（新增能力/工具）；大版本 = +1（数据契约/交付格式不兼容）。
版本追溯自 v1.1.0 起（此前仓库从未打过 tag，`__version__` 一直停在占位值 "1.0.0"）。

## v1.2.0（2026-09-25）

> 版本跨度：`v1.1.0` → `v1.2.0`（折叠 3 个从未推送的提交：`0f81631` AI 审核换自建中转、`3d2a7ba` Word 导出 + 投票数 + 法·典替换模式、`ae3fab3` v6 自包含执行器 + 下载白名单 + 兜底）
> 基线提交：`2e57efc`（= `v1.1.0`，亦即推送前远端 `origin/main` 的 HEAD）→ 本次发布提交
> 代码量：`git diff v1.1.0 HEAD --numstat`（不含本文件与版本号文件）→ **14 个文件，`+6481 / −376`**

### 上一版（v1.1.0）的代码状态 —— 改之前是什么样

| 文件 / 目录 | v1.1.0 时的状态（逐条实测，非「优化了 X」） |
| :--- | :--- |
| `zhihu_scraper/client.py` | requests 直连**不清理风控 cookie**：知乎种下的 `BEC` / `__zse_ck` 被原样重放 → 6 个 `list_*` 接口全 403（响应体是 `zh-zse-ck` 挑战页 HTML，不是 JSON）→ 分页一页都吐不出来 → **检索条数全 0**，而主页计数仍显示几百篇。也**不识别 10003 限流**（403 + `{"error":{"code":10003}}`）：0.5s 间隔连打约 25 个请求后开始被掐，244 篇文章 = 13 页分页轻松越线 → 「爬一半断掉，每次条数都不一样」。 |
| `zhihu_scraper/app/web.py` | 监听地址写死 `0.0.0.0`（端口直接暴露公网）；**无 `timeout_graceful_shutdown`**（重启 / 长任务收尾时前端拿到 502）；**无凭证诊断** —— 凭证失效时静默返回 0，用户看不出原因；`z_c0` 相关仅 28 处、`api/v4/me` 仅 1 处，**没有登录态活性探针**。 |
| `zhihu_scraper/app/qingyi_api.py` | AI 审核**直连 `api.deepseek.com`**（官方端点，被上游掐）；**无用户端脚本分发**（`qy_client` 命中 0 处）；**无 Word 导出**（`docx` 命中 0 处）；无 `comment_fetch` 评论抓取封装。 |
| `zhihu_scraper/scrapers/author.py` | `get_profile` 单通道（v4 成功即 return，不合并 `api.zhihu.com`）；**不归一 `answers_count`** → v4 不返回该字段时「问答」永远显示 0。 |
| `zhihu_scraper/qingyi.py` | 点赞数（`voteup`）取值不准（仅 3 处命中，且不是真实投票数）。 |
| `zhihu_scraper/qingyi_worker.py` | 无 Word 导出分支。 |
| `zhihu_scraper/docx_exporter.py` | **文件不存在**。 |
| `zhihu_scraper/high_value_essays.py` | **文件不存在**。 |
| `zhihu_scraper/comment_fetch.py` | **文件不存在** —— 文章与回答用的是两套完全不同的评论接口（字段名都不同），此前没有统一封装。 |
| `zhihu_scraper/qy_client.py` | **文件不存在** —— 没有任何本地用户端。 |
| `verify_gate.py` / `zh_archiver.py` / `zh_roundtrip.py` | **均不存在** —— 没有归档完整性门禁、没有全量归档工具、没有端到端往返无损验证。 |
| `README.md` / `VERSION` / `__init__.py` | 版本号一律停在 `1.1.0`。 |

### 本次改动的文件 —— 改了什么

| 文件 | 类型 | 改动行数 | 改了什么 |
| :--- | :--- | ---: | :--- |
| `zhihu_scraper/client.py` | 改 | +172 / −13 | 新增 `MANAGED_CHALLENGE_COOKIES = ("BEC", "__zse_ck")` 并**在 requests 直连路径清除风控 cookie**（与 `browser.py` 已有口径对齐）；新增 `_looks_like_rate_limit()` 识别 403 + code 10003，按 `RATE_LIMIT_BACKOFF = (3, 8, 20)` 三段退避重试。 |
| `zhihu_scraper/app/web.py` | 改 | +287 / −74 | 监听地址改为读 `QY_BIND` 环境变量（systemd 里设 `127.0.0.1`，8775 不再裸奔）；`uvicorn.run(timeout_graceful_shutdown=…)` 修 502；新增**凭证活性探针**（检索前打 `/api/v4/me?include=name,url_token`，用返回体有没有 `name` 判登录态）与 `warnings` / `catalog["credential"]` 回传；前端新增常驻 `credWarn` 诊断横幅；「方式二」指引改为**复制 `z_c0` 值**（旧指引教的 `copy(document.cookie)` 读不到 HttpOnly 的 `z_c0`，是死路）；下载路由白名单 + `?key=` 鉴权。 |
| `zhihu_scraper/app/qingyi_api.py` | 改 | +856 / −124 | AI 审核端点由 `api.deepseek.com` 换到自建中转（`156.225.31.92:7863`，模型 `deepseek-v4.1-flash`，支持 `QY_AI_URL` / `QY_AI_MODEL` 覆盖）；新增**用户端脚本分发**（`_client_source()` / `qy_client_script()` / `qy_client_launcher()`，三级路径兜底 + `QY_CLIENT_SRC`）；新增 Word 导出接口与 `comment_fetch` 接线。 |
| `zhihu_scraper/app/qingyi_page.py` | 改 | +547 / −83 | 工作台页面新增 Word 导出 / 法·典替换模式 UI 与用户端下载入口。 |
| `zhihu_scraper/scrapers/author.py` | 改 | +118 / −11 | `get_profile` 改**双通道合并**（v4 + `api.zhihu.com/people/{token}`）；`answers_count ← answer_count` 归一，修掉「问答永远 0」。 |
| `zhihu_scraper/qingyi.py` | 改 | +266 / −27 | 点赞数（`voteup`）改为真实值；法·典替换模式逻辑。 |
| `zhihu_scraper/qingyi_worker.py` | 改 | +102 / −44 | Word 导出执行分支与兜底。 |
| `zhihu_scraper/docx_exporter.py` | **新** | +500 / −0 | Word 文档导出器（含评论逐条排版，走 `comment_fetch`）。 |
| `zhihu_scraper/high_value_essays.py` | **新** | +376 / −0 | 高价值文章筛选 / 法·典替换文本库。 |
| `zhihu_scraper/comment_fetch.py` | **新** | +263 / −0 | 文章 / 回答两套评论接口的统一封装（文章用 `like_count`，回答用 `vote_count`）。 |
| `zhihu_scraper/qy_client.py` | **新** | +1909 / −0 | 本地用户端 v2.0：多通道凭证（手动粘贴 / 云端凭证柜载入 / 自动检测浏览器）、本地直连拉取 + 云端任务双模式、逐篇人工确认后才写入。 |
| `verify_gate.py` | **新** | +115 / −0 | 归档核对硬门禁：逐篇 SHA-256 校验，任一文件缺失 / 0 字节 / 图片未下全即退出码 1 阻断。 |
| `zh_archiver.py` | **新** | +694 / −0 | 全量归档工具：元数据 + 原始 Draft JSON + body.html + 原图本地化 + 评论 + Playwright 高清截图 + Word。 |
| `zh_roundtrip.py` | **新** | +276 / −0 | 端到端往返无损验证：归档 → 覆写 → 还原 → 在线回读逐字节比对。 |
| `VERSION` / `README.md` / `zhihu_scraper/__init__.py` | 改 | 版本号 | 统一升到 `1.2.0`。 |
| `CHANGELOG.md` | 改 | 本节 | 新增本条目。 |

### Fixed

- **检索条数全 0 的第一层真凶**：requests 直连重放 `__zse_ck` 风控 cookie → 6 个 `list_*` 接口全 403。现已清除。
- **检索条数全 0 的第二层真凶**：页面凭证缺 `z_c0`（HttpOnly，控制台 `document.cookie` 读不到），合并时用服务端已失效的默认 `z_c0` → 403 → 全 0。现指引改为直接复制 `z_c0` 值，并加活性探针 + 常驻诊断横幅。
- **「问答」永远 0**：v4 接口不返回 `answer_count`，现双通道合并 + 字段归一。
- 长任务收尾 / 重启时前端 502（补 `timeout_graceful_shutdown`）。
- 8775 端口裸奔公网（改 `QY_BIND`）。

### Added

- 本地用户端 `qy_client.py` v2.0（逐篇人工确认后才写入知乎）。
- Word（.docx）导出。
- 归档工具链：`zh_archiver.py` / `verify_gate.py` / `zh_roundtrip.py`。
- 评论抓取统一封装 `comment_fetch.py`。
- AI 审核支持自建中转 + 环境变量覆盖。

### Verified

- 四情景真机复现（线上 `/api/inspect`，2026-09-25）：全量真实 cookie → **63 条**（文章 50 / 想法 10 / 问答 3）；空 cookie → 0；**仅设备 cookie（用户实际情形）→ 0**，精确复现；**只粘一个 `z_c0` → 63 条**，证明新指引可用。
- `client.py` 风控对比（2026-09-25，真实用户 cookie，服务器 IP）：完整 cookie → 6 接口全 403；完整 cookie − `__zse_ck` → 6 接口全 200；只留 `z_c0` → 6 接口全 200。
- 线上 `md5` 三方一致：`web.py` = `35d400e1b31494a67a5229f5cfd5b93b`、`author.py` = `51a363dab8c3ec49989a0221209cd741`。
- 本地硬校验：渲染串抽内联 `<script>` 逐个 `node --check` 全绿；旧文案（`已读取基础设备凭证` / `1秒控制台口诀`）在线上归零。

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
