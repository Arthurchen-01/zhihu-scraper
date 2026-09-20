"""清一新教育 · 文章修改工作台 前端页面（v5）。

交互设计（每一步只做一件事）：
  第 1 步  下载部署包 → 双击 → 回来点「载入凭证」→ 自动检索（零粘贴、零 F12）
  第 2 步  打钩挑文章 → 点一个大按钮
  第 3 步  在你自己电脑上执行（进度实时回传）
  第 4 步  逐篇对照 + 正文零改动证据

v5 相对 v4 的改动：
  * 所有请求统一带上站点密钥 → 直接打开/收藏本页也能用（不再 401 天书）
  * 「每日上限」真正下发到执行器（随包 perday.txt），并显示执行器实际生效值
  * 「今日已写入」改为读取服务端真实计数（原来是永不更新的假数字）
  * 修 savePerDay 调用未定义 toast 的 ReferenceError
  * 修检索完成后按钮文案被改写、下载包没有任何反馈
  * 部署指引与手动下载从页面主体收进「高级」，消除重复与自相矛盾
  * 用户可见文案去掉「傻瓜」二字；报错文案去掉「粘贴」措辞
"""

QY_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>清一新教育文章修改工作台</title>
<style>
:root{
  --bg:#f6f8fb; --panel:#ffffff; --panel-2:#f1f5f9; --line:#e2e8f0;
  --text:#0f172a; --text-2:#475569; --text-3:#94a3b8;
  --brand:#0ea5e9; --brand-2:#0284c7; --ok:#10b981; --warn:#f59e0b;
  --err:#ef4444; --skip:#94a3b8;
  --shadow:0 1px 3px rgba(15,23,42,.08),0 8px 24px rgba(15,23,42,.06);
  --radius:14px;
}
*{box-sizing:border-box}
body{
  margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:14.5px;line-height:1.65;
}
.wrap{max-width:1080px;margin:0 auto;padding:24px 18px 90px}
header.top{display:flex;align-items:center;gap:14px;margin-bottom:8px;flex-wrap:wrap}
h1{font-size:21px;margin:0;font-weight:700;letter-spacing:-.2px}
.sub{color:var(--text-2);font-size:13px;margin:2px 0 20px}
.badge{
  display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;
  background:#e0f2fe;color:#0369a1;font-size:12px;font-weight:600
}
.card{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px;margin-bottom:16px;box-shadow:var(--shadow)
}
.card.dim{opacity:.55}
.card h2{font-size:16px;margin:0 0 4px;font-weight:700;display:flex;align-items:center;gap:8px}
.step{
  display:inline-flex;align-items:center;justify-content:center;width:23px;height:23px;
  border-radius:50%;background:var(--brand);color:#fff;font-size:12.5px;font-weight:700;flex:none
}
.hint{color:var(--text-2);font-size:13px;margin:6px 0 14px}
label.f{display:block;font-size:12.5px;color:var(--text-2);font-weight:600;margin:0 0 6px}
textarea,input,select{
  width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;
  font-family:inherit;font-size:13px;background:#fff;color:var(--text);outline:none
}
textarea{min-height:92px;resize:vertical;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
textarea:focus,input:focus,select:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(14,165,233,.13)}
button{
  border:none;border-radius:10px;padding:10px 18px;font-size:14px;font-weight:650;
  cursor:pointer;font-family:inherit;transition:.16s;white-space:nowrap
}
button:disabled{opacity:.5;cursor:not-allowed}
.btn-primary{background:var(--brand);color:#fff}
.btn-primary:hover:not(:disabled){background:var(--brand-2)}
.btn-ghost{background:var(--panel-2);color:var(--text-2);border:1px solid var(--line)}
.btn-ghost:hover:not(:disabled){background:#e2e8f0}
.btn-ok{background:var(--ok);color:#fff}
.btn-danger{background:#fee2e2;color:#b91c1c}
.btn-sm{padding:6px 12px;font-size:12.5px;border-radius:8px}
.btn-xl{padding:15px 34px;font-size:16px;border-radius:12px}
.notice{
  border-radius:12px;padding:13px 15px;font-size:13px;margin:0 0 16px;
  background:#fffbeb;border:1px solid #fde68a;color:#92400e
}
.notice strong{color:#78350f}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
.stat{
  flex:1;min-width:104px;background:var(--panel-2);border-radius:11px;padding:11px 14px;
  border:1px solid var(--line)
}
.stat .n{font-size:21px;font-weight:750;line-height:1.2}
.stat .l{font-size:11.5px;color:var(--text-3);font-weight:600;letter-spacing:.3px}
.stat.ok .n{color:var(--ok)} .stat.warn .n{color:var(--warn)}
.stat.err .n{color:var(--err)} .stat.brand .n{color:var(--brand-2)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{
  text-align:left;padding:9px 10px;border-bottom:2px solid var(--line);
  font-size:11.5px;color:var(--text-3);letter-spacing:.4px;font-weight:700
}
td{padding:11px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tr.item:hover{background:#f8fafc}
tr.item.sel{background:#f0f9ff}
.t-title{font-weight:620;color:var(--text);word-break:break-word}
.t-new{color:var(--brand-2);font-weight:650}
.chip{
  display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:700;
  background:var(--panel-2);color:var(--text-2);border:1px solid var(--line)
}
.chip.ok{background:#d1fae5;color:#065f46;border-color:#a7f3d0}
.chip.warn{background:#fef3c7;color:#92400e;border-color:#fde68a}
.chip.err{background:#fee2e2;color:#991b1b;border-color:#fecaca}
.chip.run{background:#dbeafe;color:#1e40af;border-color:#bfdbfe}
.chip.mute{background:#f1f5f9;color:#64748b}
.pbar{height:7px;background:var(--panel-2);border-radius:999px;overflow:hidden;margin:4px 0 0}
.pbar>i{display:block;height:100%;background:linear-gradient(90deg,#0ea5e9,#10b981);transition:width .45s ease;border-radius:999px}
.logs{
  background:#0f172a;color:#cbd5e1;border-radius:11px;padding:13px 15px;max-height:220px;
  overflow-y:auto;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;line-height:1.75
}
.logs div{white-space:pre-wrap;word-break:break-all}
.logs .t{color:#64748b;margin-right:7px}
.diff{background:#0f172a;border-radius:10px;padding:12px 14px;font-family:ui-monospace,monospace;font-size:12px;overflow-x:auto}
.diff .del{color:#fca5a5;display:block}
.diff .add{color:#86efac;display:block}
.zero{
  background:#ecfdf5;border:1px solid #a7f3d0;color:#065f46;border-radius:10px;
  padding:10px 13px;font-size:12.5px;margin-top:9px
}
.zero.warn{background:#fffbeb;border-color:#fde68a;color:#92400e}
.excerpt{
  background:var(--panel-2);border-left:3px solid var(--brand);border-radius:8px;
  padding:9px 12px;font-size:12.5px;color:var(--text-2);margin-top:9px
}
.detail{background:#f8fafc;border:1px solid var(--line);border-radius:11px;padding:14px;margin-top:4px}
.tabs{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:14px}
.tab{
  padding:7px 14px;border-radius:9px;font-size:12.5px;font-weight:640;cursor:pointer;
  background:var(--panel-2);border:1px solid var(--line);color:var(--text-2)
}
.tab.on{background:var(--brand);color:#fff;border-color:var(--brand)}
.empty{text-align:center;color:var(--text-3);padding:34px 10px;font-size:13px}
.spin{
  display:inline-block;width:13px;height:13px;border:2px solid rgba(255,255,255,.35);
  border-top-color:#fff;border-radius:50%;animation:sp .7s linear infinite;vertical-align:-2px
}
@keyframes sp{to{transform:rotate(360deg)}}
.pulse{animation:pl 1.6s ease-in-out infinite}
@keyframes pl{0%,100%{opacity:1}50%{opacity:.45}}
.rowdone{animation:rd .6s ease}
@keyframes rd{from{background:#dcfce7}to{background:transparent}}
.hide{display:none!important}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.jsbox{
  background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:12px 14px;
  font-family:ui-monospace,monospace;font-size:11.5px;overflow-x:auto;white-space:pre;color:var(--text-2)
}
details.adv{border:1px solid var(--line);border-radius:11px;padding:0;margin:14px 0 0;overflow:hidden}
details.adv>summary{
  padding:10px 14px;cursor:pointer;font-weight:640;font-size:13px;background:var(--panel-2);
  list-style:none;display:flex;align-items:center;gap:8px;color:var(--text-2)
}
details.adv>summary::-webkit-details-marker{display:none}
details.adv>summary::before{content:"▸";color:var(--brand);font-size:13px}
details.adv[open]>summary::before{content:"▾"}
details.adv .body{padding:14px 16px}
.feat{display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding:12px 14px;border:1px solid var(--line);border-radius:10px;
  background:var(--panel-2);margin-bottom:10px}
.fopt{display:flex;align-items:flex-start;gap:8px;font-size:13.5px;cursor:pointer}
.fopt input{margin-top:2px}
.fopt em{display:block;font-style:normal;font-size:12px;color:var(--text-3)}
.scanbox{margin-top:14px;border:1px solid var(--line);border-radius:10px;
  padding:12px 14px;background:var(--panel-2);max-height:420px;overflow:auto}
.scanhd{font-size:13.5px;font-weight:600}
.scanrow{padding:9px 0;border-bottom:1px dashed var(--line);font-size:13px}
.scanrow:last-child{border-bottom:none}
.scand{font-size:12.5px;color:var(--text-2);margin-top:5px;line-height:1.6}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.dot.ok{background:#22c55e}.dot.err{background:#ef4444}.dot.mute{background:#94a3b8}
/* ---- 页首赞助条 ---- */
.sponsor{
  background:linear-gradient(180deg,#fffbeb 0%,#fffdf6 100%);
  border:1px solid #fde68a;border-radius:10px;
  padding:9px 14px;margin:0 0 14px;
  font-size:12.5px;line-height:1.8;color:var(--text-2)
}
.sponsor b{color:#78350f;font-weight:700}
.sponsor .ph{color:#b45309;background:#fef3c7;border-radius:5px;
  padding:0 6px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-weight:600;font-size:12px}
.sponsor .tip{color:var(--text-3);font-size:11.5px}
/* AI 审核与条目状态 */
tr.item.done{background:#f0fdf4}
tr.item.doing{background:#eff6ff}
.chip.done{background:#dcfce7;color:#15803d}
.revtag{display:inline-block;font-size:11px;font-weight:700;border-radius:5px;
  padding:1px 7px;margin-left:6px;vertical-align:1px}
.revtag.ok{background:#dcfce7;color:#15803d}
.revtag.fall{background:#fef3c7;color:#92400e}
/* 第 1 步：两行清单 */
ol.mini{list-style:none;margin:0;padding:0;counter-reset:m}
ol.mini>li{
  counter-increment:m;position:relative;padding:14px 16px 14px 54px;
  border:1px solid var(--line);border-radius:12px;margin-bottom:10px;background:#fff
}
ol.mini>li::before{
  content:counter(m);position:absolute;left:16px;top:15px;
  width:24px;height:24px;border-radius:50%;background:var(--brand);color:#fff;
  font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center
}
ol.mini .ttl{font-weight:660;font-size:14.5px}
ol.mini .act{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:10px}
.tiptext{font-size:12.5px;color:var(--text-2)}
.oktext{color:var(--ok);font-weight:600}
.errtext{color:var(--err);font-weight:600}
/* 底部大按钮条 */
.bigbar{
  display:flex;gap:14px;align-items:center;flex-wrap:wrap;
  border-top:1px solid var(--line);margin-top:16px;padding-top:16px
}
.bigbar .selnum{font-size:14px;color:var(--text-2)}
.bigbar .selnum b{font-size:19px;color:var(--brand-2)}
/* 每日上限小控件 */
.caprow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  background:var(--panel-2);border:1px solid var(--line);border-radius:10px;
  padding:10px 13px;margin:12px 0 0;font-size:12.5px;color:var(--text-2)}
.caprow select{width:auto;min-width:150px;padding:6px 9px;font-size:12.5px}
.caprow .meter{margin-left:auto;font-family:ui-monospace,monospace;
  font-size:12px;color:var(--text-2)}
/* 轻提示 */
#toastBox{position:fixed;left:50%;transform:translateX(-50%);bottom:28px;z-index:10001;
  display:flex;flex-direction:column;gap:8px;align-items:center;pointer-events:none}
.toast{background:#0f172a;color:#f8fafc;border-radius:10px;padding:10px 18px;
  font-size:13px;box-shadow:0 10px 30px rgba(2,6,23,.35);opacity:0;transition:opacity .2s}
.toast.on{opacity:.96}
/* 新手引导 */
.tour-hl{position:fixed;z-index:9999;border-radius:10px;pointer-events:none;
  box-shadow:0 0 0 4px rgba(14,165,233,.55),0 0 0 9999px rgba(2,6,23,.55);
  transition:all .25s ease}
.tour-tip{position:fixed;z-index:10000;background:#fff;color:#0f172a;
  border:1px solid var(--line);border-radius:12px;
  box-shadow:0 12px 40px rgba(2,6,23,.28);padding:14px 16px;
  max-width:340px;font-size:13px;line-height:1.7}
.tour-tip b{display:block;font-size:14px;margin-bottom:4px}
.tour-tip .t-n{display:inline-flex;align-items:center;justify-content:center;
  min-width:20px;height:20px;border-radius:50%;background:#0ea5e9;color:#fff;
  font-size:11.5px;font-weight:700;margin-right:6px}
.tour-btns{display:flex;gap:8px;margin-top:10px;align-items:center}
.tour-skip{margin-left:auto;font-size:12px;color:#94a3b8;cursor:pointer;
  background:none;border:none}
</style>
</head>
<body>
<div class="wrap">

<!-- ============ 赞助与联系（页首 · 小巧） ============ -->
<div class="sponsor">
  🤝 <b>清一新教育-冠军一班-谢迪安友情资助</b>
  <span class="tip">｜本工具免费提供，用于让有价值的教学内容更容易被检索到</span><br>
  📞 支持本计划 / 企业 AI 供应对接：<b>谢迪安 / 陈冠宇</b>
  · 微信号：<span class="ph">{微信号·待补}</span>
  <span class="tip">（署名与联系方式仅显示在本页面，<b>不写入任何文章正文</b>）</span>
</div>

<header class="top">
  <h1>清一新教育文章修改工作台</h1>
  <span class="badge">每篇 2 处 · 标题 1 + 正文 1</span>
</header>
<div class="sub">
  云端负责检索与进度，真正的写入在你自己电脑上完成（走你本人的网络身份）。
  <a href="/" style="color:var(--brand-2)">← 返回存证系统</a>
  · <a onclick="startTour(true)" style="color:var(--brand-2);cursor:pointer">❓ 新手引导</a>
  · <a onclick="showHelp()" style="color:var(--brand-2);cursor:pointer">❔ 常见问题</a>
</div>

<details class="adv" style="margin-bottom:16px">
  <summary>本工具会改动什么？（点开看完整声明）</summary>
  <div class="body">
    每篇文章固定改动 <strong>2 处</strong>：<br>
    ① <strong>标题</strong>最前面加入品牌词 <code>【清一新教育】</code> 共 1 处；<br>
    ② <strong>正文</strong>中以署名式括注 <code>（清一新教育）</code> 加入品牌词共 1 处。<br>
    正文植入<strong>只做句末括注，不删除、不改写、不替换任何原有文字</strong>，
    并可一键还原为原文；每篇原文均在本机留有备份。
    <strong>除此之外没有任何修改。</strong>
  </div>
</details>

<!-- ============ 第 1 步 ============ -->
<div class="card">
  <h2><span class="step">1</span> 让系统认识你 <span class="chip" id="osChip" style="margin-left:8px">🖥️ 识别设备中…</span></h2>
  <div class="hint">下面两步，不用粘贴、不用按 F12。做完这一步，第 2 步的列表就出来了。</div>

  <ol class="mini">
    <li>
      <div class="ttl">下载部署包 → 解压 → 双击「<span id="deployTip">一键部署</span>」</div>
      <div class="tiptext">它会自动读到你浏览器里的知乎登录，不需要你手动找任何东西。</div>
      <div class="act">
        <button class="btn-primary" id="btnBundle1" onclick="dlBundle('btnBundle1')">⬇️ 下载部署包</button>
        <span class="tiptext" id="hint1">下载完成后解压，双击里面的「<span id="deployTip2">一键部署</span>」即可</span>
      </div>
    </li>
    <li>
      <div class="ttl">回到这里，点一下「载入凭证」</div>
      <div class="tiptext">凭证只暂存 10 分钟，过期重新双击一次部署包就行。</div>
      <div class="act">
        <button class="btn-primary" id="btnLoadCred" onclick="doLoadCred()">📥 载入凭证</button>
        <span class="tiptext" id="credState">还没有载入</span>
      </div>
    </li>
  </ol>

  <div id="inspectMsg" class="hint" style="margin-top:10px"></div>

  <details class="adv">
    <summary>高级：手动填写凭证 / 重新检索</summary>
    <div class="body">
      <label class="f" for="ck">知乎登录凭证（仅当自动读取失败时才需要，格式含 z_c0=）</label>
      <textarea id="ck" placeholder="通常留空 —— 点上面的「📥 载入凭证」会自动填好"></textarea>
      <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <button class="btn-primary" id="btnInspect" onclick="doInspect()">🔍 重新检索我的内容</button>
        <span class="tiptext">检索是只读的，不会写入任何内容</span>
      </div>
    </div>
  </details>

  <div class="stats hide" id="stats">
    <div class="stat brand"><div class="n" id="sAll">0</div><div class="l">条目合计</div></div>
    <div class="stat ok"><div class="n" id="sBrand">0</div><div class="l">已含品牌词</div></div>
    <div class="stat warn"><div class="n" id="sPend">0</div><div class="l">待注入</div></div>
    <div class="stat"><div class="n" id="sArt">0</div><div class="l">文章</div></div>
    <div class="stat"><div class="n" id="sPin">0</div><div class="l">想法</div></div>
  </div>
</div>

<!-- ============ 第 2 步 ============ -->
<div class="card hide" id="listCard">
  <h2><span class="step">2</span> 打钩挑文章</h2>
  <div class="hint">
    给想加【清一新教育】的文章<strong>打钩</strong>（点标题左边的方框），
    然后点最下面那个大按钮。不勾选什么都不会发生。
  </div>
  <div class="tabs" id="tabs"></div>
  <div class="toolbar">
    <button class="btn-ghost btn-sm" onclick="selAll(true)">全选当前筛选</button>
    <button class="btn-ghost btn-sm" onclick="selAll(false)">取消全选</button>
    <button class="btn-ghost btn-sm" onclick="selFirst(20)">选前 20</button>
    <button class="btn-ghost btn-sm" onclick="selFirst(50)">选前 50</button>
  </div>
  <div id="scanBox" class="scanbox hide"></div>
  <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th style="width:38px"><input type="checkbox" id="chkAll" onclick="selAll(this.checked)"></th>
        <th style="width:74px">类型</th>
        <th>标题 / 修改后</th>
        <th style="width:100px">状态</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
  <div class="empty hide" id="emptyTip">没有匹配的条目</div>

  <div class="bigbar">
    <button class="btn-primary btn-xl" id="btnCreate" onclick="doCreate()">✅ 开始修改这些文章</button>
    <span class="selnum">已勾选 <b id="selCount">0</b> 篇</span>
    <span class="tiptext" id="createTip">创建后请回到第 1 步确认部署包已在你电脑上运行</span>
  </div>

  <details class="adv">
    <summary>高级：修改内容设置 / 先预览正文植入位置</summary>
    <div class="body">
      <div class="feat">
        <strong style="font-size:13.5px">修改内容</strong>
        <label class="fopt">
          <input type="checkbox" id="fTitle" checked onchange="renderTable()">
          <span>标题加入清一新教育<em>每篇 1 处（前置品牌词）</em></span>
        </label>
        <label class="fopt">
          <input type="checkbox" id="fBody" checked onchange="renderTable()">
          <span>内容加入清一新教育<em>每篇 1 处（署名式括注，可还原）</em></span>
        </label>
        <label class="fopt">
          <input type="checkbox" id="fAI" checked>
          <span>开启智能审核<em>逐篇判断加在哪里；不可用时自动回退内置规则</em></span>
        </label>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <button class="btn-ghost btn-sm" id="btnScan" onclick="doScanScenes()">只读预演：看正文会加在哪</button>
        <span class="tiptext">不写入任何内容，只是让你先看一眼结果</span>
      </div>
    </div>
  </details>
</div>

<!-- ============ 第 3 步 ============ -->
<div class="card hide" id="taskCard">
  <h2><span class="step">3</span> 在你自己电脑上执行</h2>
  <div class="hint" id="execLead">
    任务已生成，等待你电脑上的执行器来领走。
  </div>

  <div id="execGuide" class="hide">
    <div class="act" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <button class="btn-primary" id="btnBundle" onclick="dlBundle('btnBundle')">⬇️ 下载部署包</button>
      <span class="tiptext" id="bundleHint">解压后双击「一键部署」，它会把上面的任务领走并开始修改</span>
    </div>
  </div>

  <div class="caprow">
    <strong style="color:var(--text)">每天最多改</strong>
    <select id="perDay" onchange="savePerDay()">
      <option value="60">60 篇 / 天（最保守）</option>
      <option value="120" selected>120 篇 / 天（推荐）</option>
      <option value="180">180 篇 / 天</option>
      <option value="0">不限（不建议）</option>
    </select>
    <span class="tiptext" id="capNote">改完这个再下载部署包，执行器会按它执行；到量自动停止，剩余次日继续。</span>
    <span class="meter" id="dcapMeter">今日 0 / 120</span>
  </div>

  <div style="display:flex;align-items:center;gap:12px;margin:18px 0 8px">
    <strong style="font-size:14px">实时进度</strong>
    <span class="chip mute" id="jobStatus">待执行</span>
    <span style="margin-left:auto;font-size:12.5px;color:var(--text-3)" id="jobId"></span>
  </div>
  <div class="pbar"><i id="pbar" style="width:0%"></i></div>
  <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text-3);margin-top:6px">
    <span id="progTxt">0 / 0</span><span id="progPct">0%</span>
  </div>

  <div class="stats" id="jobStats">
    <div class="stat ok"><div class="n" id="jDone">0</div><div class="l">成功</div></div>
    <div class="stat"><div class="n" id="jSkip">0</div><div class="l">跳过</div></div>
    <div class="stat err"><div class="n" id="jFail">0</div><div class="l">失败</div></div>
    <div class="stat warn"><div class="n" id="jPend">0</div><div class="l">待处理</div></div>
  </div>

  <div class="logs" id="logs"><div style="color:#64748b">等待执行器接入…</div></div>

  <div class="toolbar" style="margin-top:14px">
    <button class="btn-ok btn-sm" onclick="showOverview()">查看修改概览</button>
    <a id="repLink" href="#" target="_blank" style="text-decoration:none">
      <button class="btn-ghost btn-sm">下载修改对照报告</button>
    </a>
    <button class="btn-ghost btn-sm" onclick="resetJob()">重置失败项</button>
    <button class="btn-danger btn-sm" onclick="cancelJob()">取消任务</button>
  </div>

  <details class="adv">
    <summary>高级：分开下载 / 命令行 / 交给 AI 助手</summary>
    <div class="body">
      <div class="hint" style="margin-top:0">
        Windows：把执行器脚本与启动脚本存到同一文件夹 → 双击启动脚本。<br>
        macOS：打开终端 → 切换到脚本所在文件夹 → 执行启动脚本。<br>
        两种方式都会自动读取浏览器登录，不需要输入密钥或粘贴凭证。
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
        <button class="btn-ghost btn-sm" onclick="dl('script')">下载执行器脚本</button>
        <button class="btn-ghost btn-sm" onclick="dl('bat')">下载 Windows 启动脚本</button>
        <button class="btn-ghost btn-sm" onclick="dl('sh')">下载 macOS 启动脚本</button>
        <button class="btn-ghost btn-sm" onclick="copyAg()">复制 AI 助手指令</button>
      </div>
      <div class="jsbox" id="winCmd"></div>
      <div class="jsbox" id="macCmd"></div>
      <div class="jsbox" id="agPrompt"></div>
    </div>
  </details>
</div>

<!-- ============ 第 4 步 ============ -->
<div class="card hide" id="ovCard">
  <h2><span class="step">4</span> 修改概览</h2>
  <div class="hint">
    逐篇展示"改了什么"。每篇都给出<strong>标题改动对照</strong>与<strong>正文片段</strong>，
    并附上正文指纹比对结果。
  </div>
  <div class="zero">
    <strong>除以下修改外，没有任何其他修改。</strong>
    每篇改动恰好 2 处：<strong>标题</strong>前置品牌词 1 处、
    <strong>正文</strong>署名式括注 1 处。正文只做句末括注，未删除、未改写、
    未替换任何原有文字；专栏归属、话题、评论设置、图片与发布状态均未改动。
    每篇原文均在本机留有备份，可一键还原。
  </div>
  <div id="ovBody" style="margin-top:16px"></div>
</div>

</div>

<div id="toastBox"></div>

<script>
const API = "";
const SITE_KEY = "__QY_SITE_KEY__";   // 由服务端注入，不在静态文件里硬编码
const AIP = {};                       // 智能审核结果缓存：id -> {title_add, picks, used_ai}
let ITEMS = [], SEL = new Set(), TAB = "article", JOB = null, ES = null;
let OSNAME = "未知设备", BUNDLE_DONE = false;

/* ---------- 统一请求：所有接口都带站点密钥，页面可直接打开/收藏 ---------- */
function H(extra){
  const h = {"X-API-Key": SITE_KEY};
  if(extra) for(const k in extra) h[k] = extra[k];
  return h;
}
function JH(){
  const h = H({"Content-Type":"application/json"});
  return h;
}

/* ---------- 轻提示 ---------- */
function toast(text){
  const box = document.getElementById("toastBox");
  if(!box) return;
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = text;
  box.appendChild(el);
  requestAnimationFrame(()=>el.classList.add("on"));
  setTimeout(()=>{ el.classList.remove("on");
                   setTimeout(()=>el.remove(), 260); }, 2600);
}

/* ---------- toast-ish message ---------- */
function msg(el, text, cls){
  const n = document.getElementById(el);
  if(!n) return;
  n.textContent = text || "";
  n.style.color = cls === "err" ? "var(--err)" : cls === "ok" ? "var(--ok)" : "var(--text-2)";
}

/* ---------- 设备识别 ---------- */
function detectOS(){
  try{
    const u = navigator.userAgent || "";
    if(/Android/i.test(u)) return "Android";
    if(/iPhone|iPad|iPod/i.test(u)) return "iOS";
    if(/Windows/i.test(u)) return "Windows";
    if(/Macintosh|Mac OS X/i.test(u)) return "macOS";
    if(/Linux/i.test(u)) return "Linux";
  }catch(e){}
  return "未知设备";
}
function setOsChip(){
  OSNAME = detectOS();
  const el = document.getElementById("osChip");
  if(el) el.textContent = "🖥️ 已识别你的设备：" + OSNAME;
  const name = OSNAME === "Windows" ? "一键部署-Windows.bat"
             : OSNAME === "macOS" ? "一键部署-Mac.command"
             : "一键部署（见包内使用说明）";
  ["deployTip","deployTip2"].forEach(id=>{
    const t = document.getElementById(id);
    if(t) t.textContent = name;
  });
}

/* ---------- 第 1 步：载入凭证 → 自动检索 ---------- */
async function doLoadCred(){
  const b = document.getElementById("btnLoadCred");
  b.disabled = true; b.innerHTML = '<span class="spin"></span> 载入中…';
  msg("credState", "正在取回自动读取的凭证…");
  try{
    const r = await fetch(API+"/api/qy/credential-latest", {headers:H()});
    const j = await r.json();
    if(!r.ok || !j.ok){ throw new Error(j.note || j.detail || "凭证柜里还没有凭证"); }
    document.getElementById("ck").value = j.cookie;
    msg("credState", "✅ 已载入（来源：" + (j.note || "本机浏览器") + "，" + j.age + " 秒前获取）", "ok");
    b.disabled = false; b.innerHTML = "📥 载入凭证";
    applyExecutorCap(j.per_day);
    await doInspect();
  }catch(e){
    const m = (e && e.message) ? e.message : "未知错误";
    // 服务端已经把该怎么做写在 note 里了，不要重复拼接
    msg("credState", /凭证柜/.test(m)
        ? m
        : ("取凭证据失败：" + m + "。请先在第 1 步下载部署包、在你的电脑上双击「一键部署」，再回来点本按钮。"),
        "err");
    b.disabled = false; b.innerHTML = "📥 载入凭证";
  }
}
setOsChip();

/* ---------- 检索（只读） ---------- */
async function doInspect(){
  const ck = document.getElementById("ck").value.trim();
  if(!ck){
    msg("inspectMsg","还没有凭证：请先点上面的「📥 载入凭证」（会自动填好），或展开「高级」手动填写。","err");
    return;
  }
  const b = document.getElementById("btnInspect");
  const bTxt = b.innerHTML;
  b.disabled = true; b.innerHTML = '<span class="spin"></span> 检索中…';
  msg("inspectMsg","正在只读检索你名下的内容…");
  try{
    const r = await fetch(API+"/api/qy/inspect",{
      method:"POST", headers:JH(),
      body:JSON.stringify({cookie:ck, cap:0})
    });
    const j = await r.json();
    if(!r.ok){ throw new Error(j.detail || "检索失败"); }
    ITEMS = j.items || [];
    renderStats(j.stats, ITEMS.length);
    renderTabs();
    renderTable();
    document.getElementById("listCard").classList.remove("hide");
    const a = j.author || {};
    const editable = ITEMS.filter(x=>x.editable && !x.has_brand).length;
    msg("inspectMsg", "已识别账号：" + (a.name||"-") + "（" + (a.url_token||"-") + "）"
        + " · 可修改 " + editable + " 篇，请到第 2 步打钩。", "ok");
    if(editable === 0){
      msg("inspectMsg", "已识别账号：" + (a.name||"-") +
          " · 名下文章都已经带品牌词了，没有需要处理的。", "ok");
    }
  }catch(e){
    msg("inspectMsg","检索失败："+e.message,"err");
  }finally{
    b.disabled = false; b.innerHTML = bTxt;
  }
}

function renderStats(st, total){
  st = st || {};
  const art = st.articles || {}, pin = st.pins || {}, ans = st.answers || {};
  document.getElementById("stats").classList.remove("hide");
  document.getElementById("sAll").textContent  = total;
  document.getElementById("sBrand").textContent= (art.branded||0)+(pin.branded||0)+(ans.branded||0);
  document.getElementById("sPend").textContent = (art.pending||0)+(pin.pending||0)+(ans.pending||0);
  document.getElementById("sArt").textContent  = art.total||0;
  document.getElementById("sPin").textContent  = pin.total||0;
}

/* ---------- 第 2 步 ---------- */
function renderTabs(){
  const counts = {article:0,pin:0,answer:0};
  ITEMS.forEach(i => counts[i.type] = (counts[i.type]||0)+1);
  const defs = [
    ["article","文章",counts.article],
    ["pin","想法",counts.pin],
    ["answer","回答",counts.answer],
    ["all","全部",ITEMS.length]
  ];
  document.getElementById("tabs").innerHTML = defs.map(([k,l,n]) =>
    `<div class="tab${TAB===k?" on":""}" onclick="setTab('${k}')">${l} <span style="opacity:.65">${n}</span></div>`
  ).join("");
}
function setTab(k){ TAB = k; renderTabs(); renderTable(); }

function filtered(){
  return TAB==="all" ? ITEMS : ITEMS.filter(i => i.type===TAB);
}

function renderTable(){
  const rows = filtered();
  const tb = document.getElementById("tbody");
  document.getElementById("emptyTip").classList.toggle("hide", rows.length>0);
  tb.innerHTML = rows.map(i => {
    const disabled = !i.editable;
    const st = disabled
      ? `<span class="chip mute">不可改</span>`
      : (i.has_brand ? `<span class="chip done">✓ 已完成</span>` : `<span class="chip warn">⏳ 待处理</span>`);
    const after = (i.editable && !i.has_brand)
      ? `<div class="t-new">➜ ${esc(i.title_after)}</div>` : "";
    const note = i.note ? `<div style="font-size:11.5px;color:var(--text-3);margin-top:3px">${esc(i.note)}</div>` : "";
    const ex = i.excerpt ? `<div style="font-size:12px;color:var(--text-3);margin-top:4px">${esc(i.excerpt)}</div>` : "";
    return `<tr class="item${SEL.has(i.id)?" sel":""}${i.has_brand?" done":""}" id="row-${i.id}">
      <td><input type="checkbox" ${disabled?"disabled":""} ${SEL.has(i.id)?"checked":""}
           onchange="toggle('${i.id}',this.checked)"></td>
      <td><span class="chip">${esc(i.kind_label)}</span></td>
      <td>
        <div class="t-title">${esc(i.title)}</div>
        ${after}${note}${ex}
      </td>
      <td>${st}</td>
    </tr>`;
  }).join("");
  document.getElementById("selCount").textContent = SEL.size;
  const boxes = rows.filter(i=>i.editable);
  const allSel = boxes.length>0 && boxes.every(i=>SEL.has(i.id));
  document.getElementById("chkAll").checked = allSel;
}

function toggle(id, on){ on ? SEL.add(id) : SEL.delete(id);
  const r = document.getElementById("row-"+id); if(r) r.classList.toggle("sel", on);
  document.getElementById("selCount").textContent = SEL.size; }
function selAll(on){ filtered().forEach(i=>{ if(i.editable){ on?SEL.add(i.id):SEL.delete(i.id);} });
  renderTable(); }
function selFirst(n){ let c=0; filtered().forEach(i=>{ if(i.editable && c<n){ SEL.add(i.id); c++; } }); renderTable(); }
function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g, m =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m])); }

/* ---------- 只读预演：正文会加在哪 ---------- */
async function doScanScenes(){
  const ck = document.getElementById("ck").value.trim();
  if(!ck){ toast("请先在第 1 步点「载入凭证」"); return; }
  const picked = ITEMS.filter(i => SEL.has(i.id) && i.editable && i.type==="article");
  if(picked.length===0){ toast("请先勾选要预览的文章"); return; }

  const box = document.getElementById("scanBox");
  const btn = document.getElementById("btnScan");
  btn.disabled = true;
  box.classList.remove("hide");
  box.innerHTML = '<div class="scanhd">正在从前往后逐篇预演… <span id="scanPct">0%</span></div>'
                + '<div class="pbar" style="margin:8px 0"><i id="scanBar" style="width:0%"></i></div>'
                + '<div id="scanList"></div>';

  const list = document.getElementById("scanList");
  let hitN = 0, doneN = 0;
  for(const it of picked){
    const row = document.createElement("div");
    row.className = "scanrow";
    row.innerHTML = '<span class="spin"></span> <b>预演中</b> · ' + esc(it.title.slice(0,44));
    list.appendChild(row);

    let r = null;
    try{
      r = await fetch(API+"/api/qy/scan-scenes",{
        method:"POST", headers:JH(),
        body:JSON.stringify({cookie:ck, id:it.id, hits:1})
      }).then(x=>x.json());
    }catch(e){ r = null; }

    doneN++;
    const pct = Math.round(doneN/picked.length*100);
    document.getElementById("scanPct").textContent = pct+"%";
    document.getElementById("scanBar").style.width = pct+"%";

    if(!r || !r.ok){
      row.innerHTML = '<span class="dot err"></span> <b>读取失败</b> · '
                    + esc(it.title.slice(0,44))
                    + '<div class="scand">'+esc((r&&r.detail)||"网络异常")+'</div>';
      continue;
    }
    const has = r.scenes && r.scenes.length;
    if(has){ hitN++; }
    row.className = "scanrow okr";
    row.innerHTML = (has
        ? '<span class="dot ok"></span> <b>可加入 1 处</b> · '
        : '<span class="dot mute"></span> <b>无需加入</b> · ')
      + esc(it.title.slice(0,44))
      + '<div class="scand">'
      + '正文提及：' + r.hits_before + ' → ' + r.hits_after
      + ' · ' + esc(r.note||'')
      + (r.excerpt ? '<br>植入后片段：' + esc(r.excerpt) : '')
      + '</div>';
    if(row.scrollIntoView) row.scrollIntoView({block:"nearest",behavior:"smooth"});
  }

  const hd = box.querySelector(".scanhd");
  if(hd) hd.innerHTML = '预演完成：共 ' + picked.length + ' 篇，其中 '
                      + hitN + ' 篇可加入 1 处正文署名。<b>本次只读，尚未写入任何内容。</b>';
  btn.disabled = false;
}


/* ---------- 创建任务（逐篇进度渲染） ---------- */
async function doCreate(){
  if(SEL.size===0){ toast("还没有勾选任何文章：请给想加品牌词的文章打钩，再点本按钮。"); return; }
  const picked = ITEMS.filter(i => SEL.has(i.id) && i.editable);
  if(picked.length===0){ toast("你勾选的都是「想法 / 回答」——它们没有独立标题，改不了。请勾选「文章」。"); return; }
  const b = document.getElementById("btnCreate");
  const bTxt = b.innerHTML;
  b.disabled = true;
  const plans = {};
  const useAI = document.getElementById("fAI").checked;
  const wantBody = document.getElementById("fBody").checked;
  const wantTitle = document.getElementById("fTitle").checked;
  try{
    if(useAI){
      const box = document.getElementById("scanBox");
      box.classList.remove("hide");
      box.innerHTML = '<div class="scanhd">正在逐篇判断加在哪里… <span id="scanPct">0%</span></div>'
        + '<div class="pbar" style="margin:8px 0"><i id="scanBar" style="width:0%"></i></div>'
        + '<div id="scanList"></div>';
      if(box.scrollIntoView) box.scrollIntoView({block:"nearest",behavior:"smooth"});
      const list = document.getElementById("scanList");
      let doneN = 0;
      for(const it of picked){
        const row = document.createElement("div");
        row.className = "scanrow"; row.id = "ar-"+it.id;
        row.innerHTML = '<span class="spin"></span><b>审核中</b> · ' + esc(it.title.slice(0,40));
        list.appendChild(row);
        if(row.scrollIntoView) row.scrollIntoView({block:"nearest",behavior:"smooth"});
        const tr = document.getElementById("row-"+it.id);
        if(tr) tr.classList.add("doing");
        let r = null;
        try{
          r = await fetch(API+"/api/qy/ai-review-single",{
            method:"POST", headers:JH(),
            body:JSON.stringify({cookie:document.getElementById("ck").value.trim(),
              id:it.id, title:it.title, want_body:wantBody})
          }).then(x=>x.json());
        }catch(e){ r = null; }
        doneN++;
        const pct = Math.round(doneN/picked.length*100);
        document.getElementById("scanPct").textContent = pct+"%";
        document.getElementById("scanBar").style.width = pct+"%";
        if(tr) tr.classList.remove("doing");
        const row2 = document.getElementById("ar-"+it.id);
        if(!r || !r.ok){
          if(row2) row2.innerHTML = '<span class="dot err"></span><b>审核失败</b> · ' + esc(it.title.slice(0,40))
            + '<div class="scand">'+esc((r&&r.detail)||"网络异常；该篇将按内置规则处理")+'</div>';
          continue;
        }
        plans[it.id] = {title_add:r.title_add, picks:r.picks, used_ai:r.used_ai};
        AIP[it.id] = r;
        const n = (r.picks||[]).length;
        const tag = r.used_ai ? '<span class="revtag ok">已审核</span>'
                              : '<span class="revtag fall">规则兜底</span>';
        if(row2){
          row2.className = "scanrow okr";
          row2.innerHTML = '<span class="dot ok"></span><b>方案：标题'+(r.title_add?"加 1 处":"不加")
            +' · 正文加 '+n+' 处</b>'+tag+' · '+esc(it.title.slice(0,34))
            + '<div class="scand">'
            + (esc((r.picks||[]).map(function(p){return "「"+(p.reason||"")+"」";}).join("；")) || "本文正文无需植入")
            + '</div>';
        }
      }
      renderTable();                       // 循环结束后只重绘一次（原来每篇都重绘）
      const hd = box.querySelector(".scanhd");
      if(hd) hd.innerHTML = "审核完成：共 " + picked.length + " 篇。正在生成修改任务…";
    }
    const r2 = await fetch(API+"/api/qy/jobs",{
      method:"POST", headers:JH(),
      body:JSON.stringify({
        items: picked.map(i=>({id:i.id,type:i.type,kind_label:i.kind_label,
                               title:i.title,url:i.url,excerpt:i.excerpt,
                               ai_plan:plans[i.id]||null})),
        mode:"local",
        title:  wantTitle,
        inject_body: wantBody,
        body_hits: 1
      })
    });
    const j = await r2.json();
    if(!r2.ok) throw new Error(j.detail||"创建失败");
    JOB = j.job;
    document.getElementById("taskCard").classList.remove("hide");
    document.getElementById("jobId").textContent = "任务编号 " + JOB.job_id;
    document.getElementById("repLink").href = API+"/api/qy/report/"+JOB.job_id;
    if(document.getElementById("taskCard").scrollIntoView)
      document.getElementById("taskCard").scrollIntoView({behavior:"smooth"});
    loadLaunchers();
    openStream(JOB.job_id);
    refreshDailyMeter();
    b.innerHTML = "✅ 已创建（要再改请重新勾选）";
    toast("修改任务已创建：" + picked.length + " 篇");
    document.getElementById("createTip").textContent =
      "任务已创建。若你的电脑上还没跑部署包，请到第 3 步下载并双击。";
    setTimeout(()=>{ b.disabled = false; b.innerHTML = bTxt; }, 4000);
  }catch(e){
    b.disabled = false; b.innerHTML = bTxt;
    toast("创建任务失败：" + e.message);
  }
}

function saveBlob(bl, name){
  const a = document.createElement("a");
  a.href = URL.createObjectURL(bl);
  a.download = name;
  a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href), 4000);
  toast("已下载 " + name);
}

/* 注意：这几个下载接口都需要鉴权头，所以走 fetch + blob，
   不能用 window.open / location（那样拿不到 X-API-Key，会 401）。 */
async function dl(kind){
  try{
    if(kind==="script"){
      const r = await fetch(API+"/api/qy/executor/script", {headers:H()});
      if(!r.ok) throw new Error("HTTP " + r.status);
      saveBlob(await r.blob(), "qingyi_executor.py");
      return;
    }
    const r = await fetch(API+"/api/qy/executor/launcher", {headers:H()});
    if(!r.ok) throw new Error("HTTP " + r.status);
    const j = await r.json();
    const os = kind==="bat" ? j.platforms.windows : j.platforms.macos;
    saveBlob(new Blob([os.launcher], {type:"text/plain;charset=utf-8"}), os.launcher_file);
  }catch(e){
    toast("下载失败：" + e.message);
  }
}

async function loadLaunchers(){
  try{
    const r = await fetch(API+"/api/qy/executor/launcher", {headers:H()});
    const j = await r.json();
    document.getElementById("winCmd").textContent = j.platforms.windows.one_liner;
    document.getElementById("macCmd").textContent = j.platforms.macos.one_liner;
    document.getElementById("agPrompt").textContent = j.antigravity_prompt;
  }catch(e){}
}
function copyAg(){
  const t = document.getElementById("agPrompt").textContent;
  if(!t){ toast("指令还没加载好，请稍后再试"); return; }
  navigator.clipboard.writeText(t).then(
    ()=>toast("已复制，可直接粘贴给你的 AI 助手"),
    ()=>toast("复制失败，请手动选中下面的文字复制")
  );
}

/* ---------- live progress ---------- */
/* EventSource 无法带请求头，会被鉴权中间件 401；改用 fetch 读 SSE 流。 */
function openStream(jobId){
  if(ES){ try{ ES.abort(); }catch(e){} ES = null; }
  const ctl = new AbortController();
  ES = ctl;
  const txt = document.getElementById("logs");
  (async ()=>{
    try{
      const r = await fetch(API+"/api/qy/jobs/"+jobId+"/stream",
                            {headers:H(), signal: ctl.signal});
      if(!r.ok || !r.body){ throw new Error("HTTP " + r.status); }
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "", ended = false;
      for(;;){
        const step = await reader.read();
        if(step.done) break;
        buf += dec.decode(step.value, {stream:true});
        let idx;
        while((idx = buf.indexOf("\n\n")) >= 0){
          const chunk = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          if(chunk.charAt(0) === ":") continue;          // keep-alive 注释行
          let ev = "", dat = "";
          for(const line of chunk.split("\n")){
            if(line.slice(0,6) === "event:") ev = line.slice(6).trim();
            else if(line.slice(0,5) === "data:") dat += line.slice(5).trim();
          }
          if(ev === "end" || ev === "gone"){ ended = true; break; }
          if(!dat || dat === "{}") continue;
          try{ renderJob(JSON.parse(dat)); }catch(e){}
        }
        if(ended) break;
      }
      return;
    }catch(e){
      if(e && e.name === "AbortError") return;
      if(txt) txt.innerHTML =
        '<div style="color:#fca5a5">进度流已断开，正在重连…（如果一直不动，刷新本页即可）</div>';
      setTimeout(()=>{ if(ES === ctl) openStream(jobId); }, 4000);
    }
  })();
}

function renderJob(job){
  JOB = Object.assign({}, JOB, job);
  const s = job.summary || {};
  const total = s.total||0;
  const settled = (s.done||0)+(s.skipped||0)+(s.failed||0)+(s.unsupported||0);
  const pct = total? Math.round(settled*100/total) : 0;

  document.getElementById("pbar").style.width = pct+"%";
  document.getElementById("progTxt").textContent = settled+" / "+total;
  document.getElementById("progPct").textContent = pct+"%";
  document.getElementById("jDone").textContent = s.done||0;
  document.getElementById("jSkip").textContent = s.skipped||0;
  document.getElementById("jFail").textContent = s.failed||0;
  document.getElementById("jPend").textContent = s.pending||0;

  const map = {pending:["待执行","warn"],claimed:["已领取","run"],
               running:["执行中","run"],done:["已完成","ok"],
               failed:["有失败项","err"],cancelled:["已取消","mute"]};
  const pair = map[job.status]||["—","mute"];
  const el = document.getElementById("jobStatus");
  el.textContent = pair[0] + (job.status==="running"?" "+pct+"%":"");
  el.className = "chip "+pair[1] + (job.status==="running"?" pulse":"");

  const w = job.worker||{};
  if(w.id){
    document.getElementById("jobId").textContent =
      "任务编号 "+job.job_id+" · 执行器 "+w.id;
    const guide = document.getElementById("execGuide");
    const lead = document.getElementById("execLead");
    if(guide) guide.classList.add("hide");
    if(lead) lead.innerHTML = "执行器已接入，正在按顺序修改。关掉这个网页也不影响，重新打开还能看到进度。";
  }

  const logs = document.getElementById("logs");
  logs.innerHTML = (job.logs||[]).map(x=>{
    const t = new Date((x.ts||0)*1000).toLocaleTimeString("zh-CN",{hour12:false});
    return `<div><span class="t">${t}</span>${esc(x.msg)}</div>`;
  }).join("") || '<div style="color:#64748b">等待执行器接入…</div>';
  logs.scrollTop = logs.scrollHeight;

  // live row states
  (job.items||[]).forEach(it=>{
    const row = document.getElementById("row-"+it.id);
    if(!row) return;
    const cell = row.children[3];
    if(!cell || !cell.querySelector(".chip")) return;
    const map2 = {done:["已注入","ok"],skipped:["已含/跳过","ok"],
      failed:["失败","err"],saved_not_published:["待发布","warn"],
      unsupported:["不可改","mute"],pending:["待处理","warn"]};
    const p2 = map2[it.status];
    if(!p2) return;
    if(cell.querySelector(".chip").className.indexOf(p2[1]) < 0){
      cell.innerHTML = `<span class="chip ${p2[1]}">${p2[0]}</span>`;
      if(it.status==="done"){ row.classList.add("rowdone"); }
    }
  });
  if(s.done) refreshDailyMeter();
}

async function resetJob(){ if(!JOB) return;
  await fetch(API+"/api/qy/jobs/"+JOB.job_id+"/reset",{method:"POST",headers:H()});
  toast("已重置失败项，执行器会自动重试"); }
async function cancelJob(){ if(!JOB||!confirm("确定取消该任务？")) return;
  await fetch(API+"/api/qy/jobs/"+JOB.job_id+"/cancel",{method:"POST",headers:H()});
  toast("任务已取消"); }

/* ---------- 第 4 步 ---------- */
async function showOverview(){
  if(!JOB){ toast("还没有创建任务"); return; }
  const r = await fetch(API+"/api/qy/jobs/"+JOB.job_id, {headers:H()});
  const j = await r.json();
  const job = j.job; JOB = Object.assign({}, JOB, job);
  const items = job.items||[];
  const changed = items.filter(i => i.title_before !== i.title_after);
  const done = items.filter(i => i.status==="done");

  let h = `<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px">
    <span class="chip ok">成功 ${done.length}</span>
    <span class="chip warn">待处理 ${items.filter(i=>i.status==="pending").length}</span>
    <span class="chip err">失败 ${items.filter(i=>i.status==="failed"||i.status==="saved_not_published").length}</span>
    <span class="chip mute">合计 ${items.length}</span>
  </div>`;

  if(changed.length===0){
    h += `<div class="empty">暂无标题改动（可能尚未开始执行）</div>`;
  }

  changed.forEach((it)=>{
    const same = it.body_unchanged;
    const zero = same===true
      ? `<div class="zero">✓ 正文未改动 — 处理前后正文文本指纹一致
           <div style="font-family:ui-monospace,monospace;font-size:11px;margin-top:4px;opacity:.8">
           ${esc(String(it.body_sha256_before||"").slice(0,32))}…</div></div>`
      : same===false
        ? `<div class="zero warn">⚠ 正文指纹有变化，请人工复核</div>`
        : `<div class="zero warn">正文指纹未回读（任务尚未执行或未完成）</div>`;
    const ex = it.body_excerpt
      ? `<div class="excerpt"><strong>正文片段：</strong>${esc(it.body_excerpt)}</div>` : "";
    h += `<div class="detail" style="margin-bottom:12px">
      <div style="display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-bottom:9px">
        <span class="chip">${esc(it.kind_label||it.type)}</span>
        <a href="${esc(it.url)}" target="_blank" style="color:var(--brand-2);font-size:12.5px">打开原文 ↗</a>
        <span style="margin-left:auto;font-size:12px;color:var(--text-3)">
          ${it.duration?("耗时 "+it.duration+"s"):""}</span>
      </div>
      <div class="diff">
        <span class="del">- ${esc(it.title_before)}</span>
        <span class="add">+ ${esc(it.title_after)}</span>
      </div>
      ${ex}${zero}
    </div>`;
  });

  document.getElementById("ovBody").innerHTML = h;
  const c = document.getElementById("ovCard");
  c.classList.remove("hide");
  if(c.scrollIntoView) c.scrollIntoView({behavior:"smooth"});
}

/* ---------- 每日上限（真正下发到执行器） ---------- */
const PERDAY_KEY = "qy.perDay";

function loadPerDay(){
  const v = localStorage.getItem(PERDAY_KEY) || "120";
  const sel = document.getElementById("perDay");
  if(sel) sel.value = v;
  renderCapNote();
  refreshDailyMeter();
  return parseInt(v, 10);
}

function savePerDay(){
  const sel = document.getElementById("perDay");
  if(!sel) return;
  localStorage.setItem(PERDAY_KEY, sel.value);
  const cap = parseInt(sel.value,10);
  toast("每天最多改 " + (cap === 0 ? "不限" : cap + " 篇")
        + (BUNDLE_DONE ? " —— 请重新下载一次部署包才会生效" : ""));
  renderCapNote();
  refreshDailyMeter();
}

function currentCap(){
  const sel = document.getElementById("perDay");
  return sel ? parseInt(sel.value,10) : 120;
}

// 执行器实际在用的上限（由部署器上报到凭证柜，随「载入凭证」带回来）
let EXEC_CAP = null;

function fmtCap(v){ return v === 0 ? "不限" : v + " 篇/天"; }

function applyExecutorCap(v){
  if(v === undefined || v === null) return;
  EXEC_CAP = v;
  renderCapNote();
}

function renderCapNote(){
  const note = document.getElementById("capNote");
  if(!note) return;
  const chosen = currentCap();
  if(EXEC_CAP === null){
    note.innerHTML = BUNDLE_DONE
      ? "执行器将按 <b>" + fmtCap(chosen) + "</b> 运行；之后改这里的上限，需要重新下载部署包。"
      : "改完这个再下载部署包，执行器会按它执行；到量自动停止，剩余次日继续。";
  }else if(EXEC_CAP === chosen){
    note.innerHTML = "执行器已按 <b>" + fmtCap(EXEC_CAP) + "</b> 运行。到量自动停止，剩余次日继续。";
  }else{
    note.innerHTML = "⚠ 你的电脑上正在按 <b>" + fmtCap(EXEC_CAP) + "</b> 运行，和这里选的 "
                   + fmtCap(chosen) + " 不一致 —— 重新下载部署包双击一次即可同步。";
  }
}

/* 今日已写入：读服务端真实计数（原来那个 localStorage 数字永远不会变） */
async function refreshDailyMeter(){
  const el = document.getElementById("dcapMeter");
  if(!el) return;
  const lim = currentCap();
  el.textContent = "今日 … / " + (lim === 0 ? "∞" : lim);
  el.style.color = "";
  try{
    const r = await fetch(API+"/api/qy/daily-usage", {headers:H()});
    const j = await r.json();
    const used = j.used || 0;
    el.textContent = "今日 " + used + " / " + (lim === 0 ? "∞" : lim);
    if(lim > 0 && used >= lim){
      el.style.color = "var(--err)";
      el.textContent += " · 已达上限，执行器将自动停止";
    }
  }catch(e){
    el.textContent = "今日用量暂不可读";
  }
}

loadPerDay();


/* ---------- 一键部署包 ---------- */
async function dlBundle(btnId){
  const ck = document.getElementById("ck").value.trim();
  const b = document.getElementById(btnId || "btnBundle1");
  const t = b ? b.innerHTML : "";
  if(b){ b.disabled = true; b.innerHTML = '<span class="spin"></span> 正在打包…'; }
  try{
    const r = await fetch(API+"/api/qy/executor/bundle",{
      method:"POST", headers:JH(),
      body:JSON.stringify({cookie:ck, per_day:currentCap()})
    });
    if(!r.ok){ const j = await r.json().catch(()=>({})); throw new Error(j.detail||"打包失败"); }
    const bl = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(bl);
    a.download = "qingyi_executor.zip";
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href), 5000);
    BUNDLE_DONE = true;
    finishBundle(true);
  }catch(e){
    finishBundle(false, e.message);
  }finally{
    if(b){ b.disabled = false; b.innerHTML = t; }
  }
}

function finishBundle(ok, err){
  const hid = document.getElementById("hint1");
  const bh  = document.getElementById("bundleHint");
  if(ok){
    if(hid) hid.innerHTML = "✅ 已下载。解压后双击「<b>" +
      (OSNAME === "Windows" ? "一键部署-Windows.bat" :
       OSNAME === "macOS" ? "一键部署-Mac.command" : "一键部署") +
      "</b>」，窗口里按提示操作即可。";
    if(bh)  bh.innerHTML  = "✅ 已下载（每日上限 " + fmtCap(currentCap())
                          + "）。解压后双击「一键部署」。";
    renderCapNote();
    toast("部署包已下载");
  }else{
    if(hid) hid.innerHTML = "<span class='errtext'>下载失败：" + esc(err||"未知错误") + "</span>";
    toast("下载失败：" + (err||"未知错误"));
  }
}

/* ---------- 常见问题 ---------- */
function showHelp(){
  alert(
    "常见问题\n" +
    "────────────────────────\n" +
    "1) 点「载入凭证」说凭证柜是空的？\n" +
    "   说明你电脑上的部署包还没跑，或者跑了超过 10 分钟。\n" +
    "   重新双击一次「一键部署」即可。\n\n" +
    "2) 部署窗口提示读取失败？\n" +
    "   浏览器开着会锁住凭证文件。把 Edge / Chrome 所有窗口全部关掉\n" +
    "   （不是最小化），回到那个窗口按回车重试。\n\n" +
    "3) 双击没反应 / 一闪而过？\n" +
    "   多半是没装 Python。到 python.org 装 3.9 以上版本，\n" +
    "   安装时务必勾选 Add Python to PATH，然后再双击一次。\n\n" +
    "4) 关掉网页会不会中断？\n" +
    "   不会。修改是在你自己电脑上跑的，网页只是看进度。\n\n" +
    "5) 每天能改多少？\n" +
    "   默认 120 篇/天，到量自动停止，第二天自动继续。\n" +
    "   在任务卡片里可以调，调完重新下载一次部署包即可生效。\n\n" +
    "6) 改错了能还原吗？\n" +
    "   每篇改动前的原文都自动备份在你电脑上，可一键还原。"
  );
}

/* ---------- 新手引导 ---------- */
const TOUR_STEPS = [
  {sel:"#btnBundle1", t:"第 1 步：下载部署包",
   d:"先点这个按钮下载。解压后双击里面的「一键部署」，它会自动读到你浏览器里的知乎登录 —— 不用粘贴、不用按 F12。"},
  {sel:"#btnLoadCred", t:"第 1 步：载入凭证",
   d:"部署包跑起来之后，回到这里点一下。凭证会自动填好，并立刻帮你把名下的文章检索出来。"},
  {sel:"#tabs", t:"第 2 步：挑分类",
   d:"在这里切换 文章 / 想法 / 回答。能加品牌词的只有「文章」。"},
  {sel:"#tbody", t:"打钩选文章",
   d:"标题左边的方框就是开关。也可以用上面的「全选」「选前 20」快速选。"},
  {sel:"#btnCreate", t:"第 2 步：开始修改",
   d:"点这一个按钮，系统会逐篇判断加在哪里并生成任务。"},
  {sel:"#taskCard", t:"第 3 步：在你自己电脑上执行",
   d:"修改由你电脑上的执行器完成（走你本人的网络身份）。进度会实时显示在这里。"},
  {sel:"#perDay", t:"每天改多少",
   d:"默认每天最多 120 篇，到量自动停止，保护账号。可以改，改完重新下载一次部署包。"},
  {sel:"#ovCard", t:"第 4 步：查看结果",
   d:"任务开始后，这里会逐篇展示改了什么，并给出正文没有被改动的证据。"}
];
let TOUR_I = -1;

function tourVisible(el){
  if(!el) return false;
  if(el.offsetParent === null && getComputedStyle(el).position !== "fixed") return false;
  const r = el.getBoundingClientRect();
  return r.width > 2 && r.height > 2;
}
function tourEnd(mark){
  const h = document.getElementById("tourHl"); if(h) h.remove();
  const p = document.getElementById("tourTip"); if(p) p.remove();
  TOUR_I = -1;
  if(mark){ try{ localStorage.setItem("qy_tour_done","1"); }catch(e){} }
}
function tourSkipHidden(){
  // 跳过当前不可见的步骤（隐藏卡片里的元素会让聚光灯错位到左上角）
  let guard = 0;
  while(TOUR_I >= 0 && TOUR_I < TOUR_STEPS.length && guard++ < TOUR_STEPS.length + 2){
    const el = document.querySelector(TOUR_STEPS[TOUR_I].sel);
    if(tourVisible(el)) return true;
    TOUR_I++;
  }
  return false;
}
function tourShow(i){
  TOUR_I = i;
  if(!tourSkipHidden()){ tourEnd(true); return; }
  const st = TOUR_STEPS[TOUR_I];
  const el = document.querySelector(st.sel);
  if(el.scrollIntoView) el.scrollIntoView({block:"center",behavior:"smooth"});
  setTimeout(function(){
    if(!tourVisible(el)) { tourSkipHidden(); return; }
    let hl = document.getElementById("tourHl");
    let tip = document.getElementById("tourTip");
    if(!hl){
      hl = document.createElement("div"); hl.id = "tourHl"; hl.className = "tour-hl";
      document.body.appendChild(hl);
      tip = document.createElement("div"); tip.id = "tourTip"; tip.className = "tour-tip";
      document.body.appendChild(tip);
    }
    const pad = 8, r = el.getBoundingClientRect();
    hl.style.left = (r.left-pad)+"px"; hl.style.top = (r.top-pad)+"px";
    hl.style.width = (r.width+pad*2)+"px"; hl.style.height = (r.height+pad*2)+"px";
    const first = TOUR_I===0, last = TOUR_I===TOUR_STEPS.length-1;
    tip.innerHTML = '<b><span class="t-n">'+(TOUR_I+1)+'</span>'+st.t+'</b>'+st.d
      + '<div class="tour-btns">'
      + '<button class="btn-ghost btn-sm" onclick="tourPrev()"'+(first?' disabled style="opacity:.4"':'')+'>上一步</button>'
      + '<button class="btn-primary btn-sm" onclick="tourNext()">'+(last?"完成":"下一步 →")+'</button>'
      + '<button class="tour-skip" onclick="tourEnd(true)">跳过，不再显示</button></div>';
    let tl = (r.left + r.width/2) - 170, tt = r.bottom + 14;
    if(tt + 230 > window.innerHeight) tt = Math.max(14, r.top - 240);
    if(tl < 12) tl = 12;
    if(tl + 352 > window.innerWidth - 12) tl = window.innerWidth - 364;
    tip.style.left = tl+"px"; tip.style.top = tt+"px";
  }, 450);
}
function tourNext(){ tourShow(TOUR_I+1); }
function tourPrev(){ if(TOUR_I>0){ tourShow(TOUR_I-1); } }
function startTour(force){ tourEnd(false); tourShow(0); }
try{
  if(!localStorage.getItem("qy_tour_done")){
    setTimeout(function(){ tourShow(0); }, 1400);
  }
}catch(e){}
</script>
</body>
</html>
"""


def get_page() -> str:
    """返回页面 HTML，并把站点密钥注入到脚本常量（不在静态文件里硬编码）。"""
    import os
    key = os.environ.get("QY_SITE_KEY", "guanjun2026")
    return QY_PAGE_HTML.replace("__QY_SITE_KEY__", key)
