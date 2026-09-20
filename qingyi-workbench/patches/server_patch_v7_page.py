# -*- coding: utf-8 -*-
"""控制台页面补丁 v7：把「浏览器扩展」作为可选加速项加进第 1 步。"""
from pathlib import Path

P = Path("/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py")
src = P.read_text(encoding="utf-8")
orig = src
rep = []


def sub(old, new, tag):
    global src
    if old not in src:
        rep.append("SKIP  %s" % tag)
        return
    if src.count(old) != 1:
        rep.append("FAIL  %s（出现 %d 次）" % (tag, src.count(old)))
        return
    src = src.replace(old, new, 1)
    rep.append("OK    %s" % tag)


# ---------- 1. 顶部流程图注释 ----------
sub(
    "第 1 步  下载部署包 → 双击 → 回来点「载入凭证」→ 自动检索（零粘贴、零 F12）",
    "第 1 步  下载一键程序 → 双击 → 回来点「载入凭证」→ 自动检索（零粘贴、零 F12）\n"
    "         （可选加速：装浏览器扩展，之后连「关浏览器」都不需要）",
    "顶部注释",
)

# ---------- 2. 第 1 步：加「下载扩展」按钮 ----------
sub(
    '''        <button class="btn-primary" id="btnExe" onclick="dlExe('btnExe')">⬇️ 下载 Windows 一键程序</button>
        <span class="tiptext" id="hint1">下好直接双击就能跑（首次运行若被 Windows 拦一下，点「更多信息」→「仍要运行」）</span>
      </div>''',
    '''        <button class="btn-primary" id="btnExe" onclick="dlExe('btnExe')">⬇️ 下载 Windows 一键程序</button>
        <span class="tiptext" id="hint1">下好直接双击就能跑（首次运行若被 Windows 拦一下，点「更多信息」→「仍要运行」）</span>
      </div>
      <div class="act" style="margin-top:8px">
        <button class="btn-ghost" id="btnExt" onclick="dlExt('btnExt')">🧩 浏览器扩展：装一次，以后连浏览器都不用关</button>
      </div>
      <div class="tiptext" style="margin-top:6px">
        不装也能用，只是每次运行前要手动关一下浏览器（那个锁绕不过去）；
        装上它，一键程序改成从云端取登录，<b>浏览器可以一直开着</b>。
      </div>
      <details class="adv" style="margin-top:8px">
        <summary>扩展怎么装？我们已写好，你的 AI 助手照做即可</summary>
        <div class="body">
          <div class="tiptext">
            扩展是<b>我们写好的成品</b>，助手不需要写任何代码，只要「加载已解压的扩展程序」。
            压缩包里带一份 <b>AGENTS.md</b>（专门写给 AI 助手看的部署说明）。
          </div>
          <div class="act" style="margin-top:10px">
            <button class="btn-ghost btn-sm" onclick="copyAgentExt()">📋 复制给 AI 助手的话</button>
            <span class="tiptext">连下载地址和步骤一起复制走。</span>
          </div>
          <div class="tiptext" id="extHint" style="margin-top:8px">
            自己装也行，就 3 下：解压 → 打开 <b>edge://extensions</b>（Chrome 用 <b>chrome://extensions</b>）
            → 打开「开发者模式」→ 点「加载已解压的扩展程序」→ 选解压出来的文件夹。
          </div>
        </div>
      </details>''',
    "第 1 步加扩展按钮",
)

# ---------- 3. 新增 dlExt / copyAgentExt ----------
sub(
    "/* ---------- 常见问题 ---------- */",
    '''async function dlExt(btnId){
  const b = document.getElementById(btnId || "btnExt");
  const t = b ? b.innerHTML : "";
  if(b){ b.disabled = true; b.innerHTML = '<span class="spin"></span> 正在准备…'; }
  try{
    const r = await fetch(API+"/api/qy/download/extension", {headers:H()});
    if(!r.ok){ const j = await r.json().catch(()=>({})); throw new Error(j.detail||"下载失败"); }
    const bl = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(bl);
    a.download = "清一新教育-修改助手-扩展.zip";
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href), 8000);
    const eh = document.getElementById("extHint");
    if(eh) eh.innerHTML = "✅ 已下载。解压后打开 <b>edge://extensions</b> 或 <b>chrome://extensions</b>，" +
      "打开右上角「开发者模式」→ 点「加载已解压的扩展程序」→ 选解压出来的文件夹。" +
      "装好后点一下扩展图标 →「立即同步到云端」。";
    toast("扩展已下载：解压后按提示点 3 下装上即可");
  }catch(e){
    toast("下载失败：" + e.message);
  }finally{
    if(b){ b.disabled = false; b.innerHTML = t; }
  }
}

/* 把「怎么装扩展」整段话复制走，直接粘给 AI 助手 */
function copyAgentExt(){
  const txt =
    "请帮我在浏览器里安装一个已经写好的扩展，你不需要写任何代码。\\n" +
    "\\n" +
    "1) 下载这个地址（带请求头 X-API-Key: " + SITE_KEY + "）：\\n" +
    "   " + API + "/api/qy/download/extension\\n" +
    "2) 解压到固定位置：%LOCALAPPDATA%\\\\QingyiEdu\\\\extension\\n" +
    "3) 打开 edge://extensions（Chrome 用 chrome://extensions）→ 打开右上角「开发者模式」\\n" +
    "   → 点「加载已解压的扩展程序」→ 选中上面那个文件夹。\\n" +
    "   （注意：浏览器禁止任何脚本注入 chrome:// 页面，所以最后这几下必须人点，不要试图自动化。）\\n" +
    "4) 点工具栏上的扩展图标 →「立即同步到云端」，确认显示「本浏览器知乎登录：已登录」。\\n" +
    "5) 完成后告诉我一声。以后我双击一键程序，就不需要再关浏览器了。\\n" +
    "\\n" +
    "压缩包里有 AGENTS.md，是专门写给你的详细说明，可以先读它。";
  navigator.clipboard.writeText(txt).then(
    ()=>toast("已复制 —— 直接粘贴给你的 AI 助手即可"),
    ()=>toast("复制失败，请手动选中文字复制"));
}

/* ---------- 常见问题 ---------- */''',
    "新增 dlExt/copyAgentExt",
)

# ---------- 4. FAQ ----------
sub(
    '''    "2) 部署窗口提示读取失败？\\n" +
    "   浏览器开着会锁住凭证文件。把 Edge / Chrome 所有窗口全部关掉\\n" +
    "   （不是最小化），回到那个窗口按回车重试。\\n\\n" +''',
    '''    "2) 窗口一直停在「正在等您关掉浏览器」？\\n" +
    "   浏览器会独占锁住它的登录数据，这是 Windows 层面的锁，绕不过去。\\n" +
    "   把 Edge / Chrome 的【所有窗口】全部关掉（不是最小化），程序会自己继续，\\n" +
    "   不需要按任何键。\\n\\n" +
    "2.5) 装浏览器扩展有什么用？\\n" +
    "   装上之后就不需要关浏览器了：扩展会把登录同步到云端，\\n" +
    "   一键程序改成从云端取用。扩展在第 1 步可以下载，交给你的 AI 助手装即可。\\n\\n" +''',
    "FAQ 第 2 条",
)

# ---------- 5. 引导文案 ----------
sub(
    '就下载这一个文件，下好双击它就行 —— 不用解压、不用开终端、不用装任何东西。它会自动读到你浏览器里的知乎登录，不用粘贴、不用按 F12。',
    '就下载这一个文件，下好双击它就行 —— 不用解压、不用开终端、不用装任何东西。'
    '它会自动读到你浏览器里的知乎登录，不用粘贴、不用按 F12。'
    '嫌每次都要关浏览器麻烦？把下面那个浏览器扩展装上（我们写好的，让你的 AI 助手装），就不用关了。',
    "引导第 1 步文案",
)

if src != orig:
    bak = P.with_suffix(".py.bak-v7")
    if not bak.exists():
        bak.write_text(orig, encoding="utf-8")
    P.write_text(src, encoding="utf-8")

print("\n".join(rep))
print("\n编译校验:", end=" ")
import py_compile
try:
    py_compile.compile(str(P), doraise=True)
    print("通过")
except py_compile.PyCompileError as e:
    print("失败\n", e)
    raise
