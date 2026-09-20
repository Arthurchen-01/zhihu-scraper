# -*- coding: utf-8 -*-
"""v13.2 · 引导与提示（toast / tour）界面升级
本地把远端页面做 4 处变换，产出 _patched_qingyi_page.py，并 py_compile 校验。
只改视觉与交互，不动任何业务逻辑。
"""
import re, sys, py_compile, os
sys.stdout.reconfigure(encoding='utf-8')

HERE = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35"
SRC = os.path.join(HERE, "_remote_qingyi_page.py")
DST = os.path.join(HERE, "_patched_qingyi_page.py")
MARK = "v13.2 · 引导与提示"

src = open(SRC, "r", encoding="utf-8", newline="").read()
if MARK in src:
    print("ALREADY_APPLIED"); sys.exit(0)

# ---------------------------------------------------------------- CSS 层
CSS = r"""
/* ============ v13.2 · 引导与提示（toast / tour）============
   上一版 v13 把 .toast 改成浅色玻璃，v13.1 又按回深色 —— 两层打架；
   引导气泡只吃到圆角阴影，内部字排（序号圈 / 按钮 / 跳过）仍是老样子。
   这一层做两件事：
   1) toast 统一成浅色玻璃卡：语义色左条 + 驻留进度条 + 点击关闭 + 自动归色；
   2) 引导气泡按设计系统重排：渐变序号 / 步骤点 / 键位提示 / 窄屏钳位。 */

/* ---------- Toast ---------- */
#toastBox{gap:10px;bottom:30px;z-index:10002}
.toast{
  position:relative;overflow:hidden;
  padding:12px 18px 13px 19px;border-radius:var(--r-sm);
  background:rgba(255,255,255,.93);color:var(--text);
  border:1px solid var(--line-2);
  -webkit-backdrop-filter:saturate(180%) blur(16px);
  backdrop-filter:saturate(180%) blur(16px);
  box-shadow:var(--sh-3);
  font-size:13.5px;line-height:1.55;font-weight:500;letter-spacing:.01em;
  pointer-events:auto;cursor:pointer;
  max-width:min(560px,calc(100vw - 40px));
  transform:translateY(12px) scale(.97);opacity:0;
  transition:opacity .26s var(--ease),transform .26s var(--ease);
  --qy-accent:var(--brand);
}
.toast.on{transform:none;opacity:1}
.toast.ok{--qy-accent:var(--ok)}
.toast.warn{--qy-accent:var(--warn)}
.toast.err{--qy-accent:var(--err)}
.toast:hover{box-shadow:0 8px 18px rgba(16,24,40,.07),0 30px 60px -16px rgba(16,24,40,.34)}
.toast::before{
  content:"";position:absolute;left:0;top:0;bottom:0;width:3px;
  background:var(--qy-accent);
}
.toast::after{
  content:"";position:absolute;left:0;right:0;bottom:0;height:2px;
  background:var(--qy-accent);opacity:.5;transform-origin:left center;
  animation:qyToastDrain var(--qy-toast-dur,2600ms) linear forwards;
}
@keyframes qyToastDrain{from{transform:scaleX(1)}to{transform:scaleX(0)}}

/* ---------- 新手引导 ---------- */
.tour-hl{
  border-radius:var(--r);pointer-events:none;
  box-shadow:0 0 0 3px rgba(37,99,235,.95),0 0 0 9px rgba(37,99,235,.16),
             0 0 0 9999px rgba(8,12,22,.58);
  transition:left .3s var(--ease),top .3s var(--ease),
             width .3s var(--ease),height .3s var(--ease),box-shadow .3s var(--ease);
  animation:qyHlIn .28s var(--ease);
}
@keyframes qyHlIn{from{opacity:0}to{opacity:1}}

.tour-tip{
  box-sizing:border-box;
  width:340px;max-width:340px;
  padding:16px 18px 14px;border-radius:var(--r-lg);
  background:rgba(255,255,255,.97);color:var(--text);
  border:1px solid var(--line-2);
  -webkit-backdrop-filter:saturate(180%) blur(18px);
  backdrop-filter:saturate(180%) blur(18px);
  box-shadow:var(--sh-3),0 40px 90px -30px rgba(2,6,23,.55);
  font-size:13px;line-height:1.72;overflow:hidden;
  animation:qyTipIn .3s var(--ease);
}
.tour-tip::before{
  content:"";position:absolute;left:0;right:0;top:0;height:3px;
  background:var(--grad);
}
@keyframes qyTipIn{from{opacity:0;transform:translateY(10px) scale(.975)}
                   to{opacity:1;transform:none}}

.tour-hd{display:flex;align-items:center;gap:9px;margin:0 0 7px}
.tour-hd b{display:block;margin:0;font-size:14.5px;font-weight:700;
  line-height:1.35;letter-spacing:-.005em;color:var(--text)}
.tour-tip .t-n{
  flex:none;min-width:22px;height:22px;border-radius:50%;
  background:var(--grad);color:#fff;
  font-size:11.5px;font-weight:750;font-variant-numeric:tabular-nums;
  box-shadow:0 6px 16px -7px rgba(37,99,235,.9);
}
.tour-tip .t-d{margin:0;color:var(--text-2);font-size:12.8px;line-height:1.75}

.tour-dots{display:flex;align-items:center;gap:5px;margin:12px 0 0}
.tour-dots i{
  width:6px;height:6px;border-radius:999px;background:var(--line-2);
  cursor:pointer;transition:width .22s var(--ease),background .22s var(--ease);
}
.tour-dots i:hover{background:var(--brand-2)}
.tour-dots i.on{width:18px;background:var(--brand)}
.tour-dots .hint{
  margin-left:auto;font-size:10.5px;color:var(--text-3);
  letter-spacing:.04em;font-family:ui-monospace,SFMono-Regular,monospace
}

.tour-btns{display:flex;gap:8px;margin-top:12px;align-items:center}
.tour-btns .btn-sm{padding:6px 13px;font-size:12.5px;border-radius:9px}
.tour-skip{
  margin-left:auto;padding:4px 2px;border:none;background:none;
  font-size:11.5px;color:var(--text-3);cursor:pointer;border-radius:6px;
  transition:color .18s var(--ease)
}
.tour-skip:hover{color:var(--err)}

@media (prefers-reduced-motion: reduce){
  .toast,.tour-tip,.tour-hl{animation:none;transition:none}
  .toast::after{animation:none;opacity:0}
}
@media print{
  #toastBox,.tour-hl,.tour-tip{display:none !important}
}
"""
STYLE_BLOCK = "\n<style>\n" + CSS.strip() + "\n</style>\n"

# ---------------------------------------------------------------- JS 层
JS = r"""
/* ===== v13.2 · 引导与提示增强 ===== */
(function(){
  /* 引导：键盘导航（← → 切换，Esc 跳过） */
  document.addEventListener('keydown', function(e){
    if(typeof TOUR_I === 'undefined' || TOUR_I < 0) return;
    var k = e.key;
    if(k === 'ArrowRight' || k === 'Enter'){ e.preventDefault(); tourNext(); }
    else if(k === 'ArrowLeft'){ e.preventDefault(); tourPrev(); }
    else if(k === 'Escape'){ e.preventDefault(); tourEnd(true); }
  }, true);

  /* 引导：窄屏时把气泡钳回视口内（老定位算法按 340px 宽写死） */
  function clampTip(){
    var tip = document.getElementById('tourTip');
    if(!tip) return;
    var w = tip.offsetWidth || 340, vw = window.innerWidth;
    var l = parseFloat(tip.style.left || '0');
    if(l < 12) l = 12;
    if(l + w > vw - 12) l = Math.max(12, vw - w - 12);
    tip.style.left = l + 'px';
    var t = parseFloat(tip.style.top || '0');
    var h = tip.offsetHeight || 0;
    if(t + h > window.innerHeight - 12) t = Math.max(12, window.innerHeight - h - 12);
    tip.style.top = t + 'px';
  }
  window.addEventListener('resize', clampTip);
  var mo = new MutationObserver(function(){ clampTip(); });
  mo.observe(document.body, {childList:true, subtree:false});

  /* Toast：Esc 一键清干净 */
  document.addEventListener('keydown', function(e){
    if(e.key !== 'Escape') return;
    var box = document.getElementById('toastBox');
    if(!box || !box.children.length) return;
    [].slice.call(box.children).forEach(function(el){
      el.classList.remove('on');
      setTimeout(function(){ el.remove(); }, 280);
    });
  });
})();
"""
SCRIPT_BLOCK = "\n<script>\n" + JS.strip() + "\n</script>\n"

# ---------------------------------------------------------------- toast() 升级
OLD_TOAST = '''function toast(text){
  const box = document.getElementById("toastBox");
  if(!box) return;
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = text;
  box.appendChild(el);
  requestAnimationFrame(()=>el.classList.add("on"));
  setTimeout(()=>{ el.classList.remove("on");
                   setTimeout(()=>el.remove(), 260); }, 2600);
}'''

NEW_TOAST = '''function toast(text, kind){
  /* v13.2：语义自动归色 + 驻留进度条 + 点击关闭 + 叠层上限。
     旧调用（单参数）全部兼容 —— 不改任何一个调用点。 */
  const box = document.getElementById("toastBox");
  if(!box) return;
  const t = text == null ? "" : String(text);
  if(!kind){
    if(/失败|错误|不能|无法|请先|还没有|未通过|不通过|没能|没法|还没/.test(t)) kind = "err";
    else if(/完成|通过|成功|已上传|已重置|已下载|已取消|已复制|已生成/.test(t)) kind = "ok";
    else kind = "info";
  }
  const DUR = 2600;
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = t;
  el.title = "点击关闭";
  let done = false, kill = null;
  function dismiss(){
    if(done) return; done = true;
    clearTimeout(kill);
    el.classList.remove("on");
    setTimeout(function(){ el.remove(); }, 280);
  }
  el.addEventListener("click", dismiss);
  el.style.setProperty("--qy-toast-dur", DUR + "ms");
  box.appendChild(el);
  while(box.children.length > 4){ box.removeChild(box.firstChild); }
  requestAnimationFrame(function(){ el.classList.add("on"); });
  kill = setTimeout(dismiss, DUR);
}'''

# ---------------------------------------------------------------- 引导气泡重排
OLD_TIP = '''    tip.innerHTML = '<b><span class="t-n">'+(TOUR_I+1)+'</span>'+st.t+'</b>'+st.d
      + '<div class="tour-btns">'
      + '<button class="btn-ghost btn-sm" onclick="tourPrev()"'+(first?' disabled style="opacity:.4"':'')+'>上一步</button>'
      + '<button class="btn-primary btn-sm" onclick="tourNext()">'+(last?"完成":"下一步 →")+'</button>'
      + '<button class="tour-skip" onclick="tourEnd(true)">跳过，不再显示</button></div>';'''

NEW_TIP = '''    let dots = "";
    for(let k=0;k<TOUR_STEPS.length;k++){
      dots += '<i class="'+(k===TOUR_I?'on':'')+'" onclick="tourShow('+k+')" title="第 '+(k+1)+' 步"></i>';
    }
    tip.innerHTML = '<div class="tour-hd"><span class="t-n">'+(TOUR_I+1)+'</span><b>'+st.t+'</b></div>'
      + '<p class="t-d">'+st.d+'</p>'
      + '<div class="tour-dots">'+dots+'<span class="hint">← → 切换</span></div>'
      + '<div class="tour-btns">'
      + '<button class="btn-ghost btn-sm" onclick="tourPrev()"'+(first?' disabled style="opacity:.4"':'')+'>上一步</button>'
      + '<button class="btn-primary btn-sm" onclick="tourNext()">'+(last?"完成":"下一步 →")+'</button>'
      + '<button class="tour-skip" onclick="tourEnd(true)">跳过，不再显示</button></div>';'''

out = src
steps = []

def sub_one(name, old, new):
    """精确替换且必须命中恰好一次"""
    global out
    n = out.count(old)
    if n != 1:
        print("MATCH_FAIL %s: count=%d" % (name, n)); sys.exit(2)
    out = out.replace(old, new, 1)
    steps.append((name, len(old), len(new)))

sub_one("toast()", OLD_TOAST, NEW_TOAST)
sub_one("tour-tip", OLD_TIP, NEW_TIP)

# CSS：插在最后一个 </style> 之后（即 v13.1 层之后）
i = out.rfind("</style>")
if i < 0: print("NO_STYLE"); sys.exit(3)
out = out[:i+8] + STYLE_BLOCK + out[i+8:]
steps.append(("css", 0, len(STYLE_BLOCK)))

# JS：插在最后一个 </body> 之前
j = out.rfind("</body>")
if j < 0: print("NO_BODY"); sys.exit(4)
out = out[:j] + SCRIPT_BLOCK + out[j:]
steps.append(("js", 0, len(SCRIPT_BLOCK)))

open(DST, "w", encoding="utf-8", newline="").write(out)

# 双保险：换行/引号没被动过
assert out.count("<style>") == 4, out.count("<style>")
assert out.count("</style>") == 4
assert out.count("<script>") == 3, out.count("<script>")
assert out.count("</script>") == 3
assert out.count("__QY_SITE_KEY__") == 2, out.count("__QY_SITE_KEY__")
assert out.count("guanjun2026") == 1

try:
    py_compile.compile(DST, doraise=True, cfile=DST + ".pyc")
except py_compile.PyCompileError as e:
    print("PY_COMPILE_FAIL", e); sys.exit(5)

for s in steps:
    print("OK  %-10s %6d -> %6d" % s)
print("bytes %d -> %d" % (len(src.encode('utf-8')), len(out.encode('utf-8'))))
print("PY_COMPILE_OK")
