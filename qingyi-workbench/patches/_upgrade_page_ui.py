# -*- coding: utf-8 -*-
"""给工作台页面（qingyi_page.py）套设计系统覆盖层 + 交互增强。
只追加，不改原有规则和任何 id / onclick；原有 <style> 全部保留做兜底。"""
import io
import os
import subprocess
import sys

ROOT = "/opt/zhihu-scraper"
PY = ROOT + "/zhihu_scraper/app/qingyi_page.py"
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qy_page_uikit.py")


def sh(cmd, timeout=180):
    r = subprocess.run(["ssh", "server3", cmd], capture_output=True,
                       timeout=timeout, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or ""), (r.stderr or "")


OVERRIDE = r"""<style>
/* ============ v13 · 设计系统覆盖层（只覆盖视觉，不动结构与逻辑） ============ */
:root{
  --bg:#f4f6fb;--bg-soft:#eef2f9;--bg-soft2:#f8fafc;--panel:#fff;
  --line:#e7ebf3;--line-2:#d9e1ee;
  --text:#0b1220;--text-2:#4b5768;--text-3:#8b95a7;
  --brand:#2563eb;--brand-2:#1d4ed8;--brand-soft:#eef4ff;--cyan:#06b6d4;
  --ok:#059669;--warn:#d97706;--err:#dc2626;
  --grad:linear-gradient(135deg,#2563eb 0%,#06b6d4 100%);
  --r-sm:10px;--r:14px;--r-lg:18px;
  --sh-1:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.05);
  --sh-2:0 2px 4px rgba(16,24,40,.04),0 10px 24px -8px rgba(16,24,40,.10);
  --sh-3:0 6px 12px rgba(16,24,40,.05),0 22px 48px -14px rgba(16,24,40,.18);
  --ease:cubic-bezier(.22,.61,.36,1);
}
html{scroll-behavior:smooth}
body{
  background:
    radial-gradient(920px 500px at 10% -10%, rgba(37,99,235,.08), transparent 62%),
    radial-gradient(780px 440px at 94% 1%, rgba(6,182,212,.07), transparent 60%),
    var(--bg) !important;
  background-attachment:fixed;
  color:var(--text);
  font-family:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
    "Hiragino Sans GB","Microsoft YaHei",sans-serif !important;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
}
body::before{
  content:"";position:fixed;left:0;right:0;top:0;height:2px;z-index:9999;
  background:var(--grad);transform:scaleX(var(--qy-p,0));transform-origin:0 50%;
  transition:transform .1s linear;pointer-events:none;
}
.wrap{max-width:1020px;padding:34px 20px 90px}

/* ---------- 卡片 ---------- */
.card{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--r-lg);
  box-shadow:var(--sh-2);transition:box-shadow .3s var(--ease),border-color .2s,
    transform .3s var(--ease);
}
.card:hover{box-shadow:var(--sh-3);border-color:var(--line-2)}
.card.dim{opacity:.5;filter:saturate(.6)}
.card h2{letter-spacing:-.25px;line-height:1.4}

/* ---------- 步骤块 ---------- */
.step{
  border-radius:var(--r);border:1px solid var(--line);background:var(--bg-soft2);
  transition:box-shadow .28s var(--ease),border-color .2s,background .2s,
    transform .28s var(--ease);
}
.step:hover{border-color:var(--line-2);box-shadow:var(--sh-1);background:#fff}
.hint{color:var(--text-2)}

/* ---------- 徽标 ---------- */
.badge{
  background:var(--grad);color:#fff;border-radius:999px;font-weight:700;
  box-shadow:0 5px 14px -6px rgba(37,99,235,.8);letter-spacing:.01em;
}

/* ---------- 按钮 ---------- */
.btn-primary{
  background:var(--grad);border:none;color:#fff;border-radius:11px;font-weight:650;
  letter-spacing:.01em;box-shadow:0 8px 20px -8px rgba(37,99,235,.85);
  transition:filter .18s,transform .12s var(--ease),box-shadow .2s var(--ease);
}
.btn-primary:hover:not(:disabled){filter:brightness(1.07);transform:translateY(-1px);
  box-shadow:0 12px 26px -9px rgba(37,99,235,.9)}
.btn-primary:active:not(:disabled){transform:translateY(0) scale(.985)}
.btn-ghost{
  background:#fff;border:1px solid var(--line-2);color:var(--text-2);border-radius:11px;
  font-weight:600;transition:background .18s,border-color .18s,color .18s,
    transform .12s var(--ease);
}
.btn-ghost:hover:not(:disabled){background:var(--brand-soft);border-color:#c3d8ff;
  color:var(--brand-2)}
.btn-ghost:active:not(:disabled){transform:scale(.985)}
.btn-ok{background:linear-gradient(135deg,#059669,#10b981);border:none;color:#fff;
  border-radius:11px;font-weight:650;box-shadow:0 8px 20px -9px rgba(5,150,105,.85);
  transition:filter .18s,transform .12s var(--ease)}
.btn-ok:hover:not(:disabled){filter:brightness(1.06);transform:translateY(-1px)}
.btn-danger{background:#fff;border:1px solid #fecaca;color:#b91c1c;border-radius:11px;
  font-weight:600;transition:background .18s,border-color .18s,transform .12s var(--ease)}
.btn-danger:hover:not(:disabled){background:#fef2f2;border-color:#fca5a5}
.btn-green{background:linear-gradient(135deg,#059669,#10b981);border:none;color:#fff;
  border-radius:11px;font-weight:650;transition:filter .18s,transform .12s var(--ease)}
.btn-green:hover:not(:disabled){filter:brightness(1.06);transform:translateY(-1px)}
.btn-green:active:not(:disabled){transform:scale(.985)}
.btn-sm{border-radius:9px}
.btn-xl{border-radius:13px;font-weight:700;letter-spacing:.01em}
button,.btn-primary,.btn-ghost,.btn-ok,.btn-danger,.btn-green{position:relative}
button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,
textarea:focus-visible,[tabindex]:focus-visible{
  outline:none !important;box-shadow:0 0 0 3px rgba(37,99,235,.28) !important;
}
input,select,textarea{
  font-family:inherit;color:var(--text);
  border-radius:10px;border:1px solid var(--line-2);background:#fff;
  transition:border-color .18s,box-shadow .18s;
}
input:focus,select:focus,textarea:focus{
  border-color:var(--brand);box-shadow:0 0 0 3px rgba(37,99,235,.13);
}

/* ---------- 提示块 ---------- */
.notice{
  border-radius:var(--r);border:1px solid #dbe7ff;background:var(--brand-soft);
  border-left:3px solid var(--brand);
}
.notice strong{color:var(--brand-2)}

/* ---------- 数字卡 ---------- */
.stats .stat,.stat{
  background:var(--bg-soft2);border:1px solid var(--line);border-radius:13px;
  transition:transform .25s var(--ease),box-shadow .25s var(--ease),
    border-color .2s,background .2s;
}
.stats .stat:hover,.stat:hover{transform:translateY(-2px);box-shadow:var(--sh-2);
  background:#fff;border-color:var(--line-2)}
.stat .n{letter-spacing:-.9px;font-variant-numeric:tabular-nums;font-weight:780}
.stat .l{color:var(--text-2)}
.stat.ok .n{color:var(--ok)}
.stat.err .n{color:var(--err)}

/* ---------- 状态胶囊 ---------- */
.chip{
  border-radius:999px;font-weight:650;letter-spacing:.01em;
  display:inline-flex;align-items:center;gap:5px;
  transition:background .2s,color .2s;
}
.chip.ok{background:#ecfdf5;color:#047857;border:1px solid #bbf7d0}
.chip.warn{background:#fffbeb;color:#b45309;border:1px solid #fde68a}
.chip.err{background:#fef2f2;color:#b91c1c;border:1px solid #fecaca}
.chip.run{background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe}
.chip.mute{background:#f1f5f9;color:#64748b;border:1px solid #e2e8f0}
.chip.done{background:#ecfdf5;color:#047857;border:1px solid #bbf7d0}
.chip.run::before,.chip.done::before{
  content:"";width:6px;height:6px;border-radius:50%;background:currentColor;flex:none;
}
.chip.run::before{animation:qyPulse 1.5s ease-in-out infinite}
@keyframes qyPulse{0%,100%{opacity:.35;transform:scale(.8)}50%{opacity:1;transform:scale(1.25)}}

/* ---------- 进度条 ---------- */
.pbar{background:#eef2f8;border-radius:999px;overflow:hidden;height:9px;
  box-shadow:inset 0 1px 2px rgba(16,24,40,.06)}
.pbar>i{background:var(--grad);border-radius:999px;position:relative;overflow:hidden;
  transition:width .5s var(--ease)}
.pbar>i::after{
  content:"";position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.55),transparent);
  animation:qyShimmer 1.6s linear infinite;
}
@keyframes qyShimmer{from{transform:translateX(-100%)}to{transform:translateX(100%)}}

/* ---------- 标签页 ---------- */
.tabs{background:var(--bg-soft);border:1px solid var(--line);border-radius:12px;padding:3px}
.tab{border-radius:9px;font-weight:600;color:var(--text-2);
  transition:background .2s var(--ease),color .2s,box-shadow .2s}
.tab:hover{color:var(--text)}
.tab.on{background:#fff;color:var(--brand-2);box-shadow:var(--sh-1)}

/* ---------- 扫描预览 ---------- */
.scanbox{border:1px solid var(--line);border-radius:var(--r);background:#fff;
  box-shadow:var(--sh-1);overflow:hidden}
.scanhd{background:var(--bg-soft2);border-bottom:1px solid var(--line);font-weight:650}
.scanrow{border-bottom:1px solid var(--line);transition:background .16s}
.scanrow:hover{background:var(--brand-soft)}
.scanrow:last-child{border-bottom:none}
.scand{border-radius:999px;background:#ecfdf5;color:#047857;border:1px solid #bbf7d0;
  font-weight:650}
.dot{border-radius:50%;background:#cbd5e1}
.dot.ok{background:var(--ok);box-shadow:0 0 0 3px rgba(5,150,105,.18)}

/* ---------- 日志 / 对照 ---------- */
.logs{border-radius:var(--r);border:1px solid var(--line);background:#fff;overflow:hidden}
.logs div{border-bottom:1px solid var(--line);transition:background .16s}
.logs div:hover{background:var(--bg-soft2)}
.logs div:last-child{border-bottom:none}
.logs .t{color:var(--text-3);font-variant-numeric:tabular-nums}
.diff{border-radius:var(--r);border:1px solid var(--line);overflow:hidden;background:#fff}
.diff .del{background:#fef2f2;color:#b91c1c;border-left:3px solid #fca5a5}
.diff .add{background:#ecfdf5;color:#047857;border-left:3px solid #6ee7b7}
.excerpt{background:var(--bg-soft2);border:1px solid var(--line);border-radius:var(--r-sm);
  color:var(--text-2)}
.zero{border-radius:var(--r);border:1px dashed var(--line-2);background:var(--bg-soft2)}
.zero.warn{border-color:#fde68a;background:#fffbeb;color:#92400e}
.empty{color:var(--text-3)}
.detail{color:var(--text-2)}

/* ---------- 功能选择 ---------- */
.feat{border-radius:var(--r);border:1px solid var(--line);background:#fff}
.fopt{transition:background .18s}
.fopt:hover{background:var(--bg-soft2)}
.fopt em{color:var(--text-3)}
.agentbox{border:1px solid var(--line);border-radius:var(--r);background:var(--bg-soft2)}
.agenthd{font-weight:700}
.agenthd strong{color:var(--brand-2)}
.vrow{border-bottom:1px solid var(--line);transition:background .16s}
.vrow:hover{background:var(--bg-soft2)}
.vrow .vt{color:var(--text-2)}
.jsbox{background:#0b1220;color:#dbe4f3;border-radius:var(--r);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 14px 30px -16px rgba(11,18,32,.75)}
.toolbar{gap:8px}
.caprow{background:var(--bg-soft2);border:1px solid var(--line);border-radius:var(--r)}
.caprow .meter{color:var(--text-2)}
.bigbar{border-radius:var(--r);border:1px solid var(--line);background:#fff;
  box-shadow:var(--sh-1)}
.bigbar .selnum b{color:var(--brand-2)}
.revtag{border-radius:999px;font-weight:650}
.revtag.ok{background:#ecfdf5;color:#047857;border:1px solid #bbf7d0}
.revtag.fall{background:#fffbeb;color:#b45309;border:1px solid #fde68a}
.oktext{color:var(--ok);font-weight:650}
.errtext{color:var(--err);font-weight:650}
.tiptext{color:var(--text-2)}

/* ---------- 赞助条 ---------- */
.sponsor{
  border-radius:var(--r);border:1px solid #fde68a;
  background:linear-gradient(135deg,#fffdf5 0%,#fff 60%,#fff7ed 100%);
  box-shadow:var(--sh-1);
}
.sponsor b{color:#92400e}
.sponsor .ph{color:#b45309;font-weight:650}
.sponsor .tip{color:var(--text-3)}

/* ---------- Toast ---------- */
#toastBox{z-index:9000}
.toast{
  border-radius:13px;border:1px solid var(--line);
  background:rgba(255,255,255,.94);
  -webkit-backdrop-filter:saturate(180%) blur(14px);
  backdrop-filter:saturate(180%) blur(14px);
  box-shadow:0 24px 56px -18px rgba(16,24,40,.35);
  transform:translateY(10px) scale(.98);opacity:0;
  transition:opacity .26s var(--ease),transform .26s var(--ease);
}
.toast.on{transform:none;opacity:1}

/* ---------- 新手引导 ---------- */
.tour-tip{border-radius:var(--r);box-shadow:0 30px 70px -20px rgba(16,24,40,.45);
  border:1px solid var(--line)}
.tour-hl{border-radius:var(--r);box-shadow:0 0 0 3px var(--brand),0 0 0 9999px rgba(8,12,22,.55)}

/* ---------- 折叠块 ---------- */
details{transition:opacity .2s}
details summary{cursor:pointer;transition:color .18s}
details summary:hover{color:var(--brand-2)}
details > summary{list-style:none}
details > summary::-webkit-details-marker{display:none}
details > summary::after{
  content:"";display:inline-block;width:6px;height:6px;margin-left:8px;
  border-right:1.8px solid currentColor;border-bottom:1.8px solid currentColor;
  transform:rotate(45deg) translateY(-1px);transform-origin:60% 60%;
  transition:transform .3s var(--ease);vertical-align:middle;opacity:.65;
}
details[open] > summary::after{transform:rotate(-45deg) translateY(1px)}
details > *:not(summary){animation:qyUnfold .32s var(--ease)}
@keyframes qyUnfold{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}

/* ---------- 滚动条 ---------- */
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#cfd8e8;border-radius:9px;border:2px solid transparent;
  background-clip:content-box}
::-webkit-scrollbar-thumb:hover{background:#b6c2d8;background-clip:content-box}

@media (prefers-reduced-motion:reduce){
  *{animation-duration:.001ms !important;transition-duration:.001ms !important}
}
</style>"""

ENHANCE = r"""<script>
/* ===== v13 交互增强：滚动进度 / 步骤高亮 / 平滑滚动 ===== */
(function(){
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var root = document.documentElement, ticking = false;

  function onScroll(){
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function(){
      var h = root.scrollHeight - window.innerHeight;
      root.style.setProperty('--qy-p', h > 0 ? Math.min(1, window.scrollY / h) : 0);
      ticking = false;
    });
  }
  window.addEventListener('scroll', onScroll, {passive:true});
  window.addEventListener('resize', onScroll);
  onScroll();

  if (reduced) return;

  /* 卡片进场：轻量上浮，不抢戏。跳过 .dim / .hide —— 它们的透明度有语义 */
  var cards = [].slice.call(document.querySelectorAll('.card')).filter(function(c){
    return !c.classList.contains('dim') && !c.classList.contains('hide');
  });
  cards.forEach(function(c,i){
    if (i > 14) return;
    c.style.opacity = '0';
    c.style.transform = 'translateY(14px)';
    c.style.transition = 'opacity .5s cubic-bezier(.22,.61,.36,1),'
      + 'transform .5s cubic-bezier(.22,.61,.36,1),box-shadow .3s';
  });
  var io = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if (!e.isIntersecting) return;
      var c = e.target;
      c.style.opacity = '1';
      c.style.transform = 'none';
      io.unobserve(c);
    });
  }, {rootMargin:'0px 0px -6% 0px', threshold:0.04});
  cards.forEach(function(c,i){ if (i > 14) return; io.observe(c); });
  /* 安全网：2.5 秒后一律显示，避免长页/整页截图时留白 */
  setTimeout(function(){
    cards.forEach(function(c){ c.style.opacity='1'; c.style.transform='none'; });
  }, 2500);

  /* 锚点平滑滚动（顶栏不遮挡） */
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var t = document.querySelector(a.getAttribute('href'));
    if (!t) return;
    e.preventDefault();
    window.scrollTo({top: t.getBoundingClientRect().top + window.scrollY - 18,
      behavior:'smooth'});
  });
})();
</script>
"""


def main():
    # 1) 上传两个片段到 /tmp（纯 ASCII 路径，避免中文穿 ssh 的编码问题）
    for name, body in (("/tmp/qy_ui_override.html", OVERRIDE),
                       ("/tmp/qy_ui_enhance.html", ENHANCE)):
        r = subprocess.run(["ssh", "server3", "cat > " + name],
                           input=body.encode("utf-8"), capture_output=True, timeout=120)
        print("上传", name, "rc =", r.returncode)

    # 2) 服务端打补丁
    patch = r'''
import io, sys, os
PY = "/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py"
s = io.open(PY, encoding="utf-8").read()
n0 = len(s)
ov = io.open("/tmp/qy_ui_override.html", encoding="utf-8").read()
en = io.open("/tmp/qy_ui_enhance.html", encoding="utf-8").read()

MARK_CSS = "v13 · 设计系统覆盖层"
MARK_JS  = "v13 交互增强"
if MARK_CSS in s:
    print("已经打过补丁，跳过")
    sys.exit(0)

if s.count("</style>") != 1:
    print("ERROR: </style> 次数 =", s.count("</style>")); sys.exit(1)
if s.count("</body>") != 1:
    print("ERROR: </body> 次数 =", s.count("</body>")); sys.exit(1)
if '"""' in ov or '"""' in en:
    print("ERROR: 片段含三引号，会破坏 PAGE 原始字符串"); sys.exit(1)

s = s.replace("</style>", "</style>\n" + ov, 1)
s = s.replace("</body>", en + "\n</body>", 1)

tmps = PY + ".tmp"
io.open(tmps, "w", encoding="utf-8", newline="\n").write(s)
os.replace(tmps, PY)
print("OK %d -> %d 字符 (+%d)" % (n0, len(s), len(s) - n0))
'''
    r = subprocess.run(["ssh", "server3", "python3 -"], input=patch,
                       capture_output=True, timeout=180, encoding="utf-8",
                       errors="replace")
    print(r.stdout)
    if r.returncode != 0:
        print("patch ERR:", r.stderr[-600:])
        return 1

    # 3) 语法检查 + 重启
    rc, out, err = sh("cd %s && python3 -m py_compile zhihu_scraper/app/qingyi_page.py "
                      "&& echo COMPILE_OK && systemctl restart zhihu-scraper "
                      "&& sleep 3 && systemctl is-active zhihu-scraper" % ROOT)
    print("编译/重启 rc =", rc)
    print(out)
    if err.strip():
        print("ERR:", err.strip()[-400:])

    # 4) 回读验证
    rc, out, err = sh("curl -s -o /dev/null -w 'console=%{http_code} size=%{size_download}\\n' "
                      "http://127.0.0.1:8775/api/qy/console")
    print(out.strip())
    rc, out, err = sh("cd %s && grep -c 'v13 · 设计系统覆盖层' zhihu_scraper/app/qingyi_page.py; "
                      "grep -c 'v13 交互增强' zhihu_scraper/app/qingyi_page.py; "
                      "grep -c 'btnCreate\\|doCreate\\|doInspect\\|fBodyHits' "
                      "zhihu_scraper/app/qingyi_page.py" % ROOT)
    print("关键符号计数:", out.replace("\n", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
