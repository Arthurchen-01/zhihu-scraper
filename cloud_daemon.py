"""Zhihu Continuous Cloud Monitor Daemon Engine.
Runs 24/7 in the background on the cloud server, performing continuous deep searches,
recursive comment scraping, AI stance auditing, suspect author profiling,
and persistent SQLite deduplicated storage.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from zhihu_client import ZhihuClient, strip_html_tags
from nlp_classifier import NegativeEvaluator
from author_tracer import AuthorTracer
from ai_deep_audit import audit_stance

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("monitor_daemon.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("ZhihuDaemon")

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "zhihu_monitor.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # 1. 证据表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                source_type TEXT,
                parent_title TEXT,
                parent_url TEXT,
                author_name TEXT,
                author_token TEXT,
                author_url TEXT,
                content TEXT,
                created_at TEXT,
                voteup_count INTEGER DEFAULT 0,
                risk_level TEXT,
                category TEXT,
                evidence_quote TEXT,
                ai_verdict TEXT,
                is_true_negative INTEGER DEFAULT 0,
                first_seen_at TEXT
            )
        """)
        # 2. 可疑人员表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS suspect_users (
                url_token TEXT PRIMARY KEY,
                user_name TEXT,
                user_url TEXT,
                headline TEXT,
                follower_count INTEGER DEFAULT 0,
                total_answers INTEGER DEFAULT 0,
                total_articles INTEGER DEFAULT 0,
                true_attack_count INTEGER DEFAULT 0,
                is_core_attacker INTEGER DEFAULT 0,
                last_updated_at TEXT,
                attack_snippets TEXT
            )
        """)
        # 3. 扫描状态与统计表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_no INTEGER,
                keyword TEXT,
                search_type TEXT,
                items_scanned INTEGER,
                negative_found INTEGER,
                timestamp TEXT
            )
        """)
        conn.commit()


def save_evidence_item(item: dict[str, Any]) -> bool:
    """Save an evidence item to DB with deduplication. Returns True if newly inserted."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM evidence WHERE id = ?", (item["id"],))
        if cur.fetchone():
            return False
        
        cur.execute("""
            INSERT INTO evidence (
                id, source_type, parent_title, parent_url, author_name,
                author_token, author_url, content, created_at, voteup_count,
                risk_level, category, evidence_quote, ai_verdict, is_true_negative, first_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["id"], item.get("source_type", ""), item.get("parent_title", ""), item.get("parent_url", ""),
            item.get("author_name", ""), item.get("author_token", ""), item.get("author_url", ""),
            item.get("content", ""), item.get("created_at", ""), item.get("voteup_count", 0),
            item.get("risk_level", ""), "、".join(item.get("category", [])), item.get("evidence", ""),
            item.get("ai_verdict", ""), 1 if item.get("is_true_negative") else 0,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        return True


def update_suspect_user(user_profile: dict[str, Any]):
    """Update suspect user in DB."""
    token = user_profile.get("url_token")
    if not token or token == "anonymous":
        return
    
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        snippets = " || ".join([it.get("evidence") or it.get("content", "")[:60] for it in user_profile.get("negative_items", [])[:5]])
        cur.execute("""
            INSERT INTO suspect_users (
                url_token, user_name, user_url, headline, follower_count,
                total_answers, total_articles, true_attack_count, is_core_attacker,
                last_updated_at, attack_snippets
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url_token) DO UPDATE SET
                user_name=excluded.user_name,
                headline=excluded.headline,
                follower_count=excluded.follower_count,
                total_answers=excluded.total_answers,
                total_articles=excluded.total_articles,
                true_attack_count=excluded.true_attack_count,
                is_core_attacker=excluded.is_core_attacker,
                last_updated_at=excluded.last_updated_at,
                attack_snippets=excluded.attack_snippets
        """, (
            token, user_profile.get("name", token), user_profile.get("user_url", ""),
            user_profile.get("headline", ""), user_profile.get("follower_count", 0),
            user_profile.get("total_answers", 0), user_profile.get("total_articles", 0),
            user_profile.get("negative_count", 0), 1 if user_profile.get("is_frequent_attacker") else 0,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), snippets
        ))
        conn.commit()


# 深度扩展关键词列表
EXTENDED_KEYWORDS = [
    # 核心实体
    "清一武道馆", "清一新教育", "山长清一", "清一山长", "今日学堂", "今日塾", "张健柏", "文人格斗", "明心学堂",
    # 负面组合词
    "清一 骗子", "清一 割韭菜", "清一 洗脑", "清一 邪教", "清一 退费", "清一 坑", "清一 避雷",
    "今日学堂 骗", "张健柏 骗", "清一武道馆 假", "清一 传武", "清一 实战", "张清一 骗局",
    "清一 误人子弟", "今日学堂 洗脑", "今日学堂 害人", "清一 敛财"
]


def run_continuous_monitor():
    init_db()
    logger.info("🚀 知乎云端 7x24 小时全网深度持续监控引擎启动")
    
    round_no = 1
    while True:
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            config = {}
            
        cookie = config.get("cookie", "").strip()
        if not cookie:
            logger.error("未找到有效的 Cookie，休眠 60 秒后重试...")
            time.sleep(60)
            continue
            
        client = ZhihuClient(cookie=cookie, pause_seconds=0.8)
        evaluator = NegativeEvaluator(api_key=config.get("deepseek_api_key", ""))
        tracer = AuthorTracer(client=client, evaluator=evaluator)
        
        keywords = config.get("keywords", EXTENDED_KEYWORDS)
        max_pages = config.get("max_pages_per_keyword", 5)
        max_comments = config.get("max_comments_per_post", 50)
        
        logger.info(f"========== 🔄 开始第 {round_no} 轮全网深度巡检 (共 {len(keywords)} 个关键词, 每词 {max_pages} 页) ==========")
        
        new_evidences_count = 0
        suspects_to_trace: dict[str, str] = {}
        
        for kw_idx, kw in enumerate(keywords, 1):
            logger.info(f"[{kw_idx}/{len(keywords)}] 正在深度扫描关键词: 【{kw}】...")
            for search_type in ["general", "answer", "article"]:
                for page in range(max_pages):
                    offset = page * 20
                    try:
                        res = client.search(kw, search_type=search_type, offset=offset, limit=20)
                    except Exception as e:
                        logger.warning(f"搜索接口请求异常 ({kw}/{search_type}/p{page}): {e}")
                        break
                    
                    items = res.get("data") or []
                    if not items:
                        break
                    
                    for raw in items:
                        target = raw.get("object", {}) or raw
                        t_type = target.get("type", "")
                        
                        # 1. 回答 (Answer)
                        if t_type == "answer":
                            ans_id = str(target.get("id"))
                            q_info = target.get("question", {})
                            q_title = strip_html_tags(q_info.get("title", ""))
                            author_info = target.get("author", {})
                            author_name = author_info.get("name", "匿名用户")
                            author_token = author_info.get("url_token", "")
                            ans_content = strip_html_tags(target.get("content") or target.get("excerpt", ""))
                            ans_url = f"https://www.zhihu.com/answer/{ans_id}"
                            
                            # 正文审核
                            audit_res = audit_stance({
                                "言论发布者": author_name,
                                "作者UID/Token": author_token,
                                "父级标题/问题": q_title,
                                "完整言论原文": ans_content
                            })
                            
                            if audit_res["is_true_negative"]:
                                item_dict = {
                                    "id": f"answer_{ans_id}",
                                    "source_type": "回答正文",
                                    "parent_title": q_title,
                                    "parent_url": ans_url,
                                    "author_name": author_name,
                                    "author_token": author_token,
                                    "author_url": f"https://www.zhihu.com/people/{author_token}" if author_token else "",
                                    "content": ans_content,
                                    "created_at": target.get("created_at") or "",
                                    "voteup_count": target.get("voteup_count", 0),
                                    "risk_level": "HIGH",
                                    "category": [audit_res["clean_category"]],
                                    "evidence": audit_res["reason"],
                                    "ai_verdict": audit_res["verdict"],
                                    "is_true_negative": True
                                }
                                if save_evidence_item(item_dict):
                                    new_evidences_count += 1
                                    logger.info(f"  🔴 [新发现负面回答] [{author_name}]: {ans_content[:50]}")
                                    if author_token:
                                        suspects_to_trace[author_token] = author_name
                            
                            # 穿透抓取评论
                            comments = client.fetch_all_comments_for_target("answers", ans_id, max_roots=max_comments)
                            for c in comments:
                                c_audit = audit_stance({
                                    "言论发布者": c["author_name"],
                                    "作者UID/Token": c["author_token"],
                                    "父级标题/问题": f"问题【{q_title}】",
                                    "完整言论原文": c["content"]
                                })
                                if c_audit["is_true_negative"]:
                                    c_item = {
                                        "id": f"comment_{c['id']}",
                                        "source_type": "评论区(楼中楼)" if c["is_child"] else "评论区(主评)",
                                        "parent_title": q_title,
                                        "parent_url": ans_url,
                                        "author_name": c["author_name"],
                                        "author_token": c["author_token"],
                                        "author_url": c["author_url"],
                                        "content": c["content"],
                                        "created_at": c["created_at"],
                                        "voteup_count": c["voteup_count"],
                                        "risk_level": "HIGH",
                                        "category": [c_audit["clean_category"]],
                                        "evidence": c_audit["reason"],
                                        "ai_verdict": c_audit["verdict"],
                                        "is_true_negative": True
                                    }
                                    if save_evidence_item(c_item):
                                        new_evidences_count += 1
                                        logger.info(f"    🔴 [新发现负面评论] [{c['author_name']}]: {c['content'][:50]}")
                                        if c["author_token"]:
                                            suspects_to_trace[c["author_token"]] = c["author_name"]
                        
                        # 2. 文章 (Article)
                        elif t_type == "article":
                            art_id = str(target.get("id"))
                            art_title = strip_html_tags(target.get("title", ""))
                            author_info = target.get("author", {})
                            author_name = author_info.get("name", "匿名用户")
                            author_token = author_info.get("url_token", "")
                            art_content = strip_html_tags(target.get("content") or target.get("excerpt", ""))
                            art_url = f"https://zhuanlan.zhihu.com/p/{art_id}"
                            
                            audit_res = audit_stance({
                                "言论发布者": author_name,
                                "作者UID/Token": author_token,
                                "父级标题/问题": art_title,
                                "完整言论原文": art_content
                            })
                            if audit_res["is_true_negative"]:
                                item_dict = {
                                    "id": f"article_{art_id}",
                                    "source_type": "专栏文章",
                                    "parent_title": art_title,
                                    "parent_url": art_url,
                                    "author_name": author_name,
                                    "author_token": author_token,
                                    "author_url": f"https://www.zhihu.com/people/{author_token}" if author_token else "",
                                    "content": art_content,
                                    "created_at": target.get("created_at") or "",
                                    "voteup_count": target.get("voteup_count", 0),
                                    "risk_level": "HIGH",
                                    "category": [audit_res["clean_category"]],
                                    "evidence": audit_res["reason"],
                                    "ai_verdict": audit_res["verdict"],
                                    "is_true_negative": True
                                }
                                if save_evidence_item(item_dict):
                                    new_evidences_count += 1
                                    logger.info(f"  🔴 [新发现负面专栏] [{author_name}]: {art_content[:50]}")
                                    if author_token:
                                        suspects_to_trace[author_token] = author_name
                            
                            # 穿透抓取文章评论
                            comments = client.fetch_all_comments_for_target("articles", art_id, max_roots=max_comments)
                            for c in comments:
                                c_audit = audit_stance({
                                    "言论发布者": c["author_name"],
                                    "作者UID/Token": c["author_token"],
                                    "父级标题/问题": f"文章【{art_title}】",
                                    "完整言论原文": c["content"]
                                })
                                if c_audit["is_true_negative"]:
                                    c_item = {
                                        "id": f"comment_{c['id']}",
                                        "source_type": "评论区(楼中楼)" if c["is_child"] else "评论区(主评)",
                                        "parent_title": art_title,
                                        "parent_url": art_url,
                                        "author_name": c["author_name"],
                                        "author_token": c["author_token"],
                                        "author_url": c["author_url"],
                                        "content": c["content"],
                                        "created_at": c["created_at"],
                                        "voteup_count": c["voteup_count"],
                                        "risk_level": "HIGH",
                                        "category": [c_audit["clean_category"]],
                                        "evidence": c_audit["reason"],
                                        "ai_verdict": c_audit["verdict"],
                                        "is_true_negative": True
                                    }
                                    if save_evidence_item(c_item):
                                        new_evidences_count += 1
                                        logger.info(f"    🔴 [新发现负面评论] [{c['author_name']}]: {c['content'][:50]}")
                                        if c["author_token"]:
                                            suspects_to_trace[c["author_token"]] = c["author_name"]

        # 深度穿透发现的新可疑用户
        if suspects_to_trace:
            logger.info(f"👤 本轮发现 {len(suspects_to_trace)} 位新可疑发帖人，正在穿透其个人主页历史动态...")
            for token, name in suspects_to_trace.items():
                p = tracer.trace_user(token, name)
                if p:
                    update_suspect_user(p)
        
        logger.info(f"🎉 第 {round_no} 轮全网扫描完成！新增真实负面证据: {new_evidences_count} 条。")
        round_no += 1
        
        # 轮次间歇休眠（默认 30 分钟轮询一次增量）
        interval = config.get("round_interval_minutes", 30) * 60
        logger.info(f"⏳ 休眠 {interval // 60} 分钟后开始下一轮持续增量巡查...")
        time.sleep(interval)


if __name__ == "__main__":
    try:
        run_continuous_monitor()
    except KeyboardInterrupt:
        logger.info("Daemon gracefully stopped.")
