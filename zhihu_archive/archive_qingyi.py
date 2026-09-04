from __future__ import annotations

import argparse
import traceback
from pathlib import Path

from zhihu_archive_utils import (
    article_payload,
    column_payload,
    get_client,
    iso_now,
    load_json,
    safe_name,
    write_json,
)

ROOT = Path(__file__).resolve().parent


def archive_person_articles(person: object) -> tuple[list[dict[str, object]], list[str]]:
    index: list[dict[str, object]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for article in person.articles:
        try:
            payload = article_payload(article)
            article_id = str(payload['id'])
            if article_id in seen:
                continue
            seen.add(article_id)
            base = safe_name(f"{article_id}_{payload['title']}")
            write_json(ARTICLES_DIR / f"{base}.json", payload)
            (ARTICLES_DIR / f"{base}.html").write_text(payload['content_html'] or '', encoding='utf-8')
            (ARTICLES_DIR / f"{base}.md").write_text(payload['content_text'] or '', encoding='utf-8')
            index.append({
                'id': payload['id'],
                'title': payload['title'],
                'url': payload['url'],
                'column_title': payload['column_title'],
                'source': 'person_articles',
            })
            print(f"article {payload['id']} {payload['title']}")
        except Exception as exc:
            errors.append(f"person_articles: {exc}")
    return index, errors


def archive_columns(person: object, existing_ids: set[str]) -> tuple[list[dict[str, object]], list[str], list[str]]:
    columns_index: list[dict[str, object]] = []
    article_index: list[dict[str, object]] = []
    errors: list[str] = []

    for column in person.columns:
        try:
            c_payload = column_payload(column)
            col_dir = COLUMNS_DIR / safe_name(f"{c_payload['id']}_{c_payload['title']}")
            write_json(col_dir / 'column.json', c_payload)
            columns_index.append(c_payload)
            print(f"column {c_payload['id']} {c_payload['title']}")

            for article in column.articles:
                try:
                    payload = article_payload(article)
                    article_id = str(payload['id'])
                    if article_id in existing_ids:
                        continue
                    existing_ids.add(article_id)
                    base = safe_name(f"{article_id}_{payload['title']}")
                    write_json(ARTICLES_DIR / f"{base}.json", payload)
                    (ARTICLES_DIR / f"{base}.html").write_text(payload['content_html'] or '', encoding='utf-8')
                    (ARTICLES_DIR / f"{base}.md").write_text(payload['content_text'] or '', encoding='utf-8')
                    article_index.append({
                        'id': payload['id'],
                        'title': payload['title'],
                        'url': payload['url'],
                        'column_title': payload['column_title'],
                        'source': 'column_articles',
                    })
                    print(f"column_article {payload['id']} {payload['title']}")
                except Exception as exc:
                    errors.append(f"column_article {c_payload['title']}: {exc}")
        except Exception as exc:
            errors.append(f"column: {exc}")
    return columns_index, article_index, errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Archive Zhihu person articles via zhihu_oauth token')
    parser.add_argument('--person-id', required=True, help='Zhihu people id, e.g. shan-chang-qing-yi')
    args = parser.parse_args()

    output_root = ROOT / 'outputs' / args.person_id
    articles_dir = output_root / 'articles'
    columns_dir = output_root / 'columns'
    output_root.mkdir(parents=True, exist_ok=True)
    articles_dir.mkdir(parents=True, exist_ok=True)
    columns_dir.mkdir(parents=True, exist_ok=True)

    global OUTPUT_ROOT, ARTICLES_DIR, COLUMNS_DIR
    OUTPUT_ROOT = output_root
    ARTICLES_DIR = articles_dir
    COLUMNS_DIR = columns_dir

    client = get_client(ROOT, login_if_needed=False)
    if not client.is_login():
        raise SystemExit('未登录。请先运行 python login_zhihu.py')

    person = client.people(args.person_id)
    profile = {
        'id': getattr(person, 'id', None),
        'name': getattr(person, 'name', None),
        'headline': getattr(person, 'headline', None),
        'description': getattr(person, 'description', None),
        'answer_count': getattr(person, 'answer_count', None),
        'article_count': getattr(person, 'article_count', None),
        'column_count': getattr(person, 'column_count', None),
        'follower_count': getattr(person, 'follower_count', None),
        'archived_at': iso_now(),
        'source_urls': [
            f'https://www.zhihu.com/people/{args.person_id}',
            f'https://www.zhihu.com/people/{args.person_id}/columns',
        ],
    }
    write_json(OUTPUT_ROOT / 'profile.json', profile)

    direct_index, direct_errors = archive_person_articles(person)
    existing_ids = {str(item['id']) for item in direct_index if item.get('id') is not None}
    columns_index, column_article_index, column_errors = archive_columns(person, existing_ids)

    all_articles = direct_index + column_article_index
    all_articles.sort(key=lambda item: (str(item.get('id')), str(item.get('title'))))
    write_json(OUTPUT_ROOT / 'articles_index.json', all_articles)
    write_json(OUTPUT_ROOT / 'columns_index.json', columns_index)
    write_json(
        OUTPUT_ROOT / 'run_log.json',
        {
            'person_id': args.person_id,
            'finished_at': iso_now(),
            'direct_articles': len(direct_index),
            'column_articles_added': len(column_article_index),
            'columns': len(columns_index),
            'errors': direct_errors + column_errors,
        },
    )

    print(f"direct_articles={len(direct_index)}")
    print(f"column_articles_added={len(column_article_index)}")
    print(f"columns={len(columns_index)}")
    print(f"total_unique_articles={len(all_articles)}")
    if direct_errors or column_errors:
        print('有错误，详见 outputs\\qingyitouzihao\\run_log.json')
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
