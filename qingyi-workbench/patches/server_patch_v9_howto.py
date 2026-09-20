# -*- coding: utf-8 -*-
"""v9：补上「怎么把改动推到自己的知乎」这一步的指引。

用户原话：「云端弄好之后我要怎么更新到自己的知乎，我没看到任何指引」

查证后发现两个真 bug：
  1. 第 3 步整张卡（#taskCard）默认 `class="card hide"`，要等任务创建后才显示 ——
     没建任务的人在整个页面上看不到任何"怎么执行"的说明。
  2. 卡里的 `#execGuide`（含「下载 Windows 一键程序」按钮）初始也是 `hide`，
     而 JS 里只有 `guide.classList.add("hide")`，**从来没有移除过 hide** ——
     那块 markup 是死的，永远不可能显示。

修法：新增一张**常驻**的「第 3 步 · 把改动推到你的知乎」卡，
把 Windows 一键程序作为主路径写清楚；后面两张卡顺序编号。
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


# ---------- 1. 顶部流程图注释 ----------
sub(
    "  第 3 步  在你自己电脑上执行（进度实时回传）",
    "  第 3 步  把改动推到你的知乎（双击一键程序）→ 进度实时回传",
    "顶部注释",
)

# ---------- 2. 插入常驻的「怎么做」卡 ----------
sub(
    '<div class="card hide" id="taskCard">\n'
    '  <h2><span class="step">3</span> 在你自己电脑上执行</h2>',
    '''<!-- ============ 第 3 步：怎么做（常驻显示，不随任务隐藏） ============ -->
<div class="card" id="howtoCard">
  <h2><span class="step">3</span> 把改动推到你的知乎 —— 你要做的就这三下</h2>
  <div class="hint">
    云端只负责把每篇文章的<strong>最终标题和正文算好</strong>；
    <strong>真正的写入发生在你自己的电脑上</strong> ——
    用你的网络身份提交，而不是从我们的服务器去改你的号。所以最后需要你亲手启动一次。
  </div>

  <ol class="mini">
    <li>
      <div class="ttl">① 回到上面第 2 步，勾好文章 → 点「创建修改任务」</div>
      <div class="tiptext">
        这一步只是让云端把每篇的最终稿算好并缓存起来，<b>还没有动你的知乎</b>。
      </div>
    </li>
    <li>
      <div class="ttl">② 双击 <code>清一新教育一键修改.exe</code></div>
      <div class="tiptext">
        会弹出一个黑窗口，它自动完成：取云端凭证 → 领任务 →
        逐篇把改好的稿子提交到你的知乎 → 跑完自动停。
        <b>跑完之前别关那个窗口</b>；到每日上限会自己停下，剩下的第二天接着跑。
        窗口里会一行行打印进度，不用按任何键。
      </div>
      <div class="act" style="margin-top:8px">
        <button class="btn-primary" id="btnExe3" onclick="dlExe('btnExe3')">⬇️ 下载 Windows 一键程序</button>
        <span class="tiptext">就一个文件，双击即用；不用解压、不用装任何东西</span>
      </div>
    </li>
    <li>
      <div class="ttl">③ 回到这里看进度，跑完点「🔍 让云端复核一下」</div>
      <div class="tiptext">
        进度和日志实时显示在下面那张卡里。复核会<b>重新回读你线上的文章逐篇比对</b>，
        告诉你哪几篇没按要求完成 —— 它不采信「本地说做完了」。
      </div>
    </li>
  </ol>

  <div class="hint" id="howtoState" style="margin-top:12px;font-weight:600"></div>

  <details class="adv">
    <summary>没有 Windows？或者想让我（AI 助手）来代跑？</summary>
    <div class="body">
      <div class="tiptext">
        Mac 没有预编译程序（PyInstaller 无法在 Windows 上交叉编译 mac 版）。两种办法：<br>
        ① <b>交给 AI 助手</b>：点下面「📋 复制给 AI 助手的话」，
           粘贴给它（Antigravity / Claude / Cursor 都行），它会在你电脑上把执行器跑起来；<br>
        ② <b>下载部署包</b>：解压后双击里面的脚本（本机需要 Python 3.9+）。
      </div>
      <div class="act" style="margin-top:10px">
        <button class="btn-ghost btn-sm" onclick="copyInstr()">📋 复制给 AI 助手的话</button>
        <button class="btn-ghost btn-sm" id="btnBundle3" onclick="dlBundle('btnBundle3')">⬇️ 部署包（zip）</button>
      </div>
      <div class="tiptext" style="margin-top:8px">
        还不想动？<b>什么都不做也不会出事</b> —— 云端只是把稿子算好放着，不会自己发布。
      </div>
    </div>
  </details>
</div>

<div class="card hide" id="taskCard">
  <h2><span class="step">4</span> 执行进度与云端复核</h2>''',
    "插入常驻第 3 步卡 + 原卡改编号 4",
)

# ---------- 3. 概览卡改编号 5 ----------
sub(
    '<div class="card hide" id="ovCard">\n'
    '  <h2><span class="step">4</span> 修改概览</h2>',
    '<div class="card hide" id="ovCard">\n'
    '  <h2><span class="step">5</span> 修改概览</h2>',
    "概览卡改编号 5",
)

# ---------- 4. 修掉 #execGuide 永远隐藏的 bug ----------
sub(
    '  <div id="execGuide" class="hide">',
    '  <div id="execGuide">',
    "修 execGuide 永久隐藏",
)

# ---------- 5. 常驻状态提示（自包含，不碰原有逻辑） ----------
sub(
    "/* ---------- 常见问题 ---------- */",
    '''/* ---------- 第 3 步「你要做什么」的实时状态条 ----------
   自包含：只读全局 JOB，不修改任何原有状态，也就不可能弄坏别的东西。 */
function renderHowto(){
  try{
    const el = document.getElementById("howtoState");
    if(!el) return;
    const j = (typeof JOB === "undefined") ? null : JOB;
    let t;
    if(!j){
      t = "① 还没创建任务 —— 先完成上面第 2 步（勾文章 → 点「创建修改任务」）。";
    }else{
      const st   = j.status || "";
      const who  = (j.worker && j.worker.id) ? j.worker.id : "";
      const jid  = j.job_id || "";
      if(!who){
        t = "② 任务已就绪（" + jid + "）—— 现在双击你电脑上的「清一新教育一键修改.exe」。"
          + "还没下载就点上面的按钮。";
      }else if(st === "running"){
        t = "② 执行器已接入（" + who + "），正在逐篇提交 —— 你什么都不用做，关掉网页也不影响。";
      }else if(st === "done"){
        t = "③ 跑完了 —— 点下面那张卡里的「🔍 让云端复核一下」，云端会回读线上文章逐篇核对。";
      }else if(st === "paused"){
        t = "② 到每日上限了，已自动暂停 —— 明天再双击一次程序即可接着跑。";
      }else if(st === "cancelled"){
        t = "任务已取消。想重来的话，回到第 2 步重新创建即可。";
      }else{
        t = "任务状态：" + st + "。";
      }
    }
    el.textContent = t;
  }catch(e){ /* 任何异常都不影响页面其他功能 */ }
}
setInterval(renderHowto, 4000);
renderHowto();

/* ---------- 常见问题 ---------- */''',
    "新增 renderHowto 状态条",
)

# ---------- 6. 引导加一步 ----------
sub(
    '''  {sel:"#agentBox", t:"第 3 步：把这段话发给你的 AI 助手",''',
    '''  {sel:"#btnExe3", t:"第 3 步：双击一键程序，改动才真正生效",
   d:"前面都只是『准备好』。真正把改好的稿子提交到你知乎的，是这一步：下载这个 exe 并双击它。它会自己取凭证、领任务、逐篇提交；跑完之前别关那个黑窗口。Mac 或想让我代跑，展开它下面的『没有 Windows？』。"},
  {sel:"#agentBox", t:"第 4 步：把这段话发给你的 AI 助手",''',
    "引导补第 3 步",
)

if src != orig:
    bak = P.with_suffix(".py.bak-v9")
    if not bak.exists():
        bak.write_text(orig, encoding="utf-8")
    P.write_text(src, encoding="utf-8")

print("\n".join(rep))
print("\n编译校验:", end=" ")
py_compile.compile(str(P), doraise=True)
print("通过")
