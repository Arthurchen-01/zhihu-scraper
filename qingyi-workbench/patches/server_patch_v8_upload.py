# -*- coding: utf-8 -*-
"""v8：给「高级：手动填写凭证」补上真正的「上传到云端」按钮。

背景：用户说「我现在知道怎么弄到 cookie 了，但是没理解怎么上传」。
查页面发现那一区只有 textarea + 「重新检索」，**没有任何上传入口** ——
手里有 cookie 也送不到云端。这里把它补上。
"""
from pathlib import Path
import py_compile

P = Path("/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py")
src = P.read_text(encoding="utf-8")
orig = src
rep = []


def sub(old, new, tag):
    global src
    if old not in src:
        rep.append("SKIP  %s" % tag)
        return
    n = src.count(old)
    if n != 1:
        rep.append("FAIL  %s（出现 %d 次）" % (tag, n))
        return
    src = src.replace(old, new, 1)
    rep.append("OK    %s" % tag)


# ---------- 1. 补齐 markup：加「上传」那一行 ----------
sub(
    '''      <label class="f" for="ck">知乎登录凭证（仅当自动读取失败时才需要，格式含 z_c0=）</label>
      <textarea id="ck" placeholder="通常留空 —— 点上面的「📥 载入凭证」会自动填好"></textarea>
      <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <button class="btn-primary" id="btnInspect" onclick="doInspect()">🔍 重新检索我的内容</button>
        <span class="tiptext">检索是只读的，不会写入任何内容</span>
      </div>''',
    '''      <label class="f" for="ck">知乎登录凭证（含 <code>z_c0=</code>；手动粘贴或自动载入都行）</label>
      <textarea id="ck" placeholder="可以是：①点上面「📥 载入凭证」自动填好；②自己从浏览器复制后粘进来"></textarea>

      <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <button class="btn-primary" id="btnUploadCred" onclick="doUploadCred()">☁️ 上传这份凭证到云端</button>
        <button class="btn-ghost btn-sm" id="btnPasteCred" onclick="doPasteCred()">📋 从剪贴板粘贴</button>
        <button class="btn-ghost btn-sm" id="btnInspect" onclick="doInspect()">🔍 重新检索我的内容</button>
      </div>
      <div class="hint" id="uploadState" style="margin-top:8px">
        把凭证放进上面的框 → 点「☁️ 上传到云端」。上传之后，双击一键程序就不用再关浏览器了。
        <br>（上传的是知乎发给你这台电脑的登录凭据，云端只保留 6 小时、到点自动丢弃。）
      </div>
      <div class="hint" style="margin-top:4px">检索是只读的，不会写入任何内容。</div>''',
    "高级区加「上传到云端」",
)

# ---------- 2. 补 JS ----------
sub(
    "/* ---------- 常见问题 ---------- */",
    '''/* ---------- 手动把凭证上传到云端凭证柜 ---------- */
function doPasteCred(){
  const ta = document.getElementById("ck");
  if(!navigator.clipboard || !navigator.clipboard.readText){
    msg("uploadState", "这个浏览器不允许网页读剪贴板，请自己在框里按 Ctrl+V 粘贴。");
    if(ta) ta.focus();
    return;
  }
  navigator.clipboard.readText().then(
    (t)=>{
      const v = (t || "").trim();
      ta.value = v;
      if(!v){ msg("uploadState", "剪贴板是空的 —— 先把知乎 Cookie 复制一下再点我。"); return; }
      msg("uploadState", v.indexOf("z_c0=") >= 0
        ? "已从剪贴板粘进来了，确认没问题就点「☁️ 上传这份凭证到云端」。"
        : "粘进来了，但里面没有 z_c0= —— 多半复制得不全，请重新复制。");
    },
    ()=>{ msg("uploadState", "读剪贴板被浏览器拒绝了，请自己在框里按 Ctrl+V 粘贴。");
          if(ta) ta.focus(); }
  );
}

async function doUploadCred(){
  const b  = document.getElementById("btnUploadCred");
  const ta = document.getElementById("ck");
  const ck = (ta && ta.value ? ta.value : "").trim();
  if(!ck){
    msg("uploadState", "先把凭证放进上面的框里（可以用「📋 从剪贴板粘贴」）。");
    if(ta) ta.focus();
    return;
  }
  if(ck.indexOf("z_c0=") < 0){
    msg("uploadState", "这段里没有 z_c0= —— 它不像是知乎的登录凭证，请重新复制一次。", "err");
    return;
  }
  const t = b ? b.innerHTML : "";
  if(b){ b.disabled = true; b.innerHTML = '<span class="spin"></span> 上传中…'; }
  try{
    const r = await fetch(API+"/api/qy/credential-deposit", {
      method: "POST",
      headers: JH(),
      body: JSON.stringify({
        key: SITE_KEY, cookie: ck, note: "网页手动上传", per_day: currentCap()
      })
    });
    const j = await r.json().catch(()=>({}));
    if(!r.ok || !j.ok) throw new Error(j.detail || j.note || ("HTTP " + r.status));
    msg("uploadState",
        "✅ 已上传到云端凭证柜（编号 " + j.token + "，保留 6 小时）。"
      + "现在可以双击一键程序了 —— 浏览器可以一直开着，不用关。", "ok");
    msg("credState", "✅ 凭证已上传云端（编号 " + j.token + "）", "ok");
    toast("凭证已上传到云端");
  }catch(e){
    msg("uploadState", "上传失败：" + ((e && e.message) ? e.message : "未知错误"), "err");
  }finally{
    if(b){ b.disabled = false; b.innerHTML = t; }
  }
}

/* ---------- 常见问题 ---------- */''',
    "新增 doPasteCred/doUploadCred",
)

if src != orig:
    bak = P.with_suffix(".py.bak-v8")
    if not bak.exists():
        bak.write_text(orig, encoding="utf-8")
    P.write_text(src, encoding="utf-8")

print("\n".join(rep))
print("\n编译校验:", end=" ")
py_compile.compile(str(P), doraise=True)
print("通过")
