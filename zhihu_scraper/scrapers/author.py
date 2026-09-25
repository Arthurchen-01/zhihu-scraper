"""Zhihu Author Scraper & Asset Cataloger.
Scrapes author profile, bio, followers, columns, articles, answers, and pins.
Provides catalog_all_assets() for user inspection and selective checkboxes.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..client import ZhihuClient, safe_name, html_to_markdown

logger = logging.getLogger("zhihu_scraper.scrapers.author")


# 「动态」的独立硬上限：动态页数最多、最容易把配额翻爆，而它只用于
# 「发现我点赞/赞同过的别人的内容」，不需要全量。无论调用方传多大的
# max_per_category（含 0/None = 无上限），动态最多只翻这么多条。
ACTIVITY_HARD_CAP = 300

class AuthorScraper:
    """Scrapes all public assets belonging to a Zhihu user."""

    def __init__(self, client: ZhihuClient):
        self.client = client

    @staticmethod
    def extract_url_token(user_input: str) -> str:
        """Extract url_token from URL, e.g. https://www.zhihu.com/people/shou-qi-hei -> shou-qi-hei."""
        cleaned = user_input.strip()
        if "zhihu.com/people/" in cleaned:
            parsed = urlparse(cleaned)
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] == "people":
                return parts[1]
        # Return as-is if already a token
        return cleaned.split("?")[0].strip("/")

    def get_profile(self, url_token: str) -> Dict[str, Any]:
        """Fetch author full profile info.

        两条通道**都打并合并** —— 它们的字段互补，单用任何一条都会缺：

          · www.zhihu.com/api/v4/members/{token}?include=…
            免 x-zse-96 签名、最稳；给 articles_count / pins_count / columns_count
          · api.zhihu.com/people/{token}
            字段最全（98~121 个），给 answer_count 等 v4 不返回的字段

        合并顺序 v4 先、api 后覆盖：谁有值谁生效，任一条挂了另一条仍能兜底。
        （历史教训：只打 v4 会让「问答」永远是 0；只打 api 通道在配额紧张时
        容易先挨一个 403 而丢掉整份 profile。）
        """
        api_v4 = (
            f"https://www.zhihu.com/api/v4/members/{url_token}"
            "?include=headline,description,avatar_url,follower_count,"
            "voteup_count,thanked_count,articles_count,answers_count,"
            "pins_count,columns_count"
        )
        merged: Dict[str, Any] = {}
        for _u in (api_v4, f"https://api.zhihu.com/people/{url_token}"):
            _d = self.client.get_json(_u)
            if isinstance(_d, dict) and _d:
                merged.update(_d)

        # 字段名归一：v4 用 answers_count，api.zhihu.com 用 answer_count。
        # 不归一的话「问答」计数永远是 0（两条通道各缺一半）。
        if merged.get("answers_count") is None and merged.get("answer_count") is not None:
            merged["answers_count"] = merged["answer_count"]
        return merged

    def list_columns(self, url_token: str) -> List[Dict[str, Any]]:
        """List all columns owned or contributed to by this author."""
        url = f"https://www.zhihu.com/api/v4/members/{url_token}/column-contributions"
        columns = []
        for item in self.client.paginate(url, limit=20, max_items=100):
            col = item.get("column", item)
            columns.append({
                "type": "column",
                "id": col.get("id", ""),
                "title": col.get("title", ""),
                "url": f"https://www.zhihu.com/column/{col.get('id', '')}" if col.get("id") else col.get("url", ""),
                "description": col.get("description", ""),
                "articles_count": col.get("articles_count", 0),
                "author_name": col.get("author", {}).get("name", "")
            })
        return columns

    def list_articles(self, url_token: str, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all articles published by this author."""
        url = f"https://www.zhihu.com/api/v4/members/{url_token}/articles"
        articles = []
        fetch_limit = None if (max_items is None or max_items <= 0) else max_items
        for item in self.client.paginate(url, limit=20, max_items=fetch_limit):
            created_ts = int(item.get("created") or item.get("created_time") or 0)
            created_str = datetime.fromtimestamp(created_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_ts else ""
            created_date = created_str[:10] if created_str else ""
            articles.append({
                "type": "article",
                "id": str(item.get("id", "")),
                "title": item.get("title", "未命名文章"),
                "url": f"https://zhuanlan.zhihu.com/p/{item.get('id')}",
                "created_at": created_str,
                "created_date": created_date,
                "created_timestamp": created_ts,
                "updated_at": item.get("updated", 0),
                "voteup_count": item.get("voteup_count", 0),
                "comment_count": item.get("comment_count", 0),
                "excerpt": item.get("excerpt", "")
            })
        return articles

    def list_answers(self, url_token: str, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all answers written by this author."""
        url = f"https://www.zhihu.com/api/v4/members/{url_token}/answers?include=question,created_time,updated_time,voteup_count,comment_count,excerpt"
        answers = []
        fetch_limit = None if (max_items is None or max_items <= 0) else max_items
        for item in self.client.paginate(url, limit=20, max_items=fetch_limit):
            q = item.get("question", {})
            q_id = q.get("id", "")
            ans_id = item.get("id", "")
            created_ts = int(item.get("created_time") or item.get("created") or 0)
            created_str = datetime.fromtimestamp(created_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_ts else ""
            created_date = created_str[:10] if created_str else ""
            answers.append({
                "type": "answer",
                "id": str(ans_id),
                "question_id": str(q_id),
                "title": q.get("title", "未命名问答"),
                "url": f"https://www.zhihu.com/question/{q_id}/answer/{ans_id}",
                "created_at": created_str,
                "created_date": created_date,
                "created_timestamp": created_ts,
                "updated_at": item.get("updated_time", 0),
                "voteup_count": item.get("voteup_count", 0),
                "comment_count": item.get("comment_count", 0),
                "excerpt": item.get("excerpt", "")
            })
        return answers

    def list_pins(self, url_token: str, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all pins (想法) posted by this author."""
        url = f"https://www.zhihu.com/api/v4/members/{url_token}/pins"
        pins = []
        fetch_limit = None if (max_items is None or max_items <= 0) else max_items
        for item in self.client.paginate(url, limit=20, max_items=fetch_limit):
            pin_id = item.get("id", "")
            content_text = item.get("excerpt_title") or item.get("content", [{}])[0].get("content", "")
            created_ts = int(item.get("created") or item.get("created_time") or 0)
            created_str = datetime.fromtimestamp(created_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_ts else ""
            created_date = created_str[:10] if created_str else ""
            pins.append({
                "type": "pin",
                "id": str(pin_id),
                "title": content_text[:60] if content_text else f"想法_{pin_id}",
                "url": f"https://www.zhihu.com/pin/{pin_id}",
                "created_at": created_str,
                "created_date": created_date,
                "created_timestamp": created_ts,
                "voteup_count": item.get("reaction_count", 0),
                "comment_count": item.get("comment_count", 0),
                "excerpt": content_text
            })
        return pins

    def list_activities(self, url_token: str, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """List author's recent activities (动态全部), extracting underlying articles, answers, and pins."""
        url = f"https://www.zhihu.com/api/v3/moments/{url_token}/activities?desktop=true"
        activities = []
        fetch_limit = None if (max_items is None or max_items <= 0) else max_items
        for item in self.client.paginate(url, limit=10, max_items=fetch_limit):
            action_text = item.get("action_text", "")
            verb = item.get("verb", "")
            target = item.get("target", {})
            target_type = target.get("type", "activity")
            target_id = str(target.get("id", ""))

            created_ts = int(item.get("created_time") or target.get("created_time") or target.get("created") or 0)
            created_str = datetime.fromtimestamp(created_ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if created_ts else ""
            created_date = created_str[:10] if created_str else ""

            raw_title = target.get("title") or target.get("excerpt_title") or (target.get("question") or {}).get("title") or f"动态_{target_id}"
            
            raw_content = target.get("content")
            if isinstance(raw_content, list) and raw_content:
                excerpt = raw_content[0].get("content", "")
            elif isinstance(raw_content, str):
                excerpt = raw_content
            else:
                excerpt = target.get("excerpt", "")

            item_url = ""
            if target_type == "article":
                item_url = f"https://zhuanlan.zhihu.com/p/{target_id}"
            elif target_type == "answer":
                q_id = target.get("question", {}).get("id", "")
                item_url = f"https://www.zhihu.com/question/{q_id}/answer/{target_id}" if q_id else f"https://www.zhihu.com/answer/{target_id}"
            elif target_type == "pin":
                item_url = f"https://www.zhihu.com/pin/{target_id}"
            else:
                item_url = target.get("url") or f"https://www.zhihu.com/people/{url_token}"

            display_title = f"[{action_text}] {raw_title}" if action_text else raw_title

            # 这条动态指向的内容，到底是不是本人写的？
            #   True  = 明确是本人（target.author.url_token 就是本人）→ 属于原创资产
            #   False = 明确是别人（我赞同 / 点赞 了别人的东西）
            #   None  = 动态里没带作者信息，交给 catalog_all_assets 按 id 与自有资产比对
            _tgt_author = target.get("author") if isinstance(target, dict) else None
            if isinstance(_tgt_author, dict):
                _tgt_token = str(_tgt_author.get("url_token") or _tgt_author.get("id") or "").strip()
                own_flag = (_tgt_token == str(url_token)) if _tgt_token else None
            else:
                own_flag = None

            activities.append({
                "type": target_type if target_type in ["article", "answer", "pin"] else "activity",
                "is_activity": True,
                "is_own": own_flag,
                "origin": "activity",
                "action_text": action_text,
                "verb": verb,
                "id": target_id,
                "title": display_title,
                "raw_title": raw_title,
                "url": item_url,
                "created_at": created_str,
                "created_date": created_date,
                "created_timestamp": created_ts,
                "voteup_count": target.get("voteup_count", target.get("reaction_count", 0)),
                "comment_count": target.get("comment_count", 0),
                "excerpt": str(excerpt)[:200]
            })
        return activities

    def catalog_all_assets(
        self,
        user_input: str,
        include_articles: bool = True,
        include_answers: bool = True,
        include_pins: bool = True,
        include_columns: bool = True,
        include_activities: bool = True,
        max_per_category: int = 50
    ) -> Dict[str, Any]:
        """One-stop inspection method: resolves profile and returns all categorized assets."""
        token = self.extract_url_token(user_input)
        profile = self.get_profile(token)

        _diag: List[str] = []

        # 连主页都读不到 —— 后面所有计数必然全是 0。这是「一片 0」最常见的成因：
        # cookie 失效 / 格式不对 / 被风控。必须明说，否则用户只能干看着 0 猜。
        if not profile or not profile.get("id"):
            _diag.append(
                "没能读到该用户的主页信息 —— cookie 可能已失效或格式不对。"
                "请重新登录知乎、重新导出 cookie 后再试"
            )

        author_name = profile.get("name", token)
        headline = profile.get("headline", "")
        avatar = profile.get("avatar_url", "")
        profile_url = f"https://www.zhihu.com/people/{token}"

        assets = []
        cols = []

        def _note(kind: str, got: int, claimed: Any) -> None:
            """主页声称有 N 条、接口却一条都没给 —— 这是 cookie 被风控拦下的典型症状。

            正常空账号（主页计数也是 0）不会触发，所以这条只在「明显不对」时出现。
            """
            try:
                claimed_n = int(claimed or 0)
            except (TypeError, ValueError):
                claimed_n = 0
            if got == 0 and claimed_n > 0:
                _diag.append(
                    f"{kind}接口未返回任何数据（主页显示 {claimed_n} 条）"
                    "—— cookie 可能已被知乎风控拦截，请重新导出 cookie 再试"
                )

        # 下面这一段「动态」处理之前，assets 里全是从本人文章 / 回答 / 想法 / 专栏
        # 接口取回来的东西 —— 一律算本人原创。动态里才第一次出现的，才是
        # 「我点赞 / 赞同过的别人的内容」。
        _own_from_api = True

        if include_columns:
            try:
                cols = self.list_columns(token)
                assets.extend(cols)
            except Exception as e:
                logger.warning("Error fetching columns: %s", e)
            _note("专栏", len(cols), profile.get("columns_count"))

        if include_articles:
            try:
                arts = self.list_articles(token, max_items=max_per_category)
                assets.extend(arts)
            except Exception as e:
                logger.warning("Error fetching articles: %s", e)
                arts = []
            _note("文章", len(arts), profile.get("articles_count"))

        if include_pins:
            try:
                pins = self.list_pins(token, max_items=max_per_category)
                assets.extend(pins)
            except Exception as e:
                logger.warning("Error fetching pins: %s", e)
                pins = []
            _note("想法", len(pins), profile.get("pins_count"))

        if include_answers:
            try:
                ans = self.list_answers(token, max_items=max_per_category)
                assets.extend(ans)
            except Exception as e:
                logger.warning("Error fetching answers: %s", e)
                ans = []
            _note("问答", len(ans), profile.get("answers_count"))

        # 先给自有资产盖章：这些是本人原创，绝不能被「排除点赞内容」误伤。
        for _a in assets:
            _a.setdefault("is_own", True)
            _a.setdefault("origin", "own")

        if include_activities:
            try:
                # 动态单独套硬上限：即便调用方要「全量无上限」，也不让动态翻爆
                # （实测无上限时动态会翻到 59+ 页，必触 10003 限流）。
                if not max_per_category or max_per_category > ACTIVITY_HARD_CAP:
                    _act_cap = ACTIVITY_HARD_CAP
                else:
                    _act_cap = max_per_category
                acts = self.list_activities(token, max_items=_act_cap)
                # Avoid duplicate IDs if already present from articles/pins
                existing_ids = {str(a.get("id")) for a in assets}
                for act in acts:
                    if str(act.get("id")) not in existing_ids:
                        # 只出现在动态里。target.author 明确是本人 => 仍是原创资产
                        # （例如「转发了自己的文章」）；否则就是我点赞 / 赞同过的别人的内容。
                        if act.get("is_own") is None:
                            act["is_own"] = False
                        act["origin"] = "own" if act.get("is_own") else "activity"
                        assets.append(act)
                        existing_ids.add(str(act.get("id")))
                    else:
                        # 自有资产在动态里也出现过（例如我赞同/转发过自己的文章）
                        # —— 它仍然是本人的东西，只补上动态动作标签。
                        for a in assets:
                            if str(a.get("id")) == str(act.get("id")):
                                a["is_activity"] = True
                                a["action_text"] = act.get("action_text", "")
                                a["seen_in_activity"] = True
                                a["is_own"] = True
            except Exception as e:
                logger.warning("Error fetching activities: %s", e)

        # 限流兜底提示：这轮只要撞过一次 10003，结果就可能缺页。退避重试通常能
        # 把缺的补回来，但补不回来的情况下用户得知道「不是只有这么多」。
        if getattr(self.client, "rate_limited_seen", False):
            _diag.append(
                "检索过程中触发了知乎的频率限制，结果可能不完整 —— "
                "请等 1 分钟后再点一次「开始检索」，第二次通常是完整的"
            )

        return {
            "author": {
                "name": author_name,
                "url_token": token,
                "headline": headline,
                "avatar_url": avatar,
                "profile_url": profile_url,
                "articles_count": profile.get("articles_count", 0),
                "answers_count": profile.get("answers_count", 0),
                "pins_count": profile.get("pins_count", 0),
                "columns_count": len(cols) or profile.get("columns_count", 0)
            },
            "columns": cols,
            "total_items": len(assets),
            "items": assets,
            # 「主页说有 N 条、接口一条没给」的自检结论。正常账号恒为空列表。
            # 前端拿到非空就弹提示，避免用户看到一片 0 却不知道是 cookie 的问题。
            "warnings": _diag
        }
