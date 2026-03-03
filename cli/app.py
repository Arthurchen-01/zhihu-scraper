"""
cli/app.py — CLI 增强模块

使用 Typer 提供现代化命令行接口，支持参数自动补全。

核心功能：
- fetch: 抓取单个知乎链接 (文章/回答/问题)
- batch: 批量抓取多个链接
- monitor: 增量监控收藏夹
- query: 在 SQLite 数据库中检索已抓取的内容
- interactive: 交互式抓取模式
- config: 查看/管理配置
- check: 检查环境依赖

使用示例：
    zhihu fetch "https://www.zhihu.com/p/123456"
    zhihu fetch "https://www.zhihu.com/question/123456" -n 10
    zhihu batch ./urls.txt -c 8
    zhihu monitor 78170682 -o ./data
    zhihu query "深度学习" -l 20
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from random import uniform
import asyncio
import typer
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text

from core.config import get_config, get_logger, get_humanizer
from core.scraper import ZhihuDownloader
from core.converter import ZhihuConverter
from core.errors import handle_error

# ============================================================
# CLI 应用初始化
# ============================================================

app = typer.Typer(
    name="zhihu",
    help="🕷️ 知乎高质量内容爬取工具",
    add_completion=False,
    no_args_is_help=True,
)

# 初始化配置和日志
cfg = get_config()
log = get_logger()


# ============================================================
# 工具函数
# ============================================================

def sanitize_filename(name: str) -> str:
    """清理文件名非法字符"""
    import re
    name = re.sub(r'[/\\:*?"<>|\x00-\x1f]', "_", name)
    name = name.strip(" .")
    return name[:50] or "untitled"


def extract_urls(text: str) -> List[str]:
    """从文本中提取知乎链接

    支持的 URL 格式：
    - 专栏文章: https://zhuanlan.zhihu.com/p/123456
    - 单个回答: https://www.zhihu.com/question/123/answer/456
    - 问题页: https://www.zhihu.com/question/123
    """
    import re
    pattern = r"(?:https?://)?(?:www\.|zhuanlan\.)?zhihu\.com/(?:p/\d+|question/\d+(?:/answer/\d+)?)"
    matches = re.findall(pattern, text)
    # 去重并补全协议头
    return list(dict.fromkeys([(m if m.startswith("http") else "https://" + m) for m in matches]))


def print_result(
    title: str,
    author: str,
    success: bool,
    path: str = "",
    error: Optional[str] = None
) -> None:
    """打印单条结果"""
    if success:
        rprint(f"✅ [bold cyan]{author}[/] - [white]{title[:30]}...[/]")
        rprint(f"   📁 {path}")
    else:
        rprint(f"❌ [bold cyan]{author}[/] - [yellow]{title[:30]}...[/]")
        rprint(f"   💥 {error}")


# ============================================================
# 命令定义
# ============================================================

@app.command("fetch")
def fetch(
    url: str = typer.Argument(..., help="知乎链接 (问题/回答/专栏)"),
    output: Path = typer.Option(Path("./data"), "-o", "--output", help="输出目录"),
    limit: Optional[int] = typer.Option(None, "-n", "--limit", help="限制回答数量 (仅限问题页)"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="不下载图片"),
    headless: bool = typer.Option(True, "-b", "--headless", help="无头模式运行浏览器"),
) -> None:
    """
    抓取单个知乎链接。

    支持的链接类型：
    - 专栏文章: https://zhuanlan.zhihu.com/p/123456
    - 单个回答: https://www.zhihu.com/question/123/answer/456
    - 问题页 (批量): https://www.zhihu.com/question/123

    使用示例:
        zhihu fetch "https://www.zhihu.com/p/123456"
        zhihu fetch "https://www.zhihu.com/question/123456" -n 10
        zhihu fetch "https://www.zhihu.com/p/abcdef" -o ./output
    """
    log.info("fetch_started", url=url, limit=limit)

    try:
        downloader = ZhihuDownloader(url)

        # 检测是否需要登录
        if not downloader.has_valid_cookies() and cfg.zhihu.cookies_required:
            rprint("[yellow]⚠️  未检测到有效 Cookie，将使用游客模式[/yellow]")

        # 准备抓取配置
        scrape_config = {}
        if limit and "/question/" in url and "/answer/" not in url:
            scrape_config = {"start": 0, "limit": limit}

        # 执行抓取
        rprint(f"🌍 正在访问: {url}")

        asyncio.run(_fetch_and_save(
            url=url,
            output_dir=output,
            scrape_config=scrape_config,
            download_images=not no_images,
            headless=headless
        ))

    except Exception as e:
        handle_error(e, log)
        raise SystemExit(1)


@app.command("batch")
def batch(
    input_file: Path = typer.Argument(..., help="URL列表文件 (每行一个链接)"),
    output: Path = typer.Option(Path("./data"), "-o", "--output", help="输出目录"),
    concurrency: int = typer.Option(4, "-c", "--concurrency", help="并发数 (建议 4-8)"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="不下载图片"),
    headless: bool = typer.Option(True, "-b", "--headless", help="无头模式运行浏览器"),
) -> None:
    """
    批量抓取多个知乎链接。

    从文件中读取 URL 列表，并发执行抓取任务。

    使用示例:
        zhihu batch ./urls.txt
        zhihu batch ./urls.txt -c 8 -o ./output
    """
    if not input_file.exists():
        rprint(f"[red]❌ 文件不存在: {input_file}[/red]")
        raise SystemExit(1)

    urls = extract_urls(input_file.read_text())
    if not urls:
        rprint("[red]❌ 未找到有效链接[/red]")
        raise SystemExit(1)

    # 限制并发数，避免触发反爬
    max_concurrency = min(concurrency, len(urls), 8)
    log.info("batch_started", file=str(input_file), count=len(urls), concurrency=max_concurrency)
    rprint(f"[bold]📋 批量任务: {len(urls)} 个链接 (并发: {max_concurrency})[/bold]")

    # 并发执行
    results = asyncio.run(_batch_concurrent(
        urls=urls,
        output_dir=output,
        concurrency=max_concurrency,
        download_images=not no_images,
        headless=headless
    ))

    # 统计结果
    success = sum(1 for r in results if r["success"])
    failed = len(results) - success

    rprint(f"\n[bold]📊 批量完成: {success} 成功, {failed} 失败[/bold]")
    log.info("batch_completed", success=success, failed=failed)


@app.command("monitor")
def monitor(
    collection_id: str = typer.Argument(..., help="知乎收藏夹ID (如 78170682)"),
    output: Path = typer.Option(Path("./data"), "-o", "--output", help="输出目录"),
    concurrency: int = typer.Option(4, "-c", "--concurrency", help="并发数"),
    no_images: bool = typer.Option(False, "-i", "--no-images", help="不下载图片"),
    headless: bool = typer.Option(True, "-b", "--headless", help="无头模式"),
) -> None:
    """
    增量监控并抓取知乎收藏夹的新增内容。

    功能说明：
    - 检查收藏夹中新增的内容（自上次监控以来）
    - 自动去重，跳过已抓取的内容
    - 下载新增内容并保存到本地
    - 更新状态文件，记录最新进度

    使用示例:
        zhihu monitor 78170682                    # 监控默认配置
        zhihu monitor 78170682 -o ./data         # 指定输出目录
        zhihu monitor 78170682 -c 8             # 提高并发数
    """
    log.info("monitor_started", collection_id=collection_id)
    rprint(f"[bold]📡 启动增量监控: 收藏夹 {collection_id}[/bold]")

    from core.monitor import CollectionMonitor
    m = CollectionMonitor(data_dir=str(output))

    try:
        new_items, new_last_id = m.get_new_items(collection_id)
    except Exception as e:
        handle_error(e, log)
        raise SystemExit(1)

    if not new_items:
        rprint("[green]✨ 收藏夹没有新增内容，监控结束。[/green]")
        return

    rprint(f"\n[bold]🛒 准备下载 {len(new_items)} 个新内容...[/bold]")

    urls = [item["url"] for item in new_items]
    max_concurrency = min(concurrency, len(urls), 8)

    results = asyncio.run(_batch_concurrent(
        urls=urls,
        output_dir=output,
        concurrency=max_concurrency,
        download_images=not no_images,
        headless=headless,
        collection_id=collection_id
    ))

    success = sum(1 for r in results if r["success"])
    failed = len(results) - success

    rprint(f"\n[bold]📊 监控下载完成: {success} 成功, {failed} 失败[/bold]")

    if success > 0:
        m.mark_updated(collection_id, new_last_id)
        rprint(f"[cyan]✅ 已保存最新进度指针: {new_last_id}[/cyan]")


@app.command("query")
def query_db(
    keyword: str = typer.Argument(..., help="要搜索的关键词"),
    limit: int = typer.Option(10, "-l", "--limit", help="最大显示结果数量"),
    data_dir: str = typer.Option("./data", "-d", "--data-dir", help="数据目录（默认 ./data）"),
) -> None:
    """
    在本地 SQLite 数据库中检索已抓取的知乎内容。

    数据库结构：
    - 表: articles
    - 字段: answer_id, type, title, author, url, content_md, collection_id, created_at, updated_at

    使用示例:
        zhihu query "深度学习"              # 搜索标题和内容
        zhihu query "Transformer" -l 20     # 限制结果数量
        zhihu query "LLM" -d ./custom_data  # 指定数据目录
    """
    from core.db import ZhihuDatabase
    from rich.table import Table

    db_path = Path(data_dir) / "zhihu.db"
    if not db_path.exists():
        rprint("[red]❌ 未找到知乎数据库，请先执行抓取任务 (fetch 或 monitor)。[/red]")
        raise SystemExit(1)

    db = ZhihuDatabase(str(db_path))
    results = db.search_articles(keyword, limit)
    db.close()

    if not results:
        rprint(f"[yellow]⚠️ 未找到包含关键词 '[bold]{keyword}[/bold]' 的文章。[/yellow]")
        return

    table = Table(title=f"🔍 检索结果: '{keyword}' (前 {len(results)} 条)")
    table.add_column("Type", justify="center", style="cyan")
    table.add_column("Author", style="green")
    table.add_column("Title", style="magenta", overflow="fold")
    table.add_column("Captured At", style="dim")
    table.add_column("Zhihu ID", justify="right", style="blue")

    for row in results:
        table.add_row(
            row["type"],
            row["author"],
            row["title"],
            row["created_at"].split("T")[0],
            row["answer_id"]
        )

    rprint(table)


@app.command("interactive")
def interactive() -> None:
    """
    启动带霓虹控制台面板的交互式抓取模式。

    功能：
    - 彩色终端界面
    - 引导式输入 URL
    - 实时显示抓取进度
    - 查看抓取历史记录

    使用示例:
        zhihu interactive
    """
    from cli.interactive import run_interactive
    try:
        asyncio.run(run_interactive())
    except Exception as e:
        handle_error(e, log)


@app.command("config")
def config_cmd(
    show: bool = typer.Option(False, "--show", help="显示当前配置"),
    path: bool = typer.Option(False, "--path", help="显示配置文件路径"),
) -> None:
    """
    查看或管理配置。

    使用示例:
        zhihu config --show    # 显示当前配置
        zhihu config --path    # 显示配置文件路径
    """
    if path:
        from pathlib import Path as P
        config_path = P(__file__).parent.parent / "config.yaml"
        rprint(f"📄 配置文件: [cyan]{config_path}[/]")
        raise SystemExit(0)

    if show:
        rprint(Panel(
            Text(f"""
[b]配置路径:[/] {Path(__file__).parent.parent / "config.yaml"}

[b]输出目录:[/] {cfg.output.directory}
[b]日志级别:[/] {cfg.logging.level}
[b]浏览器:[/] {"无头" if cfg.zhihu.browser.headless else "有头"}
[b]重试次数:[/] {cfg.crawler.retry.max_attempts}
[b]图片并发:[/] {cfg.crawler.images.concurrency}
[b]Cookie轮换:[/] {"启用" if hasattr(cfg, 'zhihu') and cfg.zhihu.cookies_required else "禁用"}
            """.strip(), justify="left"),
            title="🛠️ 当前配置",
            border_style="cyan"
        ))


@app.command("check")
def check() -> None:
    """
    检查环境依赖和配置是否正常。

    检查项目：
    1. config.yaml 配置文件是否存在
    2. cookies.json 是否有效
    3. Playwright 浏览器是否可用
    """
    from playwright.async_api import async_playwright

    rprint("🔍 系统检查...\n")

    # 检查配置文件
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        rprint("✅ config.yaml 存在")
    else:
        rprint("❌ config.yaml 不存在")

    # 检查 cookies
    cookies_path = Path(__file__).parent.parent / "cookies.json"
    has_cookie = cookies_path.exists() and "YOUR_COOKIE_HERE" not in cookies_path.read_text()
    rprint(f"{'✅' if has_cookie else '⚠️'} cookies.json {'有效' if has_cookie else '未配置或无效'}")

    # 检查 playwright
    try:
        asyncio.run(_check_playwright())
        rprint("✅ Playwright 正常")
    except Exception as e:
        rprint(f"❌ Playwright 错误: {e}")


async def _check_playwright() -> None:
    """检查 playwright 是否可用"""
    async with async_playwright() as pw:
        await pw.chromium.launch(headless=True)


# ============================================================
# 内部助手
# ============================================================


async def _batch_concurrent(
    urls: List[str],
    output_dir: Path,
    concurrency: int,
    download_images: bool,
    headless: bool,
    collection_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    并发批量抓取核心实现。

    防风控策略：
    - 使用信号量限制最大并发数
    - 任务间随机延迟 (0.5~6秒)

    Args:
        urls: URL 列表
        output_dir: 输出目录
        concurrency: 并发数
        download_images: 是否下载图片
        headless: 无头模式
        collection_id: 收藏夹 ID (用于关联数据库记录)

    Returns:
        结果列表，每个元素包含 success, url 等字段
    """
    semaphore = asyncio.Semaphore(concurrency)
    humanizer = get_humanizer()

    async def fetch_one(url: str, index: int) -> Dict[str, Any]:
        async with semaphore:
            # 任务间随机延迟，避免触发反爬
            # 延迟时间随任务序号递增，降低同时发起的概率
            if index > 0:
                delay = uniform(0.5, 2.0) * (index % 3 + 1)
                await asyncio.sleep(delay)

            try:
                await _fetch_and_save(
                    url=url,
                    output_dir=output_dir,
                    scrape_config={},
                    download_images=download_images,
                    headless=headless,
                    collection_id=collection_id
                )
                return {"url": url, "success": True}
            except Exception as e:
                handle_error(e, log)
                return {"url": url, "success": False, "error": str(e)}

    # 创建所有任务
    tasks = [fetch_one(url, i) for i, url in enumerate(urls)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 清理结果
    cleaned = []
    for r in results:
        if isinstance(r, dict):
            cleaned.append(r)
        else:
            cleaned.append({"url": "unknown", "success": False})

    return cleaned


async def _fetch_and_save(
    url: str,
    output_dir: Path,
    scrape_config: dict,
    download_images: bool = True,
    headless: bool = True,
    collection_id: Optional[str] = None,
) -> None:
    """执行抓取并保存到本地文件和数据库。

    完整执行流程：
    1. 使用 ZhihuDownloader 抓取页面数据
    2. 提取图片 URL 并下载到 images/ 目录
    3. 使用 ZhihuConverter 将 HTML 转换为 Markdown
    4. 保存为 index.md 文件
    5. 保存到 SQLite 数据库

    Args:
        url: 知乎链接
        output_dir: 输出目录
        scrape_config: 抓取配置 (如 limit, start)
        download_images: 是否下载图片
        headless: 无头模式 (API 模式下不生效)
        collection_id: 收藏夹 ID (关联数据库记录)
    """
    from datetime import datetime

    downloader = ZhihuDownloader(url)
    data = await downloader.fetch_page(**scrape_config)

    if not data:
        rprint("[yellow]⚠️  未获取到内容[/yellow]")
        return

    today = datetime.now().strftime("%Y-%m-%d")

    # 处理单个或多个结果 (问题页返回多个回答列表)
    items = data if isinstance(data, list) else [data]

    for item in items:
        title = sanitize_filename(item["title"])
        author = sanitize_filename(item["author"])

        folder_name = f"[{today}] {title}"
        folder = output_dir / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        # 下载图片
        img_map = {}
        if download_images:
            img_urls = ZhihuConverter.extract_image_urls(item["html"])
            if img_urls:
                rprint(f"   📥 下载 {len(img_urls)} 张图片...")
                img_map = await ZhihuDownloader.download_images(
                    img_urls,
                    folder / "images"
                )

        # 转换并保存 Markdown
        converter = ZhihuConverter(img_map=img_map)
        md = converter.convert(item["html"])

        header = (
            f"# {item['title']}\n\n"
            f"> **作者**: {item['author']}  \n"
            f"> **来源**: [{url}]({url})  \n"
            f"> **日期**: {today}\n\n"
            "---\n\n"
        )

        out_path = folder / "index.md"
        full_md = header + md
        out_path.write_text(full_md, encoding="utf-8")

        # ★★★★★ 保存到 SQLite 数据库 ★★★★★
        from core.db import ZhihuDatabase
        db_folder = output_dir if output_dir.name == "data" else output_dir.parent
        if db_folder.name != "data":
             db_folder = Path("./data") # fallback
        db = ZhihuDatabase(str(db_folder / "zhihu.db"))
        db.save_article(item, full_md, collection_id=collection_id)
        db.close()

        rprint(f"✅ 保存: [cyan]{author}[/] - {title[:25]}...")
        rprint(f"   📁 {out_path} & 入库 DB")


# ============================================================
# 入口点
# ============================================================

def main() -> None:
    """CLI 入口"""
    app()


if __name__ == "__main__":
    main()