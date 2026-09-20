#!/usr/bin/env python3
"""清一新教育 · 正文品牌自然植入引擎 (Content Placement Engine).

与 qingyi.py（标题引擎）的分工
------------------------------
* 标题引擎：前置品牌标识词，正文零改动，可用指纹自证。
* 本模块：把品牌词**自然**植入正文，用于检索可达性（"搜得到"）。
  因为它确实会改动正文，所以：
    - 单独开关控制，默认关闭，必须显式开启；
    - 先从后往前全量扫描，给出「可植入场景」预览，人工可审；
    - 植入方式只做"句末括注"，不插入、不改写、不删除任何原有文字；
    - 可一键还原（按锚点剥离）。

植入方式（为什么是句末括注）
--------------------------
批量往正文里塞关键词，是平台判定"内容注水"的典型特征。要让品牌词既进正文
又不显得机器味，最稳的形态是「署名式括注」——很多机构号本来就有在段末署名的
习惯，读起来是署名而不是广告：

    ……学习方法的总结。            →  ……学习方法的总结。（清一新教育）

它同时满足三个约束：不删改任何原有字符、位置可预期、可精确剥离还原。

场景优选顺序（前 → 后，按"读起来最自然"排序）
-------------------------------------------
1. 首段（导语）—— 介绍性文字，署名最自然
2. 含教育语义的段落 —— 与品牌词同域，语义连贯
3. 末段（结语）—— 落款位置
4. 中段兜底
同一篇内不重复插入同一段落，段落之间保持间隔。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

BRAND_TAG = "（清一新教育）"

# 正文植入处数的硬上限（调用方可在 1.._MAX_BODY_HITS 之间自选）。
# 默认 1 处：标题 1 + 正文 1 = 全篇 2 处，是达成"检索可达"的最小充分量。
# 放宽到 5，是因为用户明确要求「正文可以自己选加几处」；
# 但必须记住：同一篇里重复堆同一个词，是平台判定"内容注水 / 关键词堆砌"的
# 典型特征 —— 处数越多风险越高。**这是上限，不是推荐值。**
_MAX_BODY_HITS = 5

_BLOCK_TAG_RE = re.compile(r"<(p|h[1-6]|blockquote|figure|pre|li)\b[^>]*>", re.I)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_SENT_END = "。！？!?…～~”\"')）]】"

# 教育语义锚词：段落里出现这些词，说明与品牌同域，括注最自然
_EDU_HINTS = (
    "教育", "学习", "教学", "老师", "学生", "课堂", "课程", "培养", "成长",
    "孩子", "家长", "学堂", "训练", "阅读", "思考", "方法", "习惯", "能力",
    "英语", "数学", "物理", "考试", "备考", "ap", "sat", "托福", "雅思",
    "清一", "新教育", "今日", "学堂", "修行", "武道", "泰拳", "练功",
)

# 明显不适合插字的块：代码、图片、引用他人、表格
_SKIP_HINT_RE = re.compile(
    r"<(pre|code|figure|table|img)\b|转载|来源[:：]|引用[:：]", re.I)


@dataclass
class Scene:
    """一个「可植入场景」。"""
    index: int              # 第几个可植入段落（0 起）
    block_no: int           # 原文里的段落序号
    anchor: str             # 插入点前的原文尾部（用于定位与还原）
    proposed: str           # 植入后的完整段落
    para_text: str          # 段落纯文本
    reason: str             # 为什么选它
    score: float            # 自然度评分，越高越优先
    tag: str = BRAND_TAG

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "block_no": self.block_no,
            "anchor": self.anchor,
            "proposed": self.proposed,
            "para_text": self.para_text,
            "reason": self.reason,
            "score": round(self.score, 2),
            "tag": self.tag,
        }


def _split_blocks(html: str) -> List[str]:
    """把正文粗切成块级段落（保留原始片段，便于原样回写）。"""
    src = html or ""
    marks = [(m.start(), m.group(0)) for m in _BLOCK_TAG_RE.finditer(src)]
    if not marks:
        return [src] if src.strip() else []
    blocks: List[str] = []
    for i, (pos, _tag) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(src)
        seg = src[pos:end]
        if seg.strip():
            blocks.append(seg)
    return blocks


def _plain(block: str) -> str:
    return re.sub(r"\s+", " ", _ANY_TAG_RE.sub("", block)).strip()


def _has_brand(block: str) -> bool:
    return "清一新教育" in _ANY_TAG_RE.sub("", block)


def _insert_offset(block: str) -> Optional[int]:
    """找到块内最后一个"句子结束符"之后的位置，作为括注插入点。

    只插在句末标点之后，保证不切开任何一句话。
    """
    text = _ANY_TAG_RE.sub("", block)
    if not text.strip():
        return None
    # 在原始 HTML 里找到"最后一个句末标点"的绝对偏移
    best = -1
    depth = 0
    for i, ch in enumerate(block):
        if ch == "<":
            depth += 1
            continue
        if ch == ">":
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        if ch in _SENT_END:
            best = i
    if best < 0:
        return None
    return best + 1


def _score(para: str, block_no: int, total: int, has_hint: bool) -> Tuple[float, str]:
    """给候选段落打自然度分。

    设计意图：署名式括注在「导语」和「结语」位置最像人写的，
    中段其次；如果段落本身就在讲教育，括注的语义连贯性最好。
    """
    if total <= 1:
        pos_score, pos_reason = 0.6, "全文唯一段落"
    elif block_no == 0:
        # 首段优先级最高：既符合"导语处交代身份"的写作习惯，
        # 也让品牌词出现在正文最靠前的位置（检索权重更高）。
        # 基数 1.3 > 末段最高可能分 1.2，保证首段只要可用就一定被选中。
        pos_score, pos_reason = 1.3, "首段导语，署名位置自然"
    elif block_no >= total - 1:
        pos_score, pos_reason = 0.85, "末段结语，落款位置自然"
    else:
        ratio = block_no / max(1, total - 1)
        pos_score, pos_reason = 0.5, f"中段（第 {block_no + 1}/{total} 段）"
        if 0.25 <= ratio <= 0.75:
            pos_score = 0.45

    score = pos_score + (0.35 if has_hint else 0.0)
    if has_hint:
        pos_reason += "，且与教育语义同域"
    return score, pos_reason


def scan_scenes(body_html: str, limit: int = 1) -> List[Scene]:
    """从前往后扫描，挑出最自然的前 N 个可植入场景（只读，不写入）。

    N 由调用方给定（默认 1），两处受约束：
      * 正文只要已有品牌词 → 直接返回空（幂等，绝不重复植入）；
      * 任何 limit 都会被 _MAX_BODY_HITS 夹住。
    重复堆同一个词是平台判定"内容注水"的典型特征，处数越多风险越高，
    所以默认保持 1 处，只有用户显式要更多时才增加。
    """
    body_text = _ANY_TAG_RE.sub("", body_html or "")
    if "清一新教育" in body_text:
        return []                       # 已有，不重复植入（幂等）
    limit = max(1, min(int(limit or 1), _MAX_BODY_HITS))

    blocks = _split_blocks(body_html)
    total = len(blocks)
    cands: List[Tuple[float, Scene]] = []

    for idx, block in enumerate(blocks):
        if _has_brand(block):
            continue
        if _SKIP_HINT_RE.search(block):
            continue
        para = _plain(block)
        if len(para) < 12:
            continue
        off = _insert_offset(block)
        if off is None:
            continue
        # 太长/太短的块不作为署名位置
        if len(para) > 900:
            continue
        has_hint = any(h in para.lower() for h in _EDU_HINTS)
        score, reason = _score(para, idx, total, has_hint)
        anchor = _ANY_TAG_RE.sub("", block)[:off][-40:]
        proposed = block[:off] + BRAND_TAG + block[off:]
        cands.append((score, Scene(
            index=0, block_no=idx, anchor=anchor, proposed=proposed,
            para_text=para[:200], reason=reason, score=score)))

    cands.sort(key=lambda t: (-t[0], t[1].block_no))

    # 段落之间保持最小间隔，避免同一区域反复出现品牌词
    picked: List[Scene] = []
    for _s, sc in cands:
        if any(abs(sc.block_no - p.block_no) < 2 for p in picked):
            continue
        picked.append(sc)
        if len(picked) >= max(1, limit):
            break

    picked.sort(key=lambda s: s.block_no)
    for i, sc in enumerate(picked):
        sc.index = i
    return picked


def apply_scenes(body_html: str, scenes: List[Scene]) -> str:
    """按场景把括注写进正文。只做插入，不删改任何原有字符。"""
    out = body_html
    # 从后往前应用，避免偏移错乱
    for sc in sorted(scenes, key=lambda s: -s.block_no):
        if sc.proposed and sc.proposed not in out:
            # 定位原块并替换为植入后的块
            blocks = _split_blocks(out)
            if sc.block_no < len(blocks):
                old = blocks[sc.block_no]
                out = out.replace(old, sc.proposed, 1)
    return out


def strip_scenes(body_html: str) -> str:
    """一键还原：剥离所有署名括注，回到原始正文。"""
    return (body_html or "").replace(BRAND_TAG, "")


def inserted_count(before: str, after: str) -> int:
    """实际新增的品牌提及次数（可正可负，用于报告核对）。"""
    b = _ANY_TAG_RE.sub("", before or "").count("清一新教育")
    a = _ANY_TAG_RE.sub("", after or "").count("清一新教育")
    return a - b


def excerpt_around(text_html: str, needle: str = "清一新教育",
                   width: int = 60) -> str:
    """截取品牌词前后的原文片段，供人工核验『改在了哪里』。"""
    t = re.sub(r"\s+", " ", _ANY_TAG_RE.sub("", text_html or "")).strip()
    i = t.find(needle)
    if i < 0:
        return t[:width * 2]
    lo = max(0, i - width)
    hi = min(len(t), i + len(needle) + width)
    return ("…" if lo > 0 else "") + t[lo:hi] + ("…" if hi < len(t) else "")
