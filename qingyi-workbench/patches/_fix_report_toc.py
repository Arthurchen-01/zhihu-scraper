# -*- coding: utf-8 -*-
"""目录改成「宽屏侧栏 + 任意宽度抽屉」，并柔化 Hero 的装饰圆。"""
import io
import os
import sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "验收报告.html")
s = io.open(P, encoding="utf-8").read()
before = len(s)

# ---------- 1) 抽屉样式 ----------
old = "@media(min-width:1440px){.qy-toc{display:block}}"
new = """@media(min-width:1440px){.qy-toc{display:block}}
.qy-toc.open{
  display:block;background:#fff;border:1px solid var(--line);border-radius:16px;
  padding:12px 10px;box-shadow:0 30px 72px -22px rgba(16,24,40,.4);
  left:16px;top:calc(var(--top) + 12px);width:236px;
  max-height:calc(100vh - var(--top) - 36px);
  animation:qyTocIn .26s var(--ease);
}
@keyframes qyTocIn{from{opacity:0;transform:translateY(-9px) scale(.98)}to{opacity:1;transform:none}}
.qy-toc-bd{position:fixed;inset:0;z-index:45;background:rgba(15,23,42,.16);
  -webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px);
  opacity:0;pointer-events:none;transition:opacity .24s var(--ease)}
.qy-toc-bd.on{opacity:1;pointer-events:auto}
@media(min-width:1440px){.qy-toc-bd{display:none}}"""
if s.count(old) != 1:
    print("toc 断点锚点异常:", s.count(old)); sys.exit(1)
s = s.replace(old, new, 1)

# ---------- 2) Hero 装饰圆柔化 ----------
old2 = """.qy-hero::after{content:"";position:absolute;right:-90px;top:-90px;width:280px;height:280px;
  border-radius:50%;background:var(--grad-soft);opacity:.85;pointer-events:none}"""
new2 = """.qy-hero::after{content:"";position:absolute;right:-70px;top:-110px;width:320px;height:320px;
  border-radius:50%;pointer-events:none;
  background:radial-gradient(circle at 34% 34%,
    rgba(37,99,235,.16), rgba(6,182,212,.10) 46%, rgba(6,182,212,0) 72%);
  filter:blur(6px)}"""
if s.count(old2) != 1:
    print("hero 装饰锚点异常:", s.count(old2)); sys.exit(1)
s = s.replace(old2, new2, 1)

# ---------- 3) 目录按钮 → 抽屉 ----------
old3 = """  /* ---------- 6. 小屏：目录抽屉 ---------- */
  menuBtn.addEventListener('click', function () {
    var on = toc.style.display === 'block';
    if (on) { toc.style.display = ''; menuBtn.classList.remove('pri'); return; }
    toc.style.display = 'block';
    toc.style.left = '16px';
    toc.style.background = '#fff';
    toc.style.borderRadius = '14px';
    toc.style.padding = '12px';
    toc.style.boxShadow = '0 24px 60px -18px rgba(16,24,40,.3)';
    menuBtn.classList.add('pri');
  });"""
new3 = """  /* ---------- 6. 目录抽屉（任意宽度都能拉出来） ---------- */
  var bd = document.createElement('div');
  bd.className = 'qy-toc-bd';
  document.body.appendChild(bd);

  function closeToc() {
    toc.classList.remove('open');
    bd.classList.remove('on');
    menuBtn.classList.remove('pri');
    menuBtn.textContent = '目录';
  }
  menuBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    if (toc.classList.contains('open')) { closeToc(); return; }
    toc.classList.add('open');
    bd.classList.add('on');
    menuBtn.classList.add('pri');
    menuBtn.textContent = '收起目录';
  });
  bd.addEventListener('click', closeToc);
  toc.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a');
    if (a && window.innerWidth < 1440) setTimeout(closeToc, 120);
  });"""
if s.count(old3) != 1:
    print("菜单锚点异常:", s.count(old3)); sys.exit(1)
s = s.replace(old3, new3, 1)

# ---------- 4) Esc 一并关抽屉 ----------
old4 = "    if (e.key === 'Escape') lb.classList.remove('on');"
new4 = ("    if (e.key === 'Escape') { lb.classList.remove('on'); closeToc(); }")
if s.count(old4) != 1:
    print("esc 锚点异常:", s.count(old4)); sys.exit(1)
s = s.replace(old4, new4, 1)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("OK  %d -> %d" % (before, len(s)))
