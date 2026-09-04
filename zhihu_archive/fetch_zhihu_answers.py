from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "outputs"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0"
)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def format_ts(value: int | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def build_session(cookie: str) -> requests.Session:
    session = requests.Session()
    retries = Retry(total=5, connect=5, read=5, backoff_factor=1.2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=1, pool_maxsize=1)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cookie": cookie.strip(),
            "Referer": "https://www.zhihu.com/",
            "x-requested-with": "fetch",
            "Connection": "close",
        }
    )
    return session


def fetch_answers_page(session: requests.Session, person_id: str, offset: int, limit: int) -> dict:
    url = f"https://www.zhihu.com/api/v4/members/{person_id}/answers"
    params = {
        "include": "data[*].id,excerpt,excerpt_new,created,updated,url,question.id,question.title,comment_count,voteup_count,voteup_count",
        "offset": offset,
        "limit": limit,
    }
    response = session.get(url, params=params, timeout=40)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError(f"Unexpected response: {str(payload)[:500]}")
    return payload


def extract_next_offset(paging: dict, current_offset: int) -> int | None:
    next_url = paging.get("next")
    if not next_url:
        return None
    parsed = urlparse(str(next_url))
    values = parse_qs(parsed.query).get("offset")
    if not values:
        return None
    next_offset = int(values[0])
    if next_offset == current_offset:
        return None
    return next_offset


def build_answer_url(answer_id: str) -> str:
    return f"https://www.zhihu.com/answer/{answer_id}"


def fetch_all_answers(session: requests.Session, person_id: str, limit: int, pause: float) -> list[dict[str, object]]:
    offset = 0
    page_no = 1
    answers: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_offsets: set[int] = set()

    while True:
        if offset in seen_offsets:
            break
        seen_offsets.add(offset)
        payload = fetch_answers_page(session, person_id, offset=offset, limit=limit)
        data = payload.get("data") or []
        paging = payload.get("paging") or {}
        if not data:
            break

        added = 0
        for item in data:
            answer_id = str(item.get("id"))
            if not answer_id or answer_id in seen_ids:
                continue
            seen_ids.add(answer_id)
            added += 1

            question = item.get("question") or {}
            answer_url = item.get("url", "") or ""
            # Fix: if url is API endpoint, construct proper page URL
            if "/api/v4/" in answer_url or not answer_url.startswith("http"):
                answer_url = f"https://www.zhihu.com/answer/{answer_id}"
            answers.append(
                {
                    "id": answer_id,
                    "url": answer_url,
                    "question_id": question.get("id"),
                    "question_title": question.get("title"),
                    "created": item.get("created"),
                    "updated": item.get("updated"),
                    "created_at": format_ts(item.get("created")),
                    "updated_at": format_ts(item.get("updated")),
                    "excerpt": item.get("excerpt") or item.get("excerpt_new"),
                    "comment_count": item.get("comment_count"),
                    "voteup_count": item.get("voteup_count"),
                    "order": len(answers) + 1,
                }
            )

        total_hint = paging.get("totals")
        print(f"page={page_no} offset={offset} fetched={len(data)} added={added} total={len(answers)} totals_hint={total_hint}")
        if bool(paging.get("is_end")):
            break
        next_offset = extract_next_offset(paging, offset)
        if next_offset is None:
            break
        offset = next_offset
        page_no += 1
        if pause > 0:
            time.sleep(pause)

    return answers


def save_outputs(output_root: Path, person_id: str, answers: list[dict[str, object]]) -> None:
    ensure_dir(output_root)
    json_path = output_root / "answers_index.json"
    txt_path = output_root / "answer_links.txt"
    meta_path = output_root / "run_log.json"

    ordered_oldest_first = sorted(
        answers,
        key=lambda item: ((item.get("created") or 0), str(item.get("id") or "")),
    )
    for idx, item in enumerate(ordered_oldest_first, start=1):
        item["archive_order_oldest_first"] = idx

    json_path.write_text(json.dumps(ordered_oldest_first, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text("\n".join(item["url"] for item in ordered_oldest_first if item.get("url")), encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "type": "answers",
                "person_id": person_id,
                "saved_at": now_iso(),
                "answer_count": len(ordered_oldest_first),
                "json_path": str(json_path),
                "txt_path": str(txt_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"saved_json={json_path}")
    print(f"saved_txt={txt_path}")
    print(f"answer_count={len(ordered_oldest_first)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Zhihu answers for a person using cookie-authenticated requests.")
    parser.add_argument("--person-id", required=True, help="Zhihu people id, e.g. shan-chang-qing-yi")
    parser.add_argument("--cookie", required=True, help="Raw Zhihu cookie string.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--pause", type=float, default=0.6)
    parser.add_argument("--output-dir", help="Custom output directory")
    args = parser.parse_args()

    output_root = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT / f"{args.person_id}" / "answers"
    session = build_session(args.cookie)
    answers = fetch_all_answers(session, args.person_id, limit=args.limit, pause=args.pause)
    save_outputs(output_root, args.person_id, answers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
