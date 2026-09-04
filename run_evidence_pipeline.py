"""One-Click Zhihu Negative Evidence Gathering & Suspect Tracing Pipeline.
Fully standalone executable script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from zhihu_client import ZhihuClient, strip_html_tags
from nlp_classifier import NegativeEvaluator
from author_tracer import AuthorTracer
from reporter import EvidenceReporter

# Windows 终端中文支持
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = ROOT / "config.json"
OUTPUT_DIR = ROOT / "outputs"


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    return json.loads(config_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="知乎负面证据全量取证与人员穿透系统")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="配置文件路径")
    parser.add_argument("--brands", help="逗号分隔的品牌关键词，覆盖配置")
    parser.add_argument("--max-pages", type=int, default=2, help="每个关键词搜索页数 (每页20条)")
    parser.add_argument("--max-comments-per-post", type=int, default=50, help="单帖最大抓取评论数")
    parser.add_argument("--skip-user-trace", action="store_true", help="跳过可疑用户主页深度穿透")
    args = parser.parse_args()

    print("=" * 60)
    print(" 🚀 知乎负面证据全量取证与可疑人员穿透系统 (自动化独立版)")
    print("=" * 60)

    config = load_config(Path(args.config))
    cookie = config.get("cookie", "").strip()
    if not cookie:
        print("[错误] 未配置 Cookie，请在 config.json 中填入有效的知乎 Cookie！")
        return 1

    brands = [b.strip() for b in args.brands.split(",") if b.strip()] if args.brands else config.get("brands", ["清一武道馆", "清一新教育"])
    api_key = config.get("deepseek_api_key", "").strip()

    # 初始化组件
    client = ZhihuClient(cookie=cookie, pause_seconds=0.6)
    evaluator = NegativeEvaluator(api_key=api_key)
    tracer = AuthorTracer(client=client, evaluator=evaluator)
    reporter = EvidenceReporter(output_dir=OUTPUT_DIR)

    # 1. 验证登录
    print("\n[阶段 0/4] 验证知乎登录态...")
    try:
        me_info = client._get_json("https://www.zhihu.com/api/v4/me")
        print(f"  ✅ 登录成功！当前身份: {me_info.get('name')} (UID: {me_info.get('id')})")
    except Exception as e:
        print(f"  ❌ 登录验证失败或 Cookie 过期: {e}")
        return 1

    all_evidence: list[dict[str, Any]] = []
    seen_evidence_keys: set[str] = set()
    suspect_tokens: dict[str, str] = {}  # token -> name
    processed_targets: set[str] = set()

    # 2. 搜索与内容抓取
    print(f"\n[阶段 1/4] 开始全网检索品牌词: {brands} ...")

    for brand in brands:
        print(f"\n>>> 🔍 正在检索关键词: 【{brand}】...")
        for search_type in ["general", "article", "answer"]:
            for page in range(args.max_pages):
                offset = page * 20
                print(f"  正在获取 [{search_type}] 第 {page + 1} 页 (offset={offset})...")
                try:
                    search_res = client.search(brand, search_type=search_type, offset=offset, limit=20)
                except Exception as e:
                    print(f"    [警告] 搜索接口请求异常: {e}")
                    break

                items = search_res.get("data") or []
                if not items:
                    break

                for raw_item in items:
                    target = raw_item.get("object", {}) or raw_item
                    t_type = target.get("type", "")

                    # ── 处理回答 (Answer) ──────────────────────────────────
                    if t_type == "answer":
                        ans_id = str(target.get("id"))
                        if ans_id in processed_targets:
                            continue
                        processed_targets.add(ans_id)

                        q_info = target.get("question", {})
                        q_title = strip_html_tags(q_info.get("title", ""))
                        author_info = target.get("author", {})
                        author_name = author_info.get("name", "匿名用户")
                        author_token = author_info.get("url_token", "")
                        ans_content = strip_html_tags(target.get("content") or target.get("excerpt", ""))
                        ans_url = f"https://www.zhihu.com/answer/{ans_id}"
                        created_time = target.get("created_time") or target.get("updated_time")

                        # 1. 研判回答正文
                        eval_res = evaluator.evaluate(ans_content, title=q_title, author_name=author_name)
                        if eval_res["is_negative"]:
                            key = f"answer_{ans_id}"
                            if key not in seen_evidence_keys:
                                seen_evidence_keys.add(key)
                                all_evidence.append({
                                    "source_type": "回答正文",
                                    "parent_title": q_title,
                                    "parent_url": ans_url,
                                    "author_name": author_name,
                                    "author_token": author_token,
                                    "author_url": f"https://www.zhihu.com/people/{author_token}" if author_token else "",
                                    "content": ans_content,
                                    "created_at": target.get("created_at") or "",
                                    "voteup_count": target.get("voteup_count", 0),
                                    "risk_level": eval_res["risk_level"],
                                    "category": eval_res["category"],
                                    "evidence": eval_res["evidence"],
                                })
                                if author_token:
                                    suspect_tokens[author_token] = author_name
                                print(f"    🔴 命中负面回答! [{author_name}]: {eval_res['evidence'][:50]}")

                        # 2. 穿透抓取回答评论区
                        comments = client.fetch_all_comments_for_target("answers", ans_id, max_roots=args.max_comments_per_post)
                        for c in comments:
                            c_eval = evaluator.evaluate(c["content"], title=f"关于问题【{q_title}】的评论", author_name=c["author_name"])
                            if c_eval["is_negative"]:
                                c_key = f"comment_{c['id']}"
                                if c_key not in seen_evidence_keys:
                                    seen_evidence_keys.add(c_key)
                                    all_evidence.append({
                                        "source_type": "评论区(楼中楼)" if c["is_child"] else "评论区(主评)",
                                        "parent_title": q_title,
                                        "parent_url": ans_url,
                                        "author_name": c["author_name"],
                                        "author_token": c["author_token"],
                                        "author_url": c["author_url"],
                                        "content": c["content"],
                                        "created_at": c["created_at"],
                                        "voteup_count": c["voteup_count"],
                                        "risk_level": c_eval["risk_level"],
                                        "category": c_eval["category"],
                                        "evidence": c_eval["evidence"],
                                    })
                                    if c["author_token"]:
                                        suspect_tokens[c["author_token"]] = c["author_name"]
                                    print(f"      🔴 命中负面评论! [{c['author_name']}]: {c_eval['evidence'][:50]}")

                    # ── 处理文章 (Article) ──────────────────────────────────
                    elif t_type == "article":
                        art_id = str(target.get("id"))
                        if art_id in processed_targets:
                            continue
                        processed_targets.add(art_id)

                        art_title = strip_html_tags(target.get("title", ""))
                        author_info = target.get("author", {})
                        author_name = author_info.get("name", "匿名用户")
                        author_token = author_info.get("url_token", "")
                        art_content = strip_html_tags(target.get("content") or target.get("excerpt", ""))
                        art_url = f"https://zhuanlan.zhihu.com/p/{art_id}"

                        # 1. 研判文章正文
                        eval_res = evaluator.evaluate(art_content, title=art_title, author_name=author_name)
                        if eval_res["is_negative"]:
                            key = f"article_{art_id}"
                            if key not in seen_evidence_keys:
                                seen_evidence_keys.add(key)
                                all_evidence.append({
                                    "source_type": "专栏文章",
                                    "parent_title": art_title,
                                    "parent_url": art_url,
                                    "author_name": author_name,
                                    "author_token": author_token,
                                    "author_url": f"https://www.zhihu.com/people/{author_token}" if author_token else "",
                                    "content": art_content,
                                    "created_at": target.get("created_at") or "",
                                    "voteup_count": target.get("voteup_count", 0),
                                    "risk_level": eval_res["risk_level"],
                                    "category": eval_res["category"],
                                    "evidence": eval_res["evidence"],
                                })
                                if author_token:
                                    suspect_tokens[author_token] = author_name
                                print(f"    🔴 命中负面专栏! [{author_name}]: {eval_res['evidence'][:50]}")

                        # 2. 穿透抓取文章评论区
                        comments = client.fetch_all_comments_for_target("articles", art_id, max_roots=args.max_comments_per_post)
                        for c in comments:
                            c_eval = evaluator.evaluate(c["content"], title=f"关于文章【{art_title}】的评论", author_name=c["author_name"])
                            if c_eval["is_negative"]:
                                c_key = f"comment_{c['id']}"
                                if c_key not in seen_evidence_keys:
                                    seen_evidence_keys.add(c_key)
                                    all_evidence.append({
                                        "source_type": "评论区(楼中楼)" if c["is_child"] else "评论区(主评)",
                                        "parent_title": art_title,
                                        "parent_url": art_url,
                                        "author_name": c["author_name"],
                                        "author_token": c["author_token"],
                                        "author_url": c["author_url"],
                                        "content": c["content"],
                                        "created_at": c["created_at"],
                                        "voteup_count": c["voteup_count"],
                                        "risk_level": c_eval["risk_level"],
                                        "category": c_eval["category"],
                                        "evidence": c_eval["evidence"],
                                    })
                                    if c["author_token"]:
                                        suspect_tokens[c["author_token"]] = c["author_name"]
                                    print(f"      🔴 命中负面评论! [{c['author_name']}]: {c_eval['evidence'][:50]}")

    print(f"\n[阶段 2/4] 检索与评论扫描完成！共捕获负面言论: {len(all_evidence)} 条，锁定可疑用户: {len(suspect_tokens)} 人。")

    # 3. 可疑人员全网动态穿透
    suspects_profiles: dict[str, dict[str, Any]] = {}
    if not args.skip_user_trace and suspect_tokens:
        print(f"\n[阶段 3/4] 正在对 {len(suspect_tokens)} 位可疑发帖人进行个人主页全量历史发言深度穿透...")
        for token, name in suspect_tokens.items():
            profile = tracer.trace_user(token, name)
            if profile:
                suspects_profiles[token] = profile

    # 4. 导出报表与证据卷宗
    print("\n[阶段 4/4] 正在生成 Excel 证据表与 Markdown 证据卷宗...")
    exported_files = reporter.export_all(
        brand=" / ".join(brands[:2]),
        evidence_list=all_evidence,
        suspects_dict=suspects_profiles
    )

    print("\n" + "=" * 60)
    print(" 🎉 全量排查与取证完成！")
    print(f" 📊 累计提取负面证据: {len(all_evidence)} 条")
    print(f" 👤 穿透可疑用户画像: {len(suspects_profiles)} 人")
    print("\n 📁 生成报告清单:")
    for k, path in exported_files.items():
        print(f"   - [{k}] -> {path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[已手动中断]")
        sys.exit(0)
