# -*- coding: utf-8 -*-
"""修补两点：① 旧卡片的杂色 inline 边框全部清掉，只给最新一轮渐变环；
② 折叠时把 body 的 padding 一并收掉，消除 22px 漏边。"""
import io
import os
import sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "验收报告.html")
s = io.open(P, encoding="utf-8").read()
before = len(s)

# ---------- 1) 折叠漏边 ----------
old = ".card-body{overflow:hidden;min-height:0;padding:0 22px 22px}"
new = (".card-body{overflow:hidden;min-height:0;padding:0 22px 22px;"
       "transition:padding .38s var(--ease)}\n"
       ".card.collapsed .card-body{padding-top:0;padding-bottom:0}")
if s.count(old) != 1:
    print("padding 锚点异常:", s.count(old)); sys.exit(1)
s = s.replace(old, new, 1)

# ---------- 2) 折叠时预览行不要贴着底 ----------
old2 = ".card-preview{display:none;padding:0 22px 18px;font-size:12.5px;color:var(--text-3);\n  line-height:1.6}"
new2 = (".card-preview{display:none;padding:0 54px 18px 22px;font-size:12.5px;\n"
        "  color:var(--text-3);line-height:1.62;\n"
        "  -webkit-mask-image:linear-gradient(90deg,#000 78%,transparent);\n"
        "  mask-image:linear-gradient(90deg,#000 78%,transparent)}")
if s.count(old2) != 1:
    print("preview 锚点异常:", s.count(old2)); sys.exit(1)
s = s.replace(old2, new2, 1)

# ---------- 3) 清掉所有卡片的 inline 杂色边框 ----------
old3 = """    /* 最新一轮的金边框换成渐变色环 */
    if ((card.getAttribute('style') || '').indexOf('#fcd34d') >= 0) {
      card.removeAttribute('style');
      card.classList.add('qy-latest');
    }
    card.classList.add('qy-w');"""
new3 = """    /* 旧卡片身上那 9 套杂色 inline 边框（红/紫/绿/天蓝…）全部清掉，
       只给「排第一的最新一轮」加渐变色环，其余走统一样式 */
    card.removeAttribute('style');
    card.classList.add('qy-w');"""
if s.count(old3) != 1:
    print("inline 锚点异常:", s.count(old3)); sys.exit(1)
s = s.replace(old3, new3, 1)

old4 = """  var roundCards = cards.filter(function (c) { return c.dataset.qyRound === '1'; });"""
new4 = """  if (cards.length) cards[0].classList.add('qy-latest');
  var roundCards = cards.filter(function (c) { return c.dataset.qyRound === '1'; });"""
if s.count(old4) != 1:
    print("latest 锚点异常:", s.count(old4)); sys.exit(1)
s = s.replace(old4, new4, 1)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("OK  %d -> %d" % (before, len(s)))
