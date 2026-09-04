"""Zhihu Martial Arts & Wudaoguan Negative Reputation Deep Penetration Engine.
Specifically targets attacks against 清一武道馆, 文人格斗, 张清一/张健柏武术实战, 假大师, 不能打, 花架子, 假传武.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from zhihu_client import ZhihuClient, strip_html_tags
from nlp_classifier import NegativeEvaluator
from author_tracer import AuthorTracer

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
OUTPUTS_DIR = ROOT / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# 专属【武道馆 / 武道实战】攻击判定模式
WUDAO_ATTACK_KEYWORDS = [
    "假武术", "不能打", "没实力", "花架子", "假大师", "打假", "不敢实战", "不敢打",
    "吹牛", "摆拍", "套路", "神论", "假传武", "骗子", "假拳", "无实战", "没实战能力",
    "骗学费", "误人子弟", "弱鸡", "花拳绣腿", "传武骗局", "大师", "神化", "马保国"
]

WUDAO_BRAND_TERMS = [
    "武道馆", "武道", "文人格斗", "格斗", "实战", "泰拳", "散打", "柔术", "传武", "功夫", "武术", "搏击", "张健柏", "清一"
]

# 己方账号白名单（严禁误杀）
PRO_AUTHORS = {
    "shan-chang-qing-yi": "山长 清一",
    "shan-chang-tou-zi-hao": "清一投资号",
    "jin-ji-de-qing-fen": "进击的清粉",
    "ellaqing-yi-gong-zhu-no1": "Ella清一公主NO.1",
    "cai-kai-qi-88": "蔡凯琪",
    "ming-xiao-wen-ren-ge-dou": "明晓-文人格斗",
    "chang-sha-shi-zhi-xiong": "长沙实之兄",
    "lu-jia-yi-10": "卢嘉仪"
}


def is_wudao_attack(text: str, author_token: str = "") -> tuple[bool, str]:
    if author_token in PRO_AUTHORS:
        return False, "己方/学员白名单"
    
    text_clean = re.sub(r"<[^>]+>", "", text).strip()
    
    # 必须与武道相关
    has_wudao = any(w in text_clean for w in WUDAO_BRAND_TERMS)
    if not has_wudao:
        return False, "与武道馆无关"
    
    # 必须包含攻击/质疑词
    hit_neg = [k for k in WUDAO_ATTACK_KEYWORDS if k in text_clean]
    if not hit_neg:
        return False, "无武道攻击特征"
    
    return True, f"命中武道攻击词: {', '.join(hit_neg[:3])}"


def run_wudao_audit(target_user_list: list[str] = None):
    print("=" * 60)
    print("🥋 启动【清一武道馆 / 文人格斗】专属武道负面舆情与黑号深度穿透")
    print("=" * 60)

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    client = ZhihuClient(cookie=config.get("cookie", ""))
    evaluator = NegativeEvaluator(api_key=config.get("deepseek_api_key", ""))
    tracer = AuthorTracer(client=client, evaluator=evaluator)

    results = []
    
    # 1. 若提供了目标黑子名单，逐个深入其主页全量排查
    if target_user_list:
        print(f"\n🎯 正在对指定的 {len(target_user_list)} 位典型黑子进行武道相关穿透排查...")
        for u_name in target_user_list:
            u_name = u_name.strip()
            if not u_name:
                continue
            print(f"\n🔍 正在检索黑子: 【{u_name}】...")
            # 搜索该用户发表的相关内容
            try:
                search_res = client.search(f"{u_name} 清一武道馆", search_type="general", limit=20)
                items = search_res.get("data", [])
                for raw in items:
                    target = raw.get("object", {}) or raw
                    content = strip_html_tags(target.get("content") or target.get("excerpt", ""))
                    author = target.get("author", {})
                    author_name = author.get("name", "")
                    author_token = author.get("url_token", "")
                    
                    is_hit, reason = is_wudao_attack(content, author_token)
                    if is_hit:
                        results.append({
                            "目标黑子": u_name,
                            "发帖人昵称": author_name,
                            "发帖人Token": author_token,
                            "来源类型": target.get("type", "回答/文章"),
                            "标题/问题": strip_html_tags(target.get("title") or target.get("question", {}).get("title", "")),
                            "攻击原句": content,
                            "判定依据": reason,
                            "链接": f"https://www.zhihu.com/{target.get('type')}/{target.get('id')}"
                        })
                        print(f"  🔴 命中武道黑帖: [{author_name}] {content[:50]}...")
            except Exception as e:
                print(f"  ⚠️ 查询异常: {e}")

    # 2. 对武道专属关键词进行深度全网抓取
    wudao_keywords = [
        "清一武道馆", "文人格斗", "清一 假武术", "清一 不能打", "清一 花架子",
        "清一武道馆 骗局", "张健柏 武术", "清一 实战", "张清一 格斗", "清一 传武"
    ]
    print(f"\n🥋 正在全网深度扫描武道馆专属关键词 ({len(wudao_keywords)} 个)...")
    for kw in wudao_keywords:
        print(f"🔍 扫描: 【{kw}】...")
        try:
            res = client.search(kw, search_type="general", limit=20)
            items = res.get("data", [])
            for raw in items:
                target = raw.get("object", {}) or raw
                content = strip_html_tags(target.get("content") or target.get("excerpt", ""))
                author = target.get("author", {})
                author_name = author.get("name", "")
                author_token = author.get("url_token", "")
                t_id = str(target.get("id"))
                t_type = target.get("type", "")

                is_hit, reason = is_wudao_attack(content, author_token)
                if is_hit:
                    results.append({
                        "目标黑子": "全网捕获",
                        "发帖人昵称": author_name,
                        "发帖人Token": author_token,
                        "来源类型": f"{t_type}正文",
                        "标题/问题": strip_html_tags(target.get("title") or target.get("question", {}).get("title", "")),
                        "攻击原句": content,
                        "判定依据": reason,
                        "链接": f"https://www.zhihu.com/{t_type}/{t_id}"
                    })
                    print(f"  🔴 命中武道黑帖: [{author_name}] {content[:50]}...")

                # 穿透抓取评论区
                if t_type in ["answer", "article"]:
                    api_type = "answers" if t_type == "answer" else "articles"
                    comments = client.fetch_all_comments_for_target(api_type, t_id, max_roots=30)
                    for c in comments:
                        c_hit, c_reason = is_wudao_attack(c["content"], c["author_token"])
                        if c_hit:
                            results.append({
                                "目标黑子": "评论区捕获",
                                "发帖人昵称": c["author_name"],
                                "发帖人Token": c["author_token"],
                                "来源类型": "评论区(楼中楼)" if c["is_child"] else "评论区(主评)",
                                "标题/问题": f"针对【{target.get('title') or target.get('question', {}).get('title', '')}】",
                                "攻击原句": c["content"],
                                "判定依据": c_reason,
                                "链接": c["author_url"]
                            })
                            print(f"    🔴 命中武道负面评论: [{c['author_name']}] {c['content'][:50]}...")
        except Exception as e:
            print(f"  ⚠️ 扫描异常: {e}")

    # 导出专项目录
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    df = pd.DataFrame(results).drop_duplicates(subset=["发帖人Token", "攻击原句"])
    excel_path = OUTPUTS_DIR / f"清一武道馆_专属黑帖证据清单_{now_str}.xlsx"
    df.to_excel(excel_path, index=False)
    print("\n" + "=" * 60)
    print(f"✅ 武道馆专项目标排查完成！共捕获 {len(df)} 条针对武道/实战的真实攻击证据！")
    print(f"📁 Excel 证据报表已保存: {excel_path}")
    print("=" * 60)
    return df


if __name__ == "__main__":
    run_wudao_audit()
