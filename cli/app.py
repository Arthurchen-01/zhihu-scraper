"""
app.py - Thin CLI for the local-first Zhihu archiver.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from cli.config_view import build_config_snapshot, render_config_panel
from cli.healthcheck import render_environment_check
from cli.workflow_service import get_workflow_service
from core.config_runtime import get_config, get_logger, resolve_project_path
from core.errors import handle_error
from core.utils import extract_urls

app = typer.Typer(
    name="zhihu",
    help="Local-first Zhihu archiver / 本地优先的知乎归档工具。",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


def _get_cfg():
    return get_config()


def _get_log():
    _get_cfg()
    return get_logger()


def _get_default_output_dir() -> Path:
    return resolve_project_path(_get_cfg().local.output_dir)


def _get_default_browser_headless() -> bool:
    return _get_cfg().zhihu.browser.headless


def _resolve_output_dir(output: Optional[Path]) -> Path:
    if output is None:
        return _get_default_output_dir()
    return output if output.is_absolute() else resolve_project_path(output)


def _resolve_headless(headless: Optional[bool]) -> bool:
    return _get_default_browser_headless() if headless is None else headless


def _get_workflow_service():
    return get_workflow_service(printer=rprint, logger=_get_log())


def print_question_limit_warning(limit: int) -> None:
    if limit > 20:
        rprint("[yellow]⚠️ Multi-page question fetch enabled / 已启用问题页分页抓取[/yellow]")


def print_failed_url_reasons(results) -> None:
    for item in results.items:
        if item.success:
            continue
        reason = item.error or "Unknown failure / 未知失败"
        rprint(f"[red]❌ Failed / 失败:[/red] {item.url}")
        rprint(f"   [dim]{reason}[/dim]")


@app.command("fetch")
def fetch(
    url: Optional[str] = typer.Argument(None, help="Zhihu link(s) or text containing links / 知乎链接或含链接文本"),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Read URLs from file / 从文件读取链接列表"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output directory / 输出目录"),
    limit: Optional[int] = typer.Option(None, "-n", "--limit", help="Limit answer count for question pages / 限制问题页回答数量"),
    concurrency: int = typer.Option(4, "-c", "--concurrency", help="Concurrency for batch mode (max 8) / 批量并发数 (最大 8)"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="Do not download images / 不下载图片"),
    headless: Optional[bool] = typer.Option(None, "-b", "--headless/--no-headless", help="Run browser fallback headless / 浏览器回退是否无头"),
) -> None:
    """Archive one or more Zhihu article/answer/question links."""
    if not url and not file:
        rprint("[red]❌ Please provide a URL or --file / 请提供链接或 --file 参数[/red]")
        raise typer.Exit(code=1)

    cfg = _get_cfg()
    log = _get_log()
    output_dir = _resolve_output_dir(output)
    headless_mode = _resolve_headless(headless)

    if file:
        source_file = file if file.is_absolute() else resolve_project_path(file)
        if not source_file.exists():
            rprint(f"[red]❌ File not found / 文件不存在: {source_file}[/red]")
            raise typer.Exit(code=1)
        urls = extract_urls(source_file.read_text(encoding="utf-8"))
    else:
        urls = extract_urls(url)

    if not urls:
        rprint("[red]❌ No valid Zhihu links found / 未找到有效知乎链接[/red]")
        raise typer.Exit(code=1)

    if limit is not None and limit < 1:
        raise typer.BadParameter("Question-page limit must be at least 1 / 问题页抓取数量至少为 1")

    try:
        from core.api_client import ZhihuAPIClient

        temp_client = ZhihuAPIClient()
        if not temp_client._cookies_dict and cfg.zhihu.cookies_required:
            rprint("[yellow]⚠️ No valid Cookie detected; guest mode may be limited / 未检测到有效 Cookie，游客模式可能受限[/yellow]")
        elif diagnostic := temp_client.cookie_diagnostic_message():
            rprint(f"[yellow]⚠️ {diagnostic}[/yellow]")

        if limit:
            for target_url in urls:
                if "/question/" in target_url and "/answer/" not in target_url:
                    print_question_limit_warning(limit)

        if file or len(urls) > 1:
            max_concurrency = min(concurrency, len(urls), 8)
            rprint(f"[bold]📋 Batch / 批量: {len(urls)} links, concurrency {max_concurrency}[/bold]")
            results = asyncio.run(
                _get_workflow_service().run_batch(
                    urls=urls,
                    output_dir=output_dir,
                    concurrency=max_concurrency,
                    download_images=not no_images,
                    headless=headless_mode,
                    question_limit=limit,
                )
            )
            rprint(f"[bold]📊 Done / 完成: {results.success_count} success, {results.failed_count} failed[/bold]")
            if results.has_failures:
                print_failed_url_reasons(results)
                raise typer.Exit(code=1)
            return

        result = asyncio.run(
            _get_workflow_service().run_fetch_urls(
                urls=urls,
                output_dir=output_dir,
                limit=limit,
                download_images=not no_images,
                headless=headless_mode,
                stop_on_error=True,
            )
        )
        if result.has_failures:
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        handle_error(exc, log)
        raise typer.Exit(code=1) from exc


@app.command("query")
def query_db(
    keyword: str = typer.Argument(..., help="Keyword to search / 要搜索的关键词"),
    limit: int = typer.Option(10, "-l", "--limit", help="Maximum number of results / 最大显示结果数量"),
    data_dir: Optional[Path] = typer.Option(None, "-d", "--data-dir", help="Data directory / 数据目录"),
) -> None:
    """Search archived content in the local SQLite index."""
    resolved_data_dir = _resolve_output_dir(data_dir)
    db_path = resolved_data_dir / "zhihu.db"
    if not db_path.exists():
        rprint("[red]❌ Zhihu database not found. Please run fetch first / 未找到数据库，请先执行 fetch。[/red]")
        raise typer.Exit(code=1)

    from core.db import ZhihuDatabase

    db = ZhihuDatabase(str(db_path))
    results = db.search_articles(keyword, limit)
    db.close()

    if not results:
        rprint(f"[yellow]⚠️ No articles found containing '{keyword}' / 未找到包含关键词的文章。[/yellow]")
        return

    table = Table(title=f"Search Results / 检索结果: {keyword}")
    table.add_column("Type", justify="center", style="cyan")
    table.add_column("Author", style="green")
    table.add_column("Title", style="magenta", overflow="fold")
    table.add_column("Captured At", style="dim")
    table.add_column("Content Key", style="blue")
    for row in results:
        table.add_row(
            row["type"],
            row["author"],
            row["title"],
            row["created_at"].split("T")[0],
            row["content_key"],
        )
    rprint(table)


@app.command("config")
def config() -> None:
    """View current configuration and resolved local paths."""
    cfg = _get_cfg()
    from core.cookie_manager import describe_cookie_file_path

    config_path = Path(__file__).parent.parent / "config.yaml"
    snapshot = build_config_snapshot(
        cfg=cfg,
        config_path=config_path,
        resolve_project_path=resolve_project_path,
        describe_cookie_file_path=describe_cookie_file_path,
    )
    rprint(f"📄 Configuration file / 配置文件: [cyan]{config_path}[/]")
    rprint(render_config_panel(snapshot))


@app.command("check")
def check() -> None:
    """Check environment dependencies and local configuration."""
    render_environment_check()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
