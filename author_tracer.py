"""Author Tracer & Suspect Profiler
Traces a suspicious user's full Zhihu activity history to find coordinated or recurring smearing posts.
"""

from __future__ import annotations

import json
from typing import Any
from zhihu_client import ZhihuClient
from nlp_classifier import NegativeEvaluator


class AuthorTracer:
    def __init__(self, client: ZhihuClient, evaluator: NegativeEvaluator):
        self.client = client
        self.evaluator = evaluator
        self.traced_users: dict[str, dict[str, Any]] = {}

    def trace_user(self, url_token: str, user_name: str = "") -> dict[str, Any]:
        """Deep dive into a user's full Zhihu history."""
        if not url_token or url_token == "anonymous":
            return {}
        if url_token in self.traced_users:
            return self.traced_users[url_token]

        print(f"      [深度穿透] 正在调查可疑人员: {user_name or url_token} (https://www.zhihu.com/people/{url_token}) ...")

        # 1. 抓取基本资料
        profile_data = {}
        try:
            profile_data = self.client.get_user_profile(url_token)
        except Exception as e:
            print(f"      [警告] 获取用户基本资料失败: {e}")

        # 2. 抓取其全量历史动态（回答、文章、想法）
        all_content = self.client.fetch_user_all_content(url_token, max_items_per_type=60)
        
        # 3. 统计该用户在全网的所有负面言论
        negative_items = []
        total_items_checked = 0

        for c_type, items in all_content.items():
            for it in items:
                total_items_checked += 1
                res = self.evaluator.evaluate(it["content"], it.get("title", ""), user_name)
                if res["is_negative"]:
                    negative_items.append({
                        "type": it.get("type", c_type),
                        "title": it.get("title", ""),
                        "url": it.get("url", ""),
                        "content": it.get("content", ""),
                        "created_at": it.get("created_at", ""),
                        "voteup_count": it.get("voteup_count", 0),
                        "category": res["category"],
                        "risk_level": res["risk_level"],
                        "evidence": res["evidence"],
                    })

        user_summary = {
            "url_token": url_token,
            "name": profile_data.get("name") or user_name or url_token,
            "user_url": f"https://www.zhihu.com/people/{url_token}",
            "headline": profile_data.get("headline", ""),
            "description": profile_data.get("description", ""),
            "follower_count": profile_data.get("follower_count", 0),
            "following_count": profile_data.get("following_count", 0),
            "total_answers": profile_data.get("answer_count", len(all_content["answers"])),
            "total_articles": profile_data.get("articles_count", len(all_content["articles"])),
            "total_pins": profile_data.get("pins_count", len(all_content["pins"])),
            "negative_count": len(negative_items),
            "negative_items": negative_items,
            "is_frequent_attacker": len(negative_items) >= 2,
        }

        self.traced_users[url_token] = user_summary
        print(f"      [穿透结果] 用户 {user_summary['name']}: 共核查 {total_items_checked} 篇历史内容，命中 {len(negative_items)} 条相关负面言论。")
        return user_summary
