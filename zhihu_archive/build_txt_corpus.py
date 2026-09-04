from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / 'outputs' / 'qingyitouzihao_browser' / 'articles'
EXPORT_ROOT = ROOT / 'outputs' / 'qingyitouzihao_corpus'
TXT_DIR = EXPORT_ROOT / 'articles_txt'
INDEX_DIR = EXPORT_ROOT / 'index'

MIN_TOKEN_LEN = 2
MAX_TOKEN_LEN = 12

STOPWORDS = {
    '我们', '你们', '他们', '自己', '这个', '那个', '一些', '一种', '一个', '没有', '不是',
    '因为', '所以', '如果', '然后', '但是', '就是', '还是', '已经', '可以', '觉得', '知道',
    '什么', '怎么', '为什么', '时候', '今天', '昨天', '明天', '现在', '这里', '那里', '这样',
    '那样', '进行', '出现', '继续', '开始', '结束', '需要', '不会', '不能', '应该', '可能',
    '比较', '很多', '非常', '真的', '一直', '只有', '文章', '内容', '评论', '回复', '更新',
    '作者', '专栏', '知乎', '投资', '股票', '市场', '公司', '企业', '行业', '利润', '价格',
    '问题', '情况', '逻辑', '模型', '原则', '基础', '后续', '整理', '合集', '方便',
}

COMPANY_SUFFIXES = (
    '股份', '控股', '集团', '实业', '科技', '银行', '证券', '啤酒', '有色', '铜业', '矿业',
    '建筑', '能源', '食品', '医药', '汽车', '电子', '酒业', '乳业', '电力', '材料', '地产',
)

KEY_STOCK_HINTS = (
    '燕京', '惠泉', '珠江', '青岛', '华润', '百威', '重庆', '白银', '铜陵', '中建', '中冶',
    '冠农', '天山', '华菱', '中粮', '洛阳', '比亚迪', '茅台', '洋河', '海天', '万华', '格力',
)


def ensure_dirs() -> None:
    for path in [EXPORT_ROOT, TXT_DIR, INDEX_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def safe_name(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]+', '_', text)
    text = text.strip().strip('.')
    return text or 'untitled'


def normalize_text(text: str) -> str:
    text = unescape(text.replace('\r\n', '\n').replace('\r', '\n'))
    text = text.replace('\u200b', '')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r'[\u4e00-\u9fffA-Za-z0-9]+', text)
    cleaned: list[str] = []
    for token in tokens:
        token = token.strip()
        if len(token) < MIN_TOKEN_LEN or len(token) > MAX_TOKEN_LEN:
            continue
        if token in STOPWORDS:
            continue
        if token.isdigit() and len(token) < 4:
            continue
        cleaned.append(token)
    return cleaned


def extract_stock_candidates(text: str) -> set[str]:
    candidates: set[str] = set()

    for match in re.findall(r'\$([^$\n]{2,40})\$', text):
        value = match.strip()
        if value:
            candidates.add(value)

    for token in tokenize(text):
        if re.fullmatch(r'(SZ|SH)?\d{6}', token):
            candidates.add(token)
            continue
        if token.endswith(COMPANY_SUFFIXES):
            candidates.add(token)
            continue
        if 2 <= len(token) <= 8 and any(key in token for key in KEY_STOCK_HINTS):
            candidates.add(token)
    return candidates


def extract_from_html(html_path: Path) -> tuple[str, str]:
    html = html_path.read_text(encoding='utf-8', errors='replace')
    soup = BeautifulSoup(html, 'lxml')

    title = ''
    title_tag = soup.find('h1')
    if title_tag:
        title = title_tag.get_text(' ', strip=True)
    if not title and soup.title:
        title = soup.title.get_text(' ', strip=True)
        title = re.sub(r'\s*-\s*知乎.*$', '', title)

    body_node = soup.find('article') or soup.find('main')
    if body_node is None:
        body_node = soup

    for bad in body_node.select('script, style, noscript'):
        bad.decompose()

    body_text = body_node.get_text('\n', strip=True)
    body_text = normalize_text(body_text)
    return title, body_text


def build_article_txt(article_id: str, title: str, url: str, archived_at: str, body_text: str) -> str:
    parts = [
        f'标题: {title}',
        f'文章ID: {article_id}',
        f'原文链接: {url}',
        f'归档时间: {archived_at}',
        '',
        '正文:',
        body_text,
    ]
    return '\n'.join(parts).strip() + '\n'


def main() -> int:
    ensure_dirs()

    article_files = sorted(ARTICLES_DIR.glob('*.json'))
    if not article_files:
        raise SystemExit(f'未找到文章 JSON: {ARTICLES_DIR}')

    corpus_parts: list[str] = []
    articles_index: list[dict[str, object]] = []
    keyword_to_articles: dict[str, set[str]] = defaultdict(set)
    keyword_counts: Counter[str] = Counter()
    stock_to_articles: dict[str, set[str]] = defaultdict(set)

    for path in article_files:
        article = json.loads(path.read_text(encoding='utf-8'))
        article_id = str(article.get('id') or path.stem.split('_', 1)[0])
        html_path = path.with_suffix('.html')

        title = str(article.get('title') or '')
        body_text = normalize_text(str(article.get('body_text') or ''))
        if html_path.exists():
            html_title, html_text = extract_from_html(html_path)
            if html_title:
                title = html_title
            if html_text:
                body_text = html_text

        if not title:
            title = path.stem.split('_', 1)[-1]

        article_txt = build_article_txt(
            article_id=article_id,
            title=title,
            url=str(article.get('url') or ''),
            archived_at=str(article.get('archived_at') or ''),
            body_text=body_text,
        )

        txt_name = safe_name(f'{article_id}_{title}') + '.txt'
        txt_path = TXT_DIR / txt_name
        txt_path.write_text(article_txt, encoding='utf-8')

        corpus_parts.append(
            '\n'.join(
                [
                    '=' * 80,
                    f'标题: {title}',
                    f'文章ID: {article_id}',
                    f'原文链接: {article.get("url") or ""}',
                    '',
                    body_text,
                    '',
                ]
            )
        )

        tokens = tokenize(f'{title}\n{body_text}')
        counts = Counter(tokens)
        top_keywords = [token for token, _ in counts.most_common(30)]
        stock_candidates = sorted(extract_stock_candidates(f'{title}\n{body_text}'))

        for token in top_keywords:
            keyword_to_articles[token].add(article_id)
            keyword_counts[token] += counts[token]

        for stock in stock_candidates:
            stock_to_articles[stock].add(article_id)

        articles_index.append(
            {
                'id': article_id,
                'title': title,
                'url': article.get('url'),
                'txt_path': str(txt_path),
                'top_keywords': top_keywords[:15],
                'stock_candidates': stock_candidates,
            }
        )

    corpus_txt = '\n'.join(corpus_parts).strip() + '\n'
    (EXPORT_ROOT / 'qingyitouzihao_corpus.txt').write_text(corpus_txt, encoding='utf-8')

    keyword_lines = []
    for token, count in keyword_counts.most_common():
        article_ids = sorted(keyword_to_articles[token])
        keyword_lines.append(f'{token}\tcount={count}\tarticles={len(article_ids)}\tids={",".join(article_ids)}')
    (INDEX_DIR / 'keyword_inverted_index.txt').write_text('\n'.join(keyword_lines) + '\n', encoding='utf-8')

    stock_lines = []
    for stock in sorted(stock_to_articles):
        article_ids = sorted(stock_to_articles[stock])
        stock_lines.append(f'{stock}\tarticles={len(article_ids)}\tids={",".join(article_ids)}')
    (INDEX_DIR / 'stock_candidates_index.txt').write_text('\n'.join(stock_lines) + '\n', encoding='utf-8')

    principles_parts = []
    for article in articles_index:
        principles_parts.append(
            '\n'.join(
                [
                    f'标题: {article["title"]}',
                    f'文章ID: {article["id"]}',
                    '候选原则关键词: ' + '、'.join(article['top_keywords'][:10]),
                    '涉及股票候选: ' + '、'.join(article['stock_candidates'][:10]),
                    '',
                ]
            )
        )
    (INDEX_DIR / 'principles_seed_notes.txt').write_text(''.join(principles_parts), encoding='utf-8')

    (INDEX_DIR / 'articles_index.json').write_text(
        json.dumps(
            {
                'article_count': len(articles_index),
                'export_root': str(EXPORT_ROOT),
                'articles': articles_index,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    print(f'export_root={EXPORT_ROOT}')
    print(f'article_count={len(articles_index)}')
    print(f'corpus_file={EXPORT_ROOT / "qingyitouzihao_corpus.txt"}')
    print(f'stock_index={INDEX_DIR / "stock_candidates_index.txt"}')
    print(f'keyword_index={INDEX_DIR / "keyword_inverted_index.txt"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
