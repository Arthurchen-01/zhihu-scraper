"""NLP Classifier & Sentiment/Risk Evaluator
Specifically tailored for detecting negative claims against 清一武道馆 / 清一新教育.
"""

from __future__ import annotations

import json
import re
from typing import Any
import requests


# 核心负面维度规则库
NEGATIVE_RULES = {
    "假武术/无实战能力/花架子": [
        r"不能打", r"没实[战力]", r"假武[术学]", r"花架子", r"花拳绣腿", r"假大师",
        r"不堪一击", r"挨揍", r"上擂台", r"不敢打", r"吹牛[逼皮]?", r"自嗨",
        r"传武骗局", r"假功夫", r"演戏", r"神化", r"神功", r"马保国", r"骗人.*武术",
        r"水平[太极很]?差", r"打不过", r"假把式", r"忽悠.*功夫", r"嘴炮"
    ],
    "骗子/圈钱/洗脑/割韭菜/套路": [
        r"骗子", r"骗人", r"诈骗", r"圈钱", r"割韭菜", r"洗脑", r"邪教",
        r"传销", r"套路", r"神棍", r"敛财", r"坑人", r"坑爹", r"避雷",
        r"虚假宣传", r"忽悠", r"千万别去", r"别上当", r"受骗", r"大忽悠",
        r"借机敛财", r"骗家长", r"骗钱", r"吃相难看", r"退钱"
    ],
    "新教育争议/误人子弟/毁孩子/伪国学": [
        r"误人子弟", r"毁[了掉]?孩子", r"害人", r"伪国学", r"害人不浅",
        r"耽误孩子", r"非法办学", r"没学籍", r"毒害", r"闭门造车",
        r"荒废学业", r"误导", r"毁了一生", r"误导大众", r"误导学员"
    ]
}

# 明确的正向/赞美词（用于过滤支持者言论）
PRAISE_PATTERNS = [
    r"感恩.*山长", r"感恩.*清一", r"事实和实力胜于一切", r"打得好", r"大慈悲",
    r"君子坦荡荡", r"光芒", r"黑暗.*光明", r"支持山长", r"清一太极.*比赛"
]


class NegativeEvaluator:
    def __init__(self, api_key: str = "", api_base: str = "https://api.deepseek.com/v1", model: str = "deepseek-chat"):
        self.api_key = api_key.strip()
        self.api_base = api_base.strip()
        self.model = model

    def evaluate(self, text: str, title: str = "", author_name: str = "") -> dict[str, Any]:
        """Evaluate whether a text contains negative / smearing claims."""
        full_text = f"{title}\n{text}".strip()
        if not full_text:
            return {"is_negative": False, "score": 0.0, "category": [], "risk_level": "NONE", "evidence": ""}

        # 1. 优先执行本地规则库精准过滤
        rule_result = self._rule_based_check(full_text)

        # 2. 如果配置了 LLM API Key 且规则判定为边缘情况，可调用 LLM 深度研判
        if self.api_key and (rule_result["is_negative"] or len(full_text) > 30):
            try:
                llm_res = self._llm_check(full_text, title, author_name)
                if llm_res is not None:
                    return llm_res
            except Exception as e:
                # LLM 失败回退到本地规则
                pass

        return rule_result

    def _rule_based_check(self, text: str) -> dict[str, Any]:
        # 检查是否命中纯赞美模式
        for p in PRAISE_PATTERNS:
            if re.search(p, text, re.I):
                # 除非同时有明确的“骗子”等强负面反讽，否则判定为支持者
                if not re.search(r"骗子|诈骗|邪教|割韭菜", text):
                    return {"is_negative": False, "score": 0.1, "category": ["支持/正面言论"], "risk_level": "NONE", "evidence": ""}

        matched_categories = []
        matched_snippets = []
        total_hits = 0

        for cat, patterns in NEGATIVE_RULES.items():
            cat_hits = 0
            for p in patterns:
                matches = re.finditer(p, text, re.I)
                for m in matches:
                    cat_hits += 1
                    # 提取关键词所在上下文（前后 15 字）
                    start = max(0, m.start() - 15)
                    end = min(len(text), m.end() + 15)
                    snippet = text[start:end].replace("\n", " ").strip()
                    if snippet not in matched_snippets:
                        matched_snippets.append(snippet)
            if cat_hits > 0:
                matched_categories.append(cat)
                total_hits += cat_hits

        if total_hits > 0:
            risk = "HIGH" if total_hits >= 2 or any(k in text for k in ["骗子", "诈骗", "邪教", "假武术", "误人子弟"]) else "MEDIUM"
            score = min(0.99, 0.6 + total_hits * 0.1)
            return {
                "is_negative": True,
                "score": score,
                "category": matched_categories,
                "risk_level": risk,
                "evidence": " | ".join(matched_snippets[:3]),
            }

        return {"is_negative": False, "score": 0.0, "category": [], "risk_level": "NONE", "evidence": ""}

    def _llm_check(self, text: str, title: str, author_name: str) -> dict[str, Any] | None:
        prompt = f"""请分析以下关于【清一武道馆 / 清一新教育】的言论，判断是否包含针对该品牌或人物的【负面、质疑、攻击、打假、控诉骗人、无实战能力、误人子弟】等负面倾向。

【标题/上下文】: {title}
【发帖人】: {author_name}
【文本内容】:
\"\"\"{text[:1000]}\"\"\"

请严格输出 JSON 格式（不要输出任何额外文字）：
{{
  "is_negative": true 或 false,
  "score": 0.0 到 1.0 之间的负面程度,
  "risk_level": "HIGH" 或 "MEDIUM" 或 "LOW" 或 "NONE",
  "category": ["假武术/无实战能力", "骗子/洗脑", "误人子弟"] 等标签列表,
  "summary": "一句话核心争议点摘要",
  "evidence": "最核心的负面原句或片段"
}}"""

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        r = requests.post(f"{self.api_base}/chat/completions", headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            res_json = r.json()
            content = res_json["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {
                "is_negative": bool(parsed.get("is_negative", False)),
                "score": float(parsed.get("score", 0.0)),
                "risk_level": str(parsed.get("risk_level", "NONE")),
                "category": list(parsed.get("category", [])),
                "evidence": str(parsed.get("evidence", "") or parsed.get("summary", "")),
            }
        return None
