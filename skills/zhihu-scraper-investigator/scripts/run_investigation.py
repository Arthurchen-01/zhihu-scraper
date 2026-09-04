"""CLI Helper for Zhihu Scraper Skill.
Usage:
    python run_investigation.py --url https://www.zhihu.com/people/shou-qi-hei --output ./investigation_results
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from zhihu_scraper import ZhihuClient, AuthorScraper, ColumnScraper, ArticleScraper, CommentScraper, VisualArchiver


def main():
    parser = argparse.ArgumentParser(description="Zhihu Target Investigator Skill Runner")
    parser.add_argument("--url", required=True, help="Target Zhihu Profile or Column URL")
    parser.add_argument("--cookie", default="", help="Zhihu Cookie (optional)")
    parser.add_argument("--output", default="./investigation_output", help="Output directory")
    parser.add_argument("--screenshot", action="store_true", help="Capture Playwright screenshot")
    parser.add_argument("--comments", action="store_true", help="Capture nested comments tree")
    parser.add_argument("--max-items", type=int, default=20, help="Maximum items per category")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = ZhihuClient(cookie=args.cookie)
    author_scraper = AuthorScraper(client)
    art_scraper = ArticleScraper(client)
    comment_scraper = CommentScraper(client)
    visual_archiver = VisualArchiver(cookie=args.cookie) if args.screenshot else None

    print(f"🔍 正在解析目标: {args.url}")
    catalog = author_scraper.catalog_all_assets(args.url, max_per_category=args.max_items)
    author_name = catalog["author"]["name"]
    items = catalog["items"]

    print(f"👤 发现作者: {author_name}，共检索到 {len(items)} 条内容")

    # Save catalog summary
    catalog_path = out_dir / "catalog_index.json"
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 目录索引已生成: {catalog_path}")

    # Process items
    articles_dir = out_dir / "articles"
    comments_dir = out_dir / "comments"
    screenshots_dir = out_dir / "screenshots"

    for idx, it in enumerate(items, 1):
        it_type = it.get("type")
        it_id = it.get("id")
        title = it.get("title", f"item_{it_id}")
        url = it.get("url")

        print(f"[{idx}/{len(items)}] 正在处理 ({it_type}): 《{title[:30]}》...")
        if it_type == "article":
            art_scraper.scrape(it_id, save_dir=articles_dir)
            if args.comments:
                comment_scraper.scrape_comment_tree("article", it_id, save_path=comments_dir / f"comments_{it_id}.json")
            if args.screenshot and visual_archiver and url:
                visual_archiver.capture_screenshot(url, screenshots_dir / f"screenshot_{it_id}.png")

    print(f"\n🎉 调查取证完成！所有结果已保存至: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
