from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions

ROOT = Path(__file__).resolve().parent
EDGE_USER_DATA = Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
CHROME_USER_DATA = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"


ARTICLE_RE = re.compile(r"https://zhuanlan\.zhihu\.com/p/\d+|/p/\d+")
COLUMN_RE = re.compile(r"https://zhuanlan\.zhihu\.com/column/[^/?#]+|/column/[^/?#]+")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_name(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]+', '_', text)
    text = text.strip().strip('.')
    return text or 'untitled'


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def strip_html(value: str) -> str:
    soup = BeautifulSoup(value, 'lxml')
    text = soup.get_text("\n")
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_driver(browser: str, profile: str, headless: bool = False):
    if browser == 'edge':
        options = EdgeOptions()
        options.use_chromium = True
        options.add_argument(f'--user-data-dir={EDGE_USER_DATA}')
        options.add_argument(f'--profile-directory={profile}')
        if headless:
            options.add_argument('--headless=new')
        return webdriver.Edge(options=options)
    if browser == 'chrome':
        options = ChromeOptions()
        options.add_argument(f'--user-data-dir={CHROME_USER_DATA}')
        options.add_argument(f'--profile-directory={profile}')
        if headless:
            options.add_argument('--headless=new')
        return webdriver.Chrome(options=options)
    raise ValueError(f'Unsupported browser: {browser}')


def collect_links_from_page_source(page_source: str, current_url: str) -> tuple[set[str], set[str]]:
    soup = BeautifulSoup(page_source, 'lxml')
    article_links: set[str] = set()
    column_links: set[str] = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        full = urljoin(current_url, href)
        if ARTICLE_RE.fullmatch(href) or ARTICLE_RE.fullmatch(full):
            if full.startswith('https://www.zhihu.com/p/'):
                article_id = full.rsplit('/', 1)[-1]
                full = f'https://zhuanlan.zhihu.com/p/{article_id}'
            elif full.startswith('https://zhuanlan.zhihu.com/p/'):
                pass
            elif '/p/' in full:
                article_id = full.rsplit('/', 1)[-1]
                full = f'https://zhuanlan.zhihu.com/p/{article_id}'
            article_links.add(full)
        if COLUMN_RE.fullmatch(href) or COLUMN_RE.fullmatch(full):
            if full.startswith('https://www.zhihu.com/column/'):
                slug = full.rsplit('/', 1)[-1]
                full = f'https://zhuanlan.zhihu.com/column/{slug}'
            column_links.add(full)
    return article_links, column_links


def open_and_scroll(driver, url: str, rounds: int = 12, pause: float = 1.5) -> str:
    driver.get(url)
    time.sleep(3)
    last_height = 0
    for _ in range(rounds):
        driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        time.sleep(pause)
        height = driver.execute_script('return document.body.scrollHeight')
        if height == last_height:
            break
        last_height = height
    return driver.page_source


def save_page_html(path: Path, html: str) -> None:
    ensure_dir(path.parent)
    path.write_text(html, encoding='utf-8')


def parse_article(driver, url: str) -> dict[str, object]:
    driver.get(url)
    time.sleep(2)
    html = driver.page_source
    soup = BeautifulSoup(html, 'lxml')

    title = None
    title_tag = soup.find('h1')
    if title_tag:
        title = title_tag.get_text(' ', strip=True)
    if not title and soup.title:
        title = soup.title.get_text(' ', strip=True)

    body_html = ''
    article_tag = soup.find('article')
    if article_tag:
        body_html = str(article_tag)
    else:
        main_tag = soup.find('main')
        body_html = str(main_tag) if main_tag else html

    return {
        'url': url,
        'title': title,
        'archived_at': now_iso(),
        'html': html,
        'body_html': body_html,
        'body_text': strip_html(body_html),
    }


def archive_articles(driver, article_links: list[str]) -> list[dict[str, object]]:
    index: list[dict[str, object]] = []
    for idx, url in enumerate(article_links, start=1):
        try:
            payload = parse_article(driver, url)
            article_id = url.rstrip('/').rsplit('/', 1)[-1]
            base = safe_name(f'{article_id}_{payload.get("title") or "article"}')
            write_json(ARTICLES_DIR / f'{base}.json', {
                'url': payload['url'],
                'title': payload['title'],
                'archived_at': payload['archived_at'],
                'body_text': payload['body_text'],
            })
            (ARTICLES_DIR / f'{base}.html').write_text(payload['html'], encoding='utf-8')
            (ARTICLES_DIR / f'{base}.md').write_text(payload['body_text'], encoding='utf-8')
            index.append({'id': article_id, 'title': payload['title'], 'url': url})
            print(f'[{idx}/{len(article_links)}] article {article_id} {payload.get("title")}')
        except Exception as exc:
            index.append({'id': None, 'title': None, 'url': url, 'error': str(exc)})
            print(f'error article {url}: {exc}')
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description='Archive Zhihu person articles using a logged-in Edge/Chrome profile.')
    parser.add_argument('--browser', default='edge', choices=['edge', 'chrome'])
    parser.add_argument('--profile', default='Default', help='Browser profile directory name, usually Default')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--article-scroll-rounds', type=int, default=12)
    parser.add_argument('--column-scroll-rounds', type=int, default=12)
    parser.add_argument('--person-id', required=True, help='Zhihu people id, e.g. shan-chang-qing-yi')
    args = parser.parse_args()

    person_url = f'https://www.zhihu.com/people/{args.person_id}/posts'
    columns_url = f'https://www.zhihu.com/people/{args.person_id}/columns'
    output_root = ROOT / 'outputs' / f'{args.person_id}_browser'
    articles_dir = output_root / 'articles'
    columns_dir = output_root / 'columns'
    index_dir = output_root / 'index'

    for path in [output_root, articles_dir, columns_dir, index_dir]:
        ensure_dir(path)

    try:
        driver = build_driver(args.browser, args.profile, headless=args.headless)
    except WebDriverException as exc:
        raise SystemExit(
            '浏览器驱动启动失败。先关闭正在运行的 Edge/Chrome，再重试。'
            '如果还是失败，说明本机缺少可用的 WebDriver。\n'
            f'原始错误: {exc}'
        )

    try:
        person_html = open_and_scroll(driver, person_url, rounds=args.article_scroll_rounds)
        save_page_html(index_dir / 'person_page.html', person_html)
        direct_articles, direct_columns = collect_links_from_page_source(person_html, person_url)

        columns_html = open_and_scroll(driver, columns_url, rounds=args.column_scroll_rounds)
        save_page_html(index_dir / 'columns_page.html', columns_html)
        _, listed_columns = collect_links_from_page_source(columns_html, columns_url)

        all_columns = sorted(direct_columns | listed_columns)
        column_index: list[dict[str, object]] = []
        all_articles: set[str] = set(direct_articles)

        for column_url in all_columns:
            try:
                html = open_and_scroll(driver, column_url, rounds=args.column_scroll_rounds)
                slug = column_url.rstrip('/').rsplit('/', 1)[-1]
                save_page_html(columns_dir / f'{safe_name(slug)}.html', html)
                article_links, _ = collect_links_from_page_source(html, column_url)
                all_articles |= article_links
                column_index.append({'url': column_url, 'article_links_found': len(article_links)})
                print(f'column {column_url} links={len(article_links)}')
            except Exception as exc:
                column_index.append({'url': column_url, 'error': str(exc)})
                print(f'error column {column_url}: {exc}')

        global ARTICLES_DIR
        ARTICLES_DIR = articles_dir
        article_index = archive_articles(driver, sorted(all_articles))

        write_json(index_dir / 'articles_index.json', article_index)
        write_json(index_dir / 'columns_index.json', column_index)
        write_json(
            index_dir / 'run_log.json',
            {
                'finished_at': now_iso(),
                'browser': args.browser,
                'profile': args.profile,
                'person_url': person_url,
                'columns_url': columns_url,
                'direct_article_links_found': len(direct_articles),
                'column_count_found': len(all_columns),
                'unique_article_links_found': len(all_articles),
                'saved_articles': sum(1 for item in article_index if item.get('id')),
                'errors': [item for item in article_index if item.get('error')] + [item for item in column_index if item.get('error')],
            },
        )
        print(f'unique_article_links_found={len(all_articles)}')
        print(f'saved_articles={sum(1 for item in article_index if item.get("id"))}')
        print(f'output={output_root}')
        return 0
    finally:
        driver.quit()


if __name__ == '__main__':
    raise SystemExit(main())
