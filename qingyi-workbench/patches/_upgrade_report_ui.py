# -*- coding: utf-8 -*-
"""验収報告 v12-UI：换掉整套样式 + 注入交互层（目录 / 折叠 / 灯箱 / 复制 / 进度 / 搜索）。"""
import io
import os
import sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "验收报告.html")
s = io.open(P, encoding="utf-8").read()
orig_len = len(s)

# ============================ 1. 标题 ============================
if s.count("可视化验收报告 (v10)") != 1:
    print("title 锚点异常:", s.count("可视化验收报告 (v10)"))
    sys.exit(1)
s = s.replace("可视化验收报告 (v10)", "可视化验收报告 (v12)", 1)

# ============================ 2. 换样式 ============================
i = s.find("<style>")
j = s.find("</style>")
if i < 0 or j < 0:
    print("找不到 style 块")
    sys.exit(1)

NEW_STYLE = r"""<style>
:root{
  --bg:#f4f6fb; --bg-soft:#eef2f9; --bg-soft2:#f8fafc;
  --panel:#ffffff;
  --line:#e7ebf3; --line-2:#d9e1ee;
  --text:#0b1220; --text-2:#4b5768; --text-3:#8b95a7;
  --brand:#2563eb; --brand-2:#1d4ed8; --brand-soft:#eef4ff;
  --cyan:#06b6d4;
  --ok:#059669; --ok-soft:#ecfdf5;
  --warn:#d97706; --warn-soft:#fffbeb;
  --err:#dc2626;
  --grad:linear-gradient(135deg,#2563eb 0%,#06b6d4 100%);
  --grad-soft:linear-gradient(135deg,#eff5ff 0%,#ecfeff 100%);
  --r-sm:10px; --r:14px; --r-lg:18px;
  --sh-1:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.05);
  --sh-2:0 2px 4px rgba(16,24,40,.04),0 10px 24px -8px rgba(16,24,40,.10);
  --sh-3:0 6px 12px rgba(16,24,40,.05),0 22px 48px -14px rgba(16,24,40,.18);
  --ease:cubic-bezier(.22,.61,.36,1);
  --top:56px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;color:var(--text);font-size:14px;line-height:1.72;
  font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
    "Hiragino Sans GB","Microsoft YaHei",sans-serif;
  background:
    radial-gradient(920px 500px at 10% -10%, rgba(37,99,235,.09), transparent 62%),
    radial-gradient(780px 440px at 94% 1%, rgba(6,182,212,.08), transparent 60%),
    var(--bg);
  background-attachment:fixed;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
}
.wrap{max-width:1060px;margin:0 auto;padding:calc(var(--top) + 40px) 22px 120px}

/* ---------- 顶栏 ---------- */
.qy-top{
  position:fixed;left:0;right:0;top:0;z-index:70;height:var(--top);
  display:flex;align-items:center;gap:12px;padding:0 18px;
  background:rgba(255,255,255,.76);
  -webkit-backdrop-filter:saturate(180%) blur(16px);
  backdrop-filter:saturate(180%) blur(16px);
  border-bottom:1px solid var(--line);
}
.qy-brand{display:flex;align-items:center;gap:9px;font-weight:750;font-size:13.5px;
  letter-spacing:-.2px;white-space:nowrap;color:var(--text)}
.qy-brand i{width:22px;height:22px;border-radius:7px;background:var(--grad);flex:none;
  box-shadow:0 5px 14px -4px rgba(37,99,235,.65)}
.qy-brand s{text-decoration:none;color:var(--text-3);font-weight:500;font-size:12.5px}
.qy-top .qy-sp{flex:1}
.qy-search{position:relative;display:flex;align-items:center}
.qy-search input{
  width:190px;height:32px;border-radius:9px;border:1px solid var(--line-2);
  background:#fff;padding:0 30px 0 30px;font-size:12.5px;color:var(--text);
  outline:none;transition:width .3s var(--ease),border-color .2s,box-shadow .2s;
  font-family:inherit;
}
.qy-search input:focus{width:250px;border-color:var(--brand);box-shadow:0 0 0 3px rgba(37,99,235,.13)}
.qy-search svg{position:absolute;left:9px;width:13px;height:13px;stroke:var(--text-3);
  fill:none;stroke-width:2;pointer-events:none}
.qy-search kbd{position:absolute;right:7px;font-size:10.5px;color:var(--text-3);
  border:1px solid var(--line-2);border-radius:4px;padding:0 4px;line-height:15px;background:#fff}
.qy-btn{
  display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 12px;
  border-radius:9px;border:1px solid var(--line-2);background:#fff;color:var(--text-2);
  font-size:12.5px;font-weight:600;cursor:pointer;white-space:nowrap;font-family:inherit;
  transition:background .18s,border-color .18s,color .18s,transform .12s var(--ease),box-shadow .18s;
}
.qy-btn:hover{background:var(--brand-soft);border-color:#c3d8ff;color:var(--brand-2)}
.qy-btn:active{transform:scale(.97)}
.qy-btn.pri{background:var(--grad);border-color:transparent;color:#fff;
  box-shadow:0 6px 16px -6px rgba(37,99,235,.7)}
.qy-btn.pri:hover{filter:brightness(1.07);color:#fff}
.qy-prog{position:absolute;left:0;right:0;bottom:-1px;height:2px}
.qy-prog i{display:block;height:100%;width:0;background:var(--grad);
  border-radius:0 2px 2px 0;transition:width .1s linear}

/* ---------- 左目录 ---------- */
.qy-toc{
  position:fixed;top:calc(var(--top) + 24px);width:188px;
  left:max(16px, calc(50vw - 530px - 206px));
  max-height:calc(100vh - var(--top) - 60px);overflow:auto;
  z-index:50;padding:2px 0 8px;display:none;
  scrollbar-width:thin;
}
.qy-toc::-webkit-scrollbar{width:5px}
.qy-toc::-webkit-scrollbar-thumb{background:#cdd6e6;border-radius:9px}
@media(min-width:1440px){.qy-toc{display:block}}
.qy-toc-t{font-size:10.5px;font-weight:750;letter-spacing:.09em;text-transform:uppercase;
  color:var(--text-3);padding:0 0 8px 12px}
.qy-toc a{
  position:relative;display:block;padding:6px 10px 6px 12px;border-radius:8px;
  color:var(--text-2);text-decoration:none;font-size:12.5px;line-height:1.45;
  transition:background .16s,color .16s;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;
}
.qy-toc a:hover{background:#fff;color:var(--text)}
.qy-toc a.on{background:#fff;color:var(--brand-2);font-weight:650;
  box-shadow:var(--sh-1)}
.qy-toc a.on::before{content:"";position:absolute;left:0;top:6px;bottom:6px;width:3px;
  border-radius:0 3px 3px 0;background:var(--grad)}
.qy-toc a .d{display:inline-block;width:5px;height:5px;border-radius:50%;
  background:#cbd5e1;margin-right:7px;vertical-align:middle;transition:background .2s,transform .2s}
.qy-toc a.on .d{background:var(--brand);transform:scale(1.35)}

/* ---------- Hero ---------- */
.qy-hero{
  position:relative;background:var(--panel);border:1px solid var(--line);
  border-radius:22px;padding:30px 30px 26px;margin-bottom:22px;
  box-shadow:var(--sh-3);overflow:hidden;
}
.qy-hero::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--grad)}
.qy-hero::after{content:"";position:absolute;right:-90px;top:-90px;width:280px;height:280px;
  border-radius:50%;background:var(--grad-soft);opacity:.85;pointer-events:none}
.qy-hero-tag{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:700;
  letter-spacing:.05em;color:var(--brand-2);background:var(--brand-soft);
  border:1px solid #d8e6ff;border-radius:999px;padding:3px 11px;margin-bottom:13px}
.qy-hero-tag::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--brand);
  box-shadow:0 0 0 3px rgba(37,99,235,.18)}
h1{position:relative;font-size:29px;line-height:1.22;margin:0 0 10px;
  letter-spacing:-.75px;font-weight:780}
.qy-hero-sub{position:relative;margin:0 0 20px;color:var(--text-2);font-size:13.5px;max-width:74ch}
.qy-hero-stats{position:relative;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:11px}
.stat{background:var(--bg-soft2);border:1px solid var(--line);border-radius:13px;
  padding:13px 15px;transition:transform .25s var(--ease),box-shadow .25s var(--ease),
  border-color .2s,background .2s}
.stat:hover{transform:translateY(-2px);box-shadow:var(--sh-2);background:#fff;border-color:var(--line-2)}
.stat .n{font-size:25px;font-weight:780;letter-spacing:-.9px;line-height:1.15;
  font-variant-numeric:tabular-nums}
.stat .l{font-size:12px;color:var(--text-2);margin-top:3px}
.stat.ok .n{color:var(--ok)}
.stat.brand .n{background:var(--grad);-webkit-background-clip:text;background-clip:text;
  color:transparent}
.stat.warn .n{color:var(--warn)}

/* 旧 .sub 兼容 */
.sub{color:var(--text-2);font-size:13px;margin-bottom:26px}

/* ---------- 卡片 ---------- */
.card{
  position:relative;background:var(--panel);border:1px solid var(--line);
  border-radius:var(--r-lg);padding:22px;margin-bottom:20px;box-shadow:var(--sh-2);
  transition:box-shadow .3s var(--ease),border-color .2s,transform .3s var(--ease);
  scroll-margin-top:calc(var(--top) + 18px);
}
.card:hover{box-shadow:var(--sh-3);border-color:var(--line-2)}
.card.qy-w{padding:0;overflow:hidden}
.card.qy-latest{border:none!important;background:
  linear-gradient(#fff,#fff) padding-box, var(--grad) border-box!important;
  border:2px solid transparent!important;box-shadow:0 1px 2px rgba(16,24,40,.05),
  0 16px 40px -16px rgba(37,99,235,.35)}
.card.qy-latest::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;
  background:var(--grad)}

h2{font-size:16.5px;margin:0 0 14px;display:flex;align-items:center;gap:10px;
  letter-spacing:-.25px;line-height:1.4}
h2 .n{
  display:inline-flex;align-items:center;justify-content:center;min-width:25px;height:25px;
  padding:0 6px;border-radius:8px;background:var(--grad);color:#fff;font-size:12px;
  font-weight:750;flex:none;box-shadow:0 4px 12px -5px rgba(37,99,235,.75)
}
.card-head{cursor:pointer;user-select:none;padding:18px 54px 18px 22px;margin:0;
  position:relative;transition:background .18s}
.card-head:hover{background:var(--bg-soft2)}
.card-head::after{
  content:"";position:absolute;right:24px;top:50%;width:7px;height:7px;margin-top:-5px;
  border-right:2px solid var(--text-3);border-bottom:2px solid var(--text-3);
  transform:rotate(45deg);transform-origin:60% 60%;
  transition:transform .32s var(--ease),border-color .2s;
}
.card-head:hover::after{border-color:var(--brand)}
.card.collapsed .card-head::after{transform:rotate(-45deg) translateY(-1px)}
.card.collapsed .card-head{border-bottom:1px solid transparent}
.qy-bwrap{display:grid;grid-template-rows:1fr;transition:grid-template-rows .38s var(--ease)}
.card.collapsed .qy-bwrap{grid-template-rows:0fr}
.card-body{overflow:hidden;min-height:0;padding:0 22px 22px}
.card-preview{display:none;padding:0 22px 18px;font-size:12.5px;color:var(--text-3);
  line-height:1.6}
.card.collapsed .card-preview{display:block}

h3{font-size:14px;margin:22px 0 10px;color:var(--text);letter-spacing:-.1px;
  display:flex;align-items:center;gap:8px}
h3::before{content:"";width:3px;height:13px;border-radius:2px;background:var(--grad);flex:none}
.card-body>:first-child{margin-top:0}
.card-body>h3:first-child{margin-top:2px}
.meta{font-size:12.5px;color:var(--text-2);margin-bottom:14px;padding:11px 14px;
  background:var(--bg-soft2);border-radius:11px;border:1px solid var(--line);
  border-left:3px solid #c7d7f7}
.meta b{color:var(--text)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}

/* ---------- 表格 ---------- */
.qy-tbl{border:1px solid var(--line);border-radius:13px;overflow:hidden;margin:12px 0;
  background:#fff}
.qy-tbl-scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px;margin:0}
th,td{padding:10px 13px;text-align:left;vertical-align:top;
  border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:none}
th{background:var(--bg-soft);font-weight:650;font-size:12.5px;color:var(--text-2);
  letter-spacing:.01em}
tbody tr{transition:background .16s}
table tr:hover td{background:var(--brand-soft)}
.card-body>:first-child.qy-tbl{margin-top:4px}

/* ---------- 行内元素 ---------- */
code{background:#eef2f8;padding:1.5px 6px;border-radius:6px;font-size:12.4px;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#1e293b;
  border:1px solid #e3e9f2}
a{color:var(--brand-2)}
.qy-prewrap{position:relative;margin:14px 0}
pre{background:#0b1220;color:#dbe4f3;padding:17px 18px;border-radius:13px;
  overflow:auto;font-size:12.3px;line-height:1.68;margin:0;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 14px 30px -16px rgba(11,18,32,.75)}
.qy-copy{
  position:absolute;top:9px;right:9px;height:26px;padding:0 9px;border-radius:7px;
  border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.1);
  color:#c7d5ec;font-size:11.5px;font-weight:650;cursor:pointer;font-family:inherit;
  opacity:0;transform:translateY(-3px);
  transition:opacity .2s var(--ease),transform .2s var(--ease),background .18s;
}
.qy-prewrap:hover .qy-copy{opacity:1;transform:none}
.qy-copy:hover{background:rgba(255,255,255,.2);color:#fff}
.qy-copy.done{background:rgba(16,185,129,.28);color:#a7f3d0;border-color:rgba(16,185,129,.45)}

.shot{
  border:1px solid var(--line);border-radius:14px;overflow:hidden;background:#fff;
  margin:16px 0 8px;box-shadow:var(--sh-2);transition:box-shadow .3s var(--ease),
  transform .3s var(--ease);cursor:zoom-in;position:relative;
}
.shot:hover{box-shadow:var(--sh-3);transform:translateY(-2px)}
.shot img{display:block;width:100%;height:auto;transition:transform .5s var(--ease)}
.shot:hover img{transform:scale(1.012)}
.shot::after{
  content:"点击放大";position:absolute;right:12px;top:12px;font-size:11px;font-weight:650;
  color:#fff;background:rgba(11,18,32,.62);padding:3px 9px;border-radius:999px;
  -webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);
  opacity:0;transform:translateY(-4px);transition:opacity .22s,transform .22s;pointer-events:none
}
.shot:hover::after{opacity:1;transform:none}
.cap{font-size:12.5px;color:var(--text-2);padding:11px 15px;background:var(--bg-soft2);
  border-top:1px solid var(--line);line-height:1.65}
.cap b{color:var(--text)}

.pill{
  display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:650;
  padding:2.5px 10px;border-radius:999px;background:var(--ok-soft);color:#047857;
  border:1px solid #bbf7d0;white-space:nowrap;line-height:1.5
}
.pill.fix{background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe}
.pill.warn{background:var(--warn-soft);color:#b45309;border-color:#fde68a}
.pill.pl{background:#f1f5f9;color:#475569;border-color:#e2e8f0}

.note{background:var(--brand-soft);border:1px solid #dbe7ff;border-left:3px solid var(--brand);
  border-radius:0 12px 12px 0;padding:13px 16px;font-size:13px;color:var(--text-2);margin:14px 0}
.note b{color:var(--text)}
.ok-t{color:var(--ok);font-weight:700}
.warn-t{color:var(--warn);font-weight:700}
ul{margin:8px 0;padding-left:22px}
li{margin:5px 0}
li::marker{color:var(--brand)}

footer{text-align:center;color:var(--text-3);font-size:12px;margin-top:40px;
  padding-top:20px;border-top:1px solid var(--line)}

/* ---------- 进场动画 ---------- */
.qy-rv{opacity:0;transform:translateY(18px)}
.qy-rv.in{opacity:1;transform:none;
  transition:opacity .55s var(--ease),transform .55s var(--ease)}

/* ---------- 回到顶部 ---------- */
.qy-top-btn{position:fixed;right:24px;bottom:26px;z-index:60;width:42px;height:42px;
  border-radius:13px;border:1px solid var(--line-2);background:rgba(255,255,255,.9);
  -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);
  color:var(--text-2);cursor:pointer;display:flex;align-items:center;justify-content:center;
  box-shadow:var(--sh-2);opacity:0;pointer-events:none;transform:translateY(10px);
  transition:opacity .25s var(--ease),transform .25s var(--ease),background .18s,color .18s}
.qy-top-btn.on{opacity:1;pointer-events:auto;transform:none}
.qy-top-btn:hover{background:var(--brand);color:#fff;border-color:transparent}
.qy-top-btn svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2.4;
  stroke-linecap:round;stroke-linejoin:round}

/* ---------- 灯箱 ---------- */
.qy-lb{position:fixed;inset:0;z-index:120;background:rgba(8,12,22,.84);
  -webkit-backdrop-filter:blur(9px);backdrop-filter:blur(9px);
  display:flex;align-items:center;justify-content:center;padding:44px;
  opacity:0;pointer-events:none;transition:opacity .26s var(--ease)}
.qy-lb.on{opacity:1;pointer-events:auto}
.qy-lb img{max-width:100%;max-height:100%;border-radius:14px;
  box-shadow:0 44px 90px -24px rgba(0,0,0,.8);transform:scale(.965);
  transition:transform .34s var(--ease)}
.qy-lb.on img{transform:scale(1)}
.qy-lb-hint{position:fixed;left:0;right:0;bottom:22px;text-align:center;color:#9fb0c9;
  font-size:12px;letter-spacing:.02em}

/* ---------- 搜索无结果 ---------- */
.qy-none{display:none;text-align:center;padding:56px 20px;color:var(--text-3);
  font-size:13.5px;background:#fff;border:1px dashed var(--line-2);border-radius:var(--r-lg)}
.qy-none.on{display:block}
mark{background:#fef08a;color:inherit;border-radius:3px;padding:0 2px}

@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  *{animation-duration:.001ms!important;transition-duration:.001ms!important}
  .qy-rv{opacity:1;transform:none}
}
@media print{
  .qy-top,.qy-toc,.qy-top-btn,.qy-lb,.qy-copy{display:none!important}
  body{background:#fff}
  .wrap{max-width:none;padding:0}
  .card{break-inside:avoid;box-shadow:none;border:1px solid #ddd}
  .card.collapsed .qy-bwrap{grid-template-rows:1fr}
  .card-preview{display:none}
  .qy-rv{opacity:1;transform:none}
}
</style>"""

s = s[:i] + NEW_STYLE + s[j + len("</style>"):]

# ============================ 3. 换 Hero ============================
old_hero = """<h1>清一新教育文章修改工作台 · 可视化验收报告</h1>
<div class="sub">
  生成时间：2026-09-20（v12 更新） · 验收对象：<code>https://zh.samuraiguan.cloud/api/qy/console</code> ·
  本报告用截图 + 文本快照两种方式交叉印证界面真实状态（截图存于 <code>qy_local/shots/</code>）
</div>"""
NEW_HERO = """<header class="qy-hero">
  <div class="qy-hero-tag">可视化验收报告 · 2026-09-20（v12）</div>
  <h1>清一新教育文章修改工作台</h1>
  <p class="qy-hero-sub">
    验收对象 <code>https://zh.samuraiguan.cloud/api/qy/console</code> ·
    用<b>页面截图</b> + <b>文本快照</b>两种方式交叉印证界面真实状态 ·
    截图存于 <code>qy_local/shots/</code>
  </p>
  <div class="qy-hero-stats">
    <div class="stat brand"><div class="n" data-count="11">11</div><div class="l">轮迭代全部落地（v2~v12）</div></div>
    <div class="stat ok"><div class="n" data-count="16">16</div><div class="l">张页面截图逐屏留证</div></div>
    <div class="stat"><div class="n" data-count="6">6</div><div class="l">道只读闸门 · 任意一道不过就停</div></div>
    <div class="stat warn"><div class="n" data-count="3">3</div><div class="l">条架构不变量 · 改代码前先看</div></div>
  </div>
</header>"""
if s.count(old_hero) != 1:
    print("hero 锚点异常:", s.count(old_hero))
    sys.exit(1)
s = s.replace(old_hero, NEW_HERO, 1)

# ============================ 4. 注入交互层 ============================
SCRIPT = r"""
<script>
/* ===== 清一新教育 · 验收报告 交互层 ===== */
(function () {
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- 1. 顶栏 ---------- */
  var top = document.createElement('div');
  top.className = 'qy-top';
  top.innerHTML =
    '<div class="qy-brand"><i></i>清一新教育<span style="font-weight:400;color:#8b95a7">·</span>' +
    '<s>验收报告</s></div>' +
    '<div class="qy-sp"></div>' +
    '<div class="qy-search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/>' +
    '<path d="M20 20l-3.2-3.2"/></svg>' +
    '<input id="qyQ" type="search" placeholder="搜这报告…" autocomplete="off">' +
    '<kbd>/</kbd></div>' +
    '<button class="qy-btn" id="qyFold">全部折叠</button>' +
    '<button class="qy-btn pri" id="qyMenu">目录</button>' +
    '<div class="qy-prog"><i id="qyBar"></i></div>';
  document.body.insertBefore(top, document.body.firstChild);

  var bar = top.querySelector('#qyBar');
  var menuBtn = top.querySelector('#qyMenu');

  /* ---------- 2. 表格包壳（圆角 + 横向滚动） ---------- */
  Array.prototype.forEach.call(document.querySelectorAll('.card table'), function (t) {
    var box = document.createElement('div');
    box.className = 'qy-tbl';
    var sc = document.createElement('div');
    sc.className = 'qy-tbl-scroll';
    t.parentNode.insertBefore(box, t);
    box.appendChild(sc);
    sc.appendChild(t);
  });

  /* ---------- 3. 代码块加复制按钮 ---------- */
  Array.prototype.forEach.call(document.querySelectorAll('pre'), function (p) {
    if (p.parentNode.classList.contains('qy-prewrap')) return;
    var w = document.createElement('div');
    w.className = 'qy-prewrap';
    p.parentNode.insertBefore(w, p);
    w.appendChild(p);
    var b = document.createElement('button');
    b.className = 'qy-copy';
    b.type = 'button';
    b.textContent = '复制';
    b.addEventListener('click', function (e) {
      e.stopPropagation();
      var txt = p.innerText;
      var done = function () {
        b.textContent = '已复制';
        b.classList.add('done');
        setTimeout(function () { b.textContent = '复制'; b.classList.remove('done'); }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(done, function () { fallback(txt, done); });
      } else { fallback(txt, done); }
    });
    w.appendChild(b);
  });
  function fallback(txt, cb) {
    var ta = document.createElement('textarea');
    ta.value = txt; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta); cb();
  }

  /* ---------- 4. 卡片：标题当把手 + 折叠 + 预览行 ---------- */
  var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
  cards.forEach(function (card, idx) {
    var h2 = card.querySelector(':scope > h2');
    if (!h2) return;

    /* 最新一轮的金边框换成渐变色环 */
    if ((card.getAttribute('style') || '').indexOf('#fcd34d') >= 0) {
      card.removeAttribute('style');
      card.classList.add('qy-latest');
    }
    card.classList.add('qy-w');
    h2.classList.add('card-head');

    var wrap = document.createElement('div');
    wrap.className = 'qy-bwrap';
    var body = document.createElement('div');
    body.className = 'card-body';
    var n = h2.nextSibling;
    while (n) { var nx = n.nextSibling; body.appendChild(n); n = nx; }
    wrap.appendChild(body);
    card.appendChild(wrap);

    var title = (h2.textContent || '').replace(/\s+/g, ' ').trim();
    card.dataset.qyTitle = title;
    card.dataset.qyText = (body.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();

    var pv = document.createElement('div');
    pv.className = 'card-preview';
    var raw = (body.textContent || '').replace(/\s+/g, ' ').trim();
    pv.textContent = raw.slice(0, 132) + (raw.length > 132 ? ' …' : '');
    card.appendChild(pv);

    card.dataset.qyRound = title.indexOf('轮') >= 0 ? '1' : '0';
    card.dataset.qyIdx = idx;

    h2.addEventListener('click', function () { card.classList.toggle('collapsed'); });
  });

  /* 默认：历史轮次折起来，最新一轮和常设章节展开 */
  var roundCards = cards.filter(function (c) { return c.dataset.qyRound === '1'; });
  roundCards.forEach(function (c, i) { if (i > 0) c.classList.add('collapsed'); });

  var foldBtn = top.querySelector('#qyFold');
  var allFolded = false;
  foldBtn.addEventListener('click', function () {
    allFolded = !allFolded;
    cards.forEach(function (c) { c.classList.toggle('collapsed', allFolded); });
    foldBtn.textContent = allFolded ? '全部展开' : '全部折叠';
  });

  /* ---------- 5. 目录 ---------- */
  var toc = document.createElement('nav');
  toc.className = 'qy-toc';
  toc.innerHTML = '<div class="qy-toc-t">目录</div>';
  cards.forEach(function (card, i) {
    if (!card.dataset.qyTitle) return;
    if (!card.id) card.id = 'qy-sec-' + i;
    var a = document.createElement('a');
    a.href = '#' + card.id;
    var t = card.dataset.qyTitle;
    a.innerHTML = '<span class="d"></span>' + t.replace(/^[◆★]\s*/, '');
    a.title = t;
    a.dataset.target = card.id;
    a.addEventListener('click', function () {
      card.classList.remove('collapsed');
      allFolded = false; foldBtn.textContent = '全部折叠';
    });
    toc.appendChild(a);
  });
  document.body.appendChild(toc);

  var links = Array.prototype.slice.call(toc.querySelectorAll('a'));
  function spy() {
    var y = window.scrollY + 130, best = null;
    cards.forEach(function (card, i) {
      if (card.offsetTop <= y) best = card;
    });
    links.forEach(function (a) {
      a.classList.toggle('on', !!best && a.dataset.target === best.id);
    });
  }

  /* ---------- 6. 小屏：目录抽屉 ---------- */
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
  });

  /* ---------- 7. 灯箱 ---------- */
  var lb = document.createElement('div');
  lb.className = 'qy-lb';
  lb.innerHTML = '<img alt=""><div class="qy-lb-hint">点击任意处 / 按 Esc 关闭 · ' +
    '图片为 1280px 宽真机截图</div>';
  document.body.appendChild(lb);
  var lbImg = lb.querySelector('img');

  Array.prototype.forEach.call(document.querySelectorAll('.shot'), function (sh) {
    var img = sh.querySelector('img');
    if (!img) return;
    sh.addEventListener('click', function () {
      lbImg.src = img.src;
      lb.classList.add('on');
    });
  });
  lb.addEventListener('click', function () { lb.classList.remove('on'); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') lb.classList.remove('on');
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
      e.preventDefault();
      document.getElementById('qyQ').focus();
    }
  });

  /* ---------- 8. 回到顶部 ---------- */
  var tb = document.createElement('button');
  tb.className = 'qy-top-btn';
  tb.title = '回到顶部';
  tb.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  tb.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
  });
  document.body.appendChild(tb);

  /* ---------- 9. 进场动画 + 数字滚动 ---------- */
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.classList.add('in');
      io.unobserve(e.target);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
  cards.forEach(function (c, i) {
    if (reduced || i < 2) { c.classList.add('in'); return; }
    c.classList.add('qy-rv');
    io.observe(c);
  });
  /* 安全网：无论观察器有没有触发（整页截图 / 极端长页），3 秒后一律显示 */
  setTimeout(function () { cards.forEach(function (c) { c.classList.add('in'); }); }, 2600);

  var cio = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return;
      var el = e.target, t = parseInt(el.dataset.count, 10) || 0, st = null;
      cio.unobserve(el);
      if (reduced) { el.textContent = t; return; }
      function step(ts) {
        if (!st) st = ts;
        var p = Math.min(1, (ts - st) / 900);
        el.textContent = Math.round(t * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }, { threshold: 0.5 });
  Array.prototype.forEach.call(document.querySelectorAll('[data-count]'), function (el) {
    cio.observe(el);
  });

  /* ---------- 10. 滚动进度 + 回顶按钮 + 目录高亮 ---------- */
  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = (h > 0 ? Math.min(100, (window.scrollY / h) * 100) : 0) + '%';
      tb.classList.toggle('on', window.scrollY > 520);
      spy();
      ticking = false;
    });
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  onScroll();

  /* ---------- 11. 搜索过滤 ---------- */
  var q = document.getElementById('qyQ');
  var none = document.createElement('div');
  none.className = 'qy-none';
  none.textContent = '没有匹配的章节 —— 换个词试试';
  var wrapEl = document.querySelector('.wrap');
  var ft = wrapEl.querySelector('footer');
  if (ft) wrapEl.insertBefore(none, ft); else wrapEl.appendChild(none);

  var t0 = null;
  q.addEventListener('input', function () {
    clearTimeout(t0);
    t0 = setTimeout(function () {
      var kw = q.value.trim().toLowerCase();
      if (!kw) {
        cards.forEach(function (c) { c.style.display = ''; });
        none.classList.remove('on');
        return;
      }
      var hit = 0;
      cards.forEach(function (c) {
        var ok = (c.dataset.qyText || '').indexOf(kw) >= 0 ||
                 (c.dataset.qyTitle || '').toLowerCase().indexOf(kw) >= 0;
        c.style.display = ok ? '' : 'none';
        if (ok) { hit++; c.classList.remove('collapsed'); }
      });
      none.classList.toggle('on', hit === 0);
    }, 110);
  });
})();
</script>
"""

if s.count("</body>") != 1:
    print("</body> 异常:", s.count("</body>"))
    sys.exit(1)
s = s.replace("</body>", SCRIPT + "\n</body>", 1)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("OK  %d -> %d 字符（+%d）" % (orig_len, len(s), len(s) - orig_len))
