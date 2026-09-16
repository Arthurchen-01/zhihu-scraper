# ⚡ Scraper API 与 MCP 智能体接入规范指南

本文档全面规范 Scraper 知乎定向排查与批量存证系统的两大对外开放能力：
1. **HTTP RESTful API**（适合 cURL、Python、Node.js、微服务调用）
2. **Anthropic Model Context Protocol (MCP) Server**（适合 Claude Desktop、Cursor、Cline、Antigravity 等 AI 智能体零配置接入）

---

## 🔑 核心接入凭据 (Master Credentials)

无论使用 REST API 还是 MCP，统一采用主安全凭据鉴权：
* **生产环境 Base URL**: `https://zh.samuraiguan.cloud`
* **主鉴权密码 (API Key)**: `guanjun2026`
* **支持的请求头 (Headers)**:
  * `Authorization: Bearer guanjun2026`
  * 或 `X-API-Key: guanjun2026`
  * 或 `X-Auth-Token: 5937bbba30953a1e94fc1fa454378f7e`

---

## 🔌 第一部分：RESTful API 接入规范

### 1. 智能穿透检索创作者主页或专栏 (`POST /api/inspect`)

输入任意知乎链接（包括个人主页、某条想法、单个回答、专栏主页或单篇文章），系统自动进行**双向穿透**：
- 输入主页：提取该作者的全量文章、想法、专栏与动态；
- 输入想法/回答/文章：自动穿透溯源到底层创作者，提取其个人主页全量资产；
- 支持深度拉取参数 `max_items` (0 为全量，300 为深度，100 为标准)。

#### 请求示例 (cURL)
```bash
curl -X POST "https://zh.samuraiguan.cloud/api/inspect" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer guanjun2026" \
  -d '{
    "url": "https://www.zhihu.com/pin/2079702939531321857",
    "max_items": 100,
    "drill_column": false
  }'
```

#### Python 调用示例
```python
import requests

url = "https://zh.samuraiguan.cloud/api/inspect"
headers = {
    "Authorization": "Bearer guanjun2026",
    "Content-Type": "application/json"
}
payload = {
    "url": "https://www.zhihu.com/people/zhang-qing-yi-78",
    "max_items": 50,
    "drill_column": False
}

resp = requests.post(url, json=payload, headers=headers)
data = resp.json()

print(f"目标类型: {data.get('target_type')}")
print(f"作者姓名: {data.get('author', {}).get('name')}")
print(f"检索到的资产条数: {len(data.get('items', []))}")
```

---

### 2. 批量存证归档任务提交 (`POST /api/scrape/batch`)

提交批量抓取任务，后端在后台异步抓取并生成正文 Markdown、评论树 JSON、原生截图，并打包输出高清 PDF、精美 EPUB 电子书与 ZIP 存证包。

#### 请求示例 (cURL)
```bash
curl -X POST "https://zh.samuraiguan.cloud/api/scrape/batch" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer guanjun2026" \
  -d '{
    "items": [
      {
        "id": "2079668307335050654",
        "type": "article",
        "title": "张清一原创：木兰明晓世运会打入半决赛"
      }
    ],
    "options": {
      "export_formats": ["pdf", "epub", "zip"],
      "save_markdown": true,
      "save_comments": true,
      "save_screenshot": true
    }
  }'
```

响应：
```json
{
  "job_id": "job_20260916_143000_abcd12",
  "status": "pending",
  "total": 1,
  "message": "批量存证任务已提交，包含导出格式: ['pdf', 'epub', 'zip']"
}
```

---

### 3. 任务状态与实时进度监听 (`GET /api/jobs/{job_id}/stream` & `/status`)

#### SSE 实时流式进度
```javascript
const evtSource = new EventSource("https://zh.samuraiguan.cloud/api/jobs/{job_id}/stream");
evtSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`进度: ${data.current}/${data.total} [${data.status}] - ${data.current_item_title}`);
    if (data.status === "completed") {
        evtSource.close();
    }
};
```

---

### 4. 存证交付物下载接口

当任务完成后，可通过以下接口下载对应格式存证文件：
- **高清矢量排版 PDF**: `GET https://zh.samuraiguan.cloud/api/jobs/{job_id}/download_pdf`
- **精美移动阅读 EPUB**: `GET https://zh.samuraiguan.cloud/api/jobs/{job_id}/download_epub`
- **全套完整存证 ZIP 包**: `GET https://zh.samuraiguan.cloud/api/jobs/{job_id}/download`

---

## 🤖 第二部分：MCP (Model Context Protocol) 智能体接入

Scraper 内置 Anthropic 标准 MCP Server：`zhihu_scraper.mcp_server`。
代码完全零三方重度依赖，基于 Python 标准库 `urllib` / `json` 实现，支持跨平台一键启动。

### 1. Claude Desktop 接入配置

编辑 Claude Desktop 配置文件：
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

添加如下配置节：
```json
{
  "mcpServers": {
    "zhihu-scraper": {
      "command": "python",
      "args": ["-m", "zhihu_scraper.mcp_server"],
      "env": {
        "ZHIHU_API_BASE": "https://zh.samuraiguan.cloud",
        "ZHIHU_API_KEY": "guanjun2026"
      }
    }
  }
}
```

---

### 2. Cursor 接入配置

在项目根目录或全局创建 `.cursor/mcp.json`：
```json
{
  "mcpServers": {
    "zhihu-scraper": {
      "command": "python",
      "args": ["-m", "zhihu_scraper.mcp_server"],
      "env": {
        "ZHIHU_API_BASE": "https://zh.samuraiguan.cloud",
        "ZHIHU_API_KEY": "guanjun2026"
      }
    }
  }
}
```

---

### 3. Cline / Roo Code / Antigravity 接入配置

在 `mcpSettings.json` 中配置：
```json
{
  "mcpServers": {
    "zhihu-scraper": {
      "command": "python",
      "args": ["-m", "zhihu_scraper.mcp_server"],
      "env": {
        "ZHIHU_API_BASE": "https://zh.samuraiguan.cloud",
        "ZHIHU_API_KEY": "guanjun2026"
      }
    }
  }
}
```

---

## 🛠️ MCP 工具清单与参数定义 (Tools Schema)

### 工具 1: `zhihu_inspect`
* **说明**: 输入任意知乎链接（主页、想法、回答、专栏或文章），智能穿透溯源创作者，返回资产目录清单。
* **参数**:
  * `url` *(string, 必填)*: 目标知乎 URL。
  * `max_items` *(integer, 可选, 默认 50)*: 拉取条数上限（0 为全量）。
  * `drill_column` *(boolean, 可选, 默认 false)*: 若为 true 且输入专栏，则只检索该专栏内容。

### 工具 2: `zhihu_batch_archive`
* **说明**: 对检索出的文章或想法进行批量存证归档，支持生成 PDF、EPUB 与 ZIP。
* **参数**:
  * `items` *(array of objects, 必填)*: 待存证的项目列表，每项需包含 `id`, `type`, `title`。
  * `export_formats` *(array of string, 可选, 默认 ["pdf", "epub", "zip"])*: 导出格式。

### 工具 3: `zhihu_get_article`
* **说明**: 单篇知乎专栏文章正文 Markdown 与元数据秒级直提。
* **参数**:
  * `article_id_or_url` *(string, 必填)*: 知乎专栏文章 ID 或完整 URL。

---

## 🌐 第三部分：独立文档页面

系统在 Web 端提供了独立的无密码公开接入文档页面：
* **在线独立页面**: `https://zh.samuraiguan.cloud/api-docs`
* **Web 控制台直接访问**: 点击页面顶部导航栏 **【⚡ API / MCP 接入】** 按钮即可一键弹出交互式接入面板。
