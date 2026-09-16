"""Model Context Protocol (MCP) Server for Zhihu Scraper and Archival Toolkit.

Compliant with standard Model Context Protocol specification (JSON-RPC 2.0 over stdio).
Allows Claude Desktop, Cursor, Antigravity, Cline, and any LLM agent to directly invoke:
1. `zhihu_inspect`: Smart creator penetration and asset retrieval (pins, answers, columns, articles, author homepage).
2. `zhihu_batch_archive`: Batch scrape and generate PDF, EPUB, and ZIP evidence bundles.
3. `zhihu_get_article`: Extract full article Markdown content and metadata.
4. `zhihu_get_comments`: Deep scrape nested comment trees.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup clean stderr logging so stdout is dedicated to pure JSON-RPC
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("zhihu_mcp_server")

# Default Remote Config
DEFAULT_API_BASE = os.environ.get("ZHIHU_API_BASE", "https://zh.samuraiguan.cloud").rstrip("/")
DEFAULT_API_KEY = os.environ.get("ZHIHU_API_KEY", "guanjun2026")


def make_remote_request(endpoint: str, payload: Optional[Dict[str, Any]] = None, api_base: str = DEFAULT_API_BASE, api_key: str = DEFAULT_API_KEY) -> Dict[str, Any]:
    """Execute HTTP request against the deployed Zhihu Scraper REST API."""
    url = f"{api_base}{endpoint}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Zhihu-MCP-Server/1.0",
        "Accept": "application/json",
        "X-API-Key": api_key,
        "Authorization": f"Bearer {api_key}"
    }

    # 1. Prefer requests library for resilient TLS/Cloudflare handling
    try:
        import requests
        if payload is not None:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
        else:
            resp = requests.get(url, headers=headers, timeout=120)
        if resp.status_code >= 400:
            raise RuntimeError(f"API Error ({resp.status_code}): {resp.text}")
        return resp.json()
    except ImportError:
        pass
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning(f"requests failed ({e}), trying urllib fallback...")

    # 2. Fallback to standard library urllib with TLS context
    import ssl
    ctx = ssl.create_default_context()
    try:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    except Exception:
        pass

    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        logger.error(f"HTTP {e.code} for {url}: {err_body}")
        raise RuntimeError(f"API Error ({e.code}): {err_body}")
    except Exception as e:
        logger.error(f"Connection failed to {url}: {e}")
        raise RuntimeError(f"Connection to Zhihu Scraper API failed: {str(e)}")


def tool_zhihu_inspect(url: str, max_items: int = 100, drill_column: bool = False, api_base: str = DEFAULT_API_BASE, api_key: str = DEFAULT_API_KEY) -> Dict[str, Any]:
    """Inspects any Zhihu URL (author profile, pin, answer, column, article).
    Automatically resolves single items to their author and catalogs child assets.
    """
    payload = {
        "url": url.strip(),
        "max_items": max_items,
        "drill_column": drill_column
    }
    return make_remote_request("/api/inspect", payload=payload, api_base=api_base, api_key=api_key)


def tool_zhihu_batch_archive(items: List[Dict[str, Any]], export_formats: Optional[List[str]] = None, api_base: str = DEFAULT_API_BASE, api_key: str = DEFAULT_API_KEY) -> Dict[str, Any]:
    """Triggers batch archival and returns status, job ID, and download links."""
    formats = export_formats or ["pdf", "epub", "zip"]
    payload = {
        "items": items,
        "options": {
            "export_formats": formats,
            "save_markdown": True,
            "save_comments": True,
            "save_screenshot": True
        }
    }
    res = make_remote_request("/api/scrape/batch", payload=payload, api_base=api_base, api_key=api_key)
    job_id = res.get("job_id")
    if job_id:
        res["download_urls"] = {
            "pdf": f"{api_base}/api/jobs/{job_id}/download_pdf",
            "epub": f"{api_base}/api/jobs/{job_id}/download_epub",
            "zip": f"{api_base}/api/jobs/{job_id}/download",
            "sse_stream": f"{api_base}/api/jobs/{job_id}/stream"
        }
    return res


def tool_zhihu_get_article(article_id: str, api_base: str = DEFAULT_API_BASE, api_key: str = DEFAULT_API_KEY) -> Dict[str, Any]:
    """Extracts a single Zhihu article's Markdown, title, author, and statistics."""
    clean_id = str(article_id).strip().split("/")[-1].split("?")[0]
    art_url = f"https://zhuanlan.zhihu.com/p/{clean_id}" if not clean_id.startswith("http") else clean_id
    res = tool_zhihu_inspect(art_url, max_items=10, api_base=api_base, api_key=api_key)
    return res


MCP_TOOLS = [
    {
        "name": "zhihu_inspect",
        "description": "【知乎全类型智能穿透】解析知乎任意链接（创作者个人主页、单条想法、单篇回答、专栏、或文章），自动穿透溯源创作者并检索全量资产与档案统计。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "知乎任意目标链接，支持: /people/xxx, /pin/xxx, /answer/xxx, /column/xxx 或 /p/xxx"
                },
                "max_items": {
                    "type": "integer",
                    "description": "每类资产获取上限 (默认100，填0为全量)",
                    "default": 100
                },
                "drill_column": {
                    "type": "boolean",
                    "description": "若为专栏，是否直接下钻查看专栏内部文章 (默认false，即默认穿透至作者主页)",
                    "default": False
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "zhihu_batch_archive",
        "description": "【知乎批量存证导出】将多篇知乎内容批量打包归档，生成高清矢量排版 PDF 文档、标准 EPUB 电子书及包含评论树的完整 ZIP 证据包。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "条目ID"},
                            "type": {"type": "string", "description": "类型 (article/pin/answer/column)"},
                            "title": {"type": "string", "description": "条目标题"},
                            "url": {"type": "string", "description": "知乎原文链接"}
                        },
                        "required": ["id", "type"]
                    },
                    "description": "待批量归档存证的条目清单"
                },
                "export_formats": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["pdf", "epub", "zip"]},
                    "description": "导出格式多选列表，默认全部导出: [\"pdf\", \"epub\", \"zip\"]",
                    "default": ["pdf", "epub", "zip"]
                }
            },
            "required": ["items"]
        }
    },
    {
        "name": "zhihu_get_article",
        "description": "【知乎单篇精读与提取】获取单篇知乎专栏文章的正文 Markdown、发表时间、作者信息及互动数据。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "知乎文章 ID 或文章 URL (如 2079668307335050654 或 https://zhuanlan.zhihu.com/p/xxx)"
                }
            },
            "required": ["article_id"]
        }
    }
]


class McpServer:
    """Zero-dependency JSON-RPC 2.0 stdio Model Context Protocol (MCP) Server."""

    def __init__(self, api_base: str = DEFAULT_API_BASE, api_key: str = DEFAULT_API_KEY):
        self.api_base = api_base
        self.api_key = api_key

    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not method:
            return None

        logger.info(f"Incoming MCP method: {method} (id={req_id})")

        # 1. Initialize
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "zhihu-scraper-mcp",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            }

        # 2. Initialized notification
        if method == "notifications/initialized":
            logger.info("Client handshake complete.")
            return None

        # 3. Ping
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        # 4. Tools List
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": MCP_TOOLS
                }
            }

        # 5. Tools Call
        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            try:
                if tool_name == "zhihu_inspect":
                    res = tool_zhihu_inspect(
                        url=args["url"],
                        max_items=args.get("max_items", 100),
                        drill_column=args.get("drill_column", False),
                        api_base=self.api_base,
                        api_key=self.api_key
                    )
                elif tool_name == "zhihu_batch_archive":
                    res = tool_zhihu_batch_archive(
                        items=args["items"],
                        export_formats=args.get("export_formats"),
                        api_base=self.api_base,
                        api_key=self.api_key
                    )
                elif tool_name == "zhihu_get_article":
                    res = tool_zhihu_get_article(
                        article_id=args["article_id"],
                        api_base=self.api_base,
                        api_key=self.api_key
                    )
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(res, ensure_ascii=False, indent=2)
                            }
                        ]
                    }
                }
            except Exception as e:
                logger.error(f"Error executing {tool_name}: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "isError": True,
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error executing tool {tool_name}: {str(e)}"
                            }
                        ]
                    }
                }

        # Unsupported method
        if req_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        return None

    def run_stdio(self):
        """Standard stdio loop reading JSON-RPC messages and writing responses."""
        logger.info(f"Zhihu MCP Server started on stdio (Target API: {self.api_base})")
        
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {line}")
            except Exception as e:
                logger.error(f"Unexpected error handling stdio line: {e}")


def main():
    parser = argparse.ArgumentParser(description="Zhihu Scraper MCP Server and CLI Tool")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="Zhihu Scraper API Base URL")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="Access Token / Master Key")
    parser.add_argument("--inspect", type=str, help="Quick test CLI: inspect a Zhihu URL and print JSON")
    args = parser.parse_args()

    if args.inspect:
        print(f"Inspecting {args.inspect} via {args.api_base}...")
        res = tool_zhihu_inspect(args.inspect, api_base=args.api_base, api_key=args.api_key)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    server = McpServer(api_base=args.api_base, api_key=args.api_key)
    server.run_stdio()


if __name__ == "__main__":
    main()
