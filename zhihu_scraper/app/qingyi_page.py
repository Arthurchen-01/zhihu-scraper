"""清一新教育 · 标题署名控制台 前端页面。

交互设计：
  第一步  部署包自动读取凭证（零粘贴）→ 只读检索本人资产
  第二步  按分类筛选 + 勾选文章
  第三步  创建任务 → 本地执行器领取 → 实时进度渲染
  第四步  逐篇展开查看修改对照（标题 diff + 正文片段）与正文零修改证据
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
  font-size:14px;line-height:1.6;
}
.wrap{max-width:1160px;margin:0 auto;padding:26px 20px 80px}
header.top{display:flex;align-items:center;gap:14px;margin-bottom:8px;flex-wrap:wrap}
h1{font-size:21px;margin:0;font-weight:700;letter-spacing:-.2px}
.sub{color:var(--text-2);font-size:13px;margin:2px 0 22px}
.badge{
  display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;
  background:#e0f2fe;color:#0369a1;font-size:12px;font-weight:600
}
.card{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px;margin-bottom:16px;box-shadow:var(--shadow)
}
.card h2{font-size:15px;margin:0 0 4px;font-weight:700;display:flex;align-items:center;gap:8px}
.step{
  display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;
  border-radius:50%;background:var(--brand);color:#fff;font-size:12px;font-weight:700;flex:none
}
.hint{color:var(--text-2);font-size:12.5px;margin:6px 0 14px}
label.f{display:block;font-size:12.5px;color:var(--text-2);font-weight:600;margin:0 0 6px}
textarea,input,select{
  width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;
  font-family:inherit;font-size:13px;background:#fff;color:var(--text);outline:none
}
textarea{min-height:96px;resize:vertical;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
textarea:focus,input:focus,select:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(14,165,233,.13)}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}
.row>div{flex:1;min-width:170px}
button{
  border:none;border-radius:10px;padding:10px 18px;font-size:13.5px;font-weight:650;
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
.notice{
  border-radius:12px;padding:13px 15px;font-size:13px;margin:0 0 16px;
  background:#fffbeb;border:1px solid #fde68a;color:#92400e
}
.notice strong{color:#78350f}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
.stat{
  flex:1;min-width:112px;background:var(--panel-2);border-radius:11px;padding:11px 14px;
  border:1px solid var(--line)
}
.stat .n{font-size:21px;font-weight:750;line-height:1.2}
.stat .l{font-size:11.5px;color:var(--text-3);font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.stat.ok .n{color:var(--ok)} .stat.warn .n{color:var(--warn)}
.stat.err .n{color:var(--err)} .stat.brand .n{color:var(--brand-2)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{
  text-align:left;padding:9px 10px;border-bottom:2px solid var(--line);
  font-size:11.5px;color:var(--text-3);text-transform:uppercase;letter-spacing:.5px;font-weight:700
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
  background:#0f172a;color:#cbd5e1;border-radius:11px;padding:13px 15px;max-height:230px;
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
details.os{border:1px solid var(--line);border-radius:11px;padding:0;margin-bottom:10px;overflow:hidden}
details.os>summary{
  padding:12px 15px;cursor:pointer;font-weight:650;font-size:13.5px;background:var(--panel-2);
  list-style:none;display:flex;align-items:center;gap:9px
}
details.os>summary::-webkit-details-marker{display:none}
details.os>summary::before{content:"▸";color:var(--brand);font-size:13px}
details.os[open]>summary::before{content:"▾"}
details.os .body{padding:14px 16px}

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
/* ---- 页首赞助条（小巧，几行） ---- */
.sponsor{
  background:linear-gradient(180deg,#fffbeb 0%,#fffdf6 100%);
  border:1px solid #fde68a;border-radius:10px;
  padding:9px 14px;margin:0 0 14px;
  font-size:12.5px;line-height:1.85;color:var(--text-2)
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
/* 步步教学：聚光灯 + 幕布 */
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
.dcap{display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  background:var(--panel-2);border:1px solid var(--line);border-radius:10px;
  padding:11px 14px;margin:12px 0 4px;font-size:12.5px;color:var(--text-2)}
.dcap strong{color:var(--text)}
.dcap select{width:auto;min-width:112px;padding:6px 9px;font-size:12.5px}
.dcap .meter{margin-left:auto;font-family:ui-monospace,monospace;
  font-size:12px;color:var(--text-2)}
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
  云端负责检索、编排与进度聚合；真正的写入由你自己电脑上的<strong>本地执行器</strong>完成，走你本人的网络身份。
  <a href="/" style="color:var(--brand-2)">← 返回存证系统</a>
  · <a onclick="startTour(true)" style="color:var(--brand-2);cursor:pointer">❓ 新手引导（一步步教）</a>
</div>

<div class="notice">
  <strong>作用范围声明：</strong>每篇文章固定改动 <strong>2 处</strong> ——
  ① <strong>标题</strong>最前面加入品牌词 <code>【清一新教育】</code> 共 1 处；
  ② <strong>正文</strong>中以署名式括注 <code>（清一新教育）</code> 加入品牌词共 1 处。<br>
  正文植入<strong>只做句末括注，不删除、不改写、不替换任何原有文字</strong>，
  并可一键还原为原文；每篇原文均在本机留有备份。
  <strong>除此之外没有任何修改。</strong>
</div>

<!-- ============ STEP 1 ============ -->
<div class="card">
  <h2><span class="step">1</span> 凭证与检索 <span class="chip" id="osChip" style="margin-left:8px">🖥️ 识别设备中…</span></h2>
  <div class="hint"><strong>全自动 · 零粘贴（推荐）：</strong>① 点「⬇️ 下载部署包」→ ② 在你的电脑上双击「<span id="deployTip">一键部署</span>」，它会自动从浏览器读取知乎登录（<strong>不用粘贴、不用 F12</strong>）→ ③ 回到本页点「📥 载入凭证」。检索是<strong>只读</strong>的，不会写入任何内容。</div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 12px">
    <button class="btn-primary" id="btnBundle1" onclick="dlBundle()">⬇️ 下载部署包（自动读登录）</button>
    <button class="btn-ghost" id="btnLoadCred" onclick="doLoadCred()">📥 载入凭证</button>
    <span class="chip mute">凭证暂存 10 分钟，过期可重新部署获取</span>
  </div>
  <div class="row">
    <div style="flex:3;min-width:300px">
      <label class="f">知乎登录凭证（一般无需手动填写，点「📥 载入凭证」自动填好）</label>
      <textarea id="ck" placeholder="点上面「📥 载入凭证」即可自动填入 —— 不需要你粘贴任何东西"></textarea>
    </div>
    <div style="flex:0 0 auto;display:flex;gap:8px">
      <button class="btn-primary" id="btnInspect" onclick="doInspect()">🔍 开始检索我的文章</button>
    </div>
  </div>
  <div id="inspectMsg" class="hint"></div>
  <div class="stats hide" id="stats">
    <div class="stat brand"><div class="n" id="sAll">0</div><div class="l">条目合计</div></div>
    <div class="stat ok"><div class="n" id="sBrand">0</div><div class="l">已含品牌词</div></div>
    <div class="stat warn"><div class="n" id="sPend">0</div><div class="l">待注入</div></div>
    <div class="stat"><div class="n" id="sArt">0</div><div class="l">文章</div></div>
    <div class="stat"><div class="n" id="sPin">0</div><div class="l">想法</div></div>
  </div>
</div>

<!-- ============ STEP 2 ============ -->
<div class="card hide" id="listCard">
  <h2><span class="step">2</span> 勾选要处理的文章</h2>
  <div class="hint"><strong>这一步做两件事：</strong>① 在下面列表里，给想加【清一新教育】的文章<strong>打钩</strong>（点标题左边的方框）；② 点右下角的大按钮「🤖 AI 审核 + 创建修改任务」。想法和回答没有独立标题，改不了；不勾选就什么都不会发生。</div>
  <div class="tabs" id="tabs"></div>
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
      <span>AI 审核植入<em>由 DeepSeek 决定每篇加几处、加在哪里；AI 不可用时自动回退内置规则</em></span>
    </label>
    <span class="chip mute" style="margin-left:auto">每篇合计 2 处</span>
  </div>

  <div class="toolbar">
    <button class="btn-ghost btn-sm" onclick="selAll(true)">全选当前筛选</button>
    <button class="btn-ghost btn-sm" onclick="selAll(false)">取消全选</button>
    <button class="btn-ghost btn-sm" onclick="selFirst(20)">选前 20</button>
    <button class="btn-ghost btn-sm" onclick="selFirst(50)">选前 50</button>
    <span style="margin-left:auto;font-size:13px;color:var(--text-2)">
      已勾选 <strong id="selCount">0</strong> 项
    </span>
    <button class="btn-ghost btn-sm" id="btnScan" onclick="doScanScenes()"
            title="从前往后逐篇检索正文中可植入品牌词的位置（只读，不写入）">
      全面检索可加入场景
    </button>
    <button class="btn-primary" id="btnCreate" onclick="doCreate()">🤖 AI 审核 + 创建修改任务</button>
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
</div>

<!-- ============ STEP 3 ============ -->
<div class="card hide" id="taskCard">
  <h2><span class="step">3</span> 执行</h2>
  <div class="hint">
    任务已生成，等待本地执行器领取。请在<strong>你自己的电脑</strong>上按下方指引启动执行器——
    这样写入行为来自你本人的网络身份，而不是服务器机房 IP。
  </div>

  <div id="execGuide">
    <div class="hint" style="margin-top:0">
      <strong>傻瓜三步：</strong>① 点下面的蓝色按钮下载部署包（自带自动部署器）
      → ② 解压到任意文件夹 → ③ 双击「一键部署」：自动从浏览器读取知乎登录并启动执行器。
      然后回第 1 步点「📥 载入凭证」即可勾选文章。
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0">
      <button class="btn-primary" id="btnBundle" onclick="dlBundle()">⬇️ 一键下载部署包（推荐）</button>
      <span class="chip mute" id="bundleHint">包内自带自动部署器（无凭证时会自动读取浏览器登录）</span>
    </div>
    <details class="os">
      <summary>高级：分开下载 / 手动运行 / 交给 Antigravity</summary>
      <div class="body">
        <div class="hint" style="margin-top:0">
          Windows：把执行器脚本与启动脚本存到同一文件夹 → 双击启动脚本。<br>
          macOS：打开终端 → 切换到脚本所在文件夹 → 执行启动脚本。
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
          <button class="btn-ghost btn-sm" onclick="dl('script')">下载执行器脚本</button>
          <button class="btn-ghost btn-sm" onclick="dl('bat')">下载 Windows 启动脚本</button>
          <button class="btn-ghost btn-sm" onclick="dl('sh')">下载 macOS 启动脚本</button>
          <button class="btn-ghost btn-sm" onclick="copyAg()">复制 Antigravity 指令</button>
        </div>
        <div class="jsbox" id="winCmd"></div>
        <div class="jsbox" id="macCmd"></div>
        <div class="jsbox" id="agPrompt"></div>
      </div>
    </details>
  </div>

  <div class="dcap">
    <strong>每日上限</strong>
    <span>为保护账号，写入按自然日限量；到量后执行器<strong>自动停止</strong>，剩余篇数次日继续。</span>
    <select id="perDay" onchange="savePerDay()">
      <option value="60">60 篇 / 天（最保守）</option>
      <option value="120" selected>120 篇 / 天（推荐）</option>
      <option value="180">180 篇 / 天</option>
      <option value="0">不限（不建议）</option>
    </select>
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
</div>

<!-- ============ STEP 4 ============ -->
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

<script>
const API = "";
const AIP = {};   // AI 审核结果缓存：id -> {title_add, picks, used_ai}
let ITEMS = [], SEL = new Set(), TAB = "article", JOB = null, ES = null;

/* ---------- toast-ish message ---------- */
function msg(el, text, cls){
  const n = document.getElementById(el);
  n.textContent = text || "";
  n.style.color = cls === "err" ? "var(--err)" : cls === "ok" ? "var(--ok)" : "var(--text-2)";
}

/* ---------- v4：设备识别 + 凭证柜一键载入 ---------- */
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
  const os = detectOS();
  const el = document.getElementById("osChip");
  if(el) el.textContent = "🖥️ 已识别你的设备：" + os;
  const tip = document.getElementById("deployTip");
  if(tip){
    tip.textContent = os === "Windows" ? "一键部署-Windows.bat"
                    : os === "macOS" ? "一键部署-Mac.command"
                    : "一键部署（见包内使用说明）";
  }
}
async function doLoadCred(){
  const b = document.getElementById("btnLoadCred");
  b.disabled = true; b.innerHTML = '<span class="spin"></span> 载入中…';
  msg("inspectMsg","正在获取自动读取的凭证（10 分钟内有效）…");
  try{
    const r = await fetch(API+"/api/qy/credential-latest",
                          {headers:{"X-API-Key":"guanjun2026"}});
    const j = await r.json();
    if(!r.ok || !j.ok){ throw new Error(j.note || j.detail || "凭证柜为空"); }
    document.getElementById("ck").value = j.cookie;
    msg("inspectMsg","✅ 凭证已载入（来源：" + (j.note || "本机浏览器") + "，" + j.age + " 秒前获取）—— 正在自动检索…");
    b.disabled = false; b.innerHTML = "📥 载入凭证";
    await doInspect();
  }catch(e){
    msg("inspectMsg", "暂时没有可载入的凭证：" + e.message +
        "。请先在电脑上运行部署包（第 1 步蓝色按钮），或稍后再试。", "err");
    b.disabled = false; b.innerHTML = "📥 载入凭证";
  }
}
setOsChip();

/* ---------- STEP 1 ---------- */
async function doInspect(){
  const ck = document.getElementById("ck").value.trim();
  if(!ck){ msg("inspectMsg","请先粘贴知乎凭证","err"); return; }
  const b = document.getElementById("btnInspect");
  b.disabled = true; b.innerHTML = '<span class="spin"></span> 检索中…';
  msg("inspectMsg","正在只读检索你名下的内容…");
  try{
    const r = await fetch(API+"/api/qy/inspect",{
      method:"POST", headers:{"Content-Type":"application/json"},
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
    msg("inspectMsg", `已识别账号：${a.name||"-"}（${a.url_token||"-"}）`, "ok");
  }catch(e){
    msg("inspectMsg","检索失败："+e.message,"err");
  }finally{
    b.disabled = false; b.textContent = "检索我的内容";
  }
}

function renderStats(st, total){
  document.getElementById("stats").classList.remove("hide");
  document.getElementById("sAll").textContent  = total;
  document.getElementById("sBrand").textContent= (st.articles.branded||0)+(st.pins.branded||0)+(st.answers.branded||0);
  document.getElementById("sPend").textContent = (st.articles.pending||0);
  document.getElementById("sArt").textContent  = st.articles.total||0;
  document.getElementById("sPin").textContent  = st.pins.total||0;
}

/* ---------- STEP 2 ---------- */
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

/* ---------- 全面检索可加入场景（只读，逐条交互式渲染） ---------- */
async function doScanScenes(){
  const ck = document.getElementById("ck").value.trim();
  if(!ck){ alert("请先粘贴知乎登录凭证并检索"); return; }
  const picked = ITEMS.filter(i => SEL.has(i.id) && i.editable && i.type==="article");
  if(picked.length===0){ alert("请先勾选要检索的文章"); return; }

  const box = document.getElementById("scanBox");
  const btn = document.getElementById("btnScan");
  btn.disabled = true;
  box.classList.remove("hide");
  box.innerHTML = '<div class="scanhd">正在从前往后逐篇检索… <span id="scanPct">0%</span></div>'
                + '<div class="pbar" style="margin:8px 0"><i id="scanBar" style="width:0%"></i></div>'
                + '<div id="scanList"></div>';

  const list = document.getElementById("scanList");
  let hitN = 0, doneN = 0;
  for(const it of picked){
    const row = document.createElement("div");
    row.className = "scanrow";
    row.innerHTML = '<span class="spin"></span> <b>检索中</b> · ' + esc(it.title.slice(0,44));
    list.appendChild(row);

    let r = null;
    try{
      r = await fetch(API+"/api/qy/scan-scenes",{
        method:"POST", headers:{"Content-Type":"application/json"},
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
    row.scrollIntoView({block:"nearest",behavior:"smooth"});
  }

  const hd = box.querySelector(".scanhd");
  if(hd) hd.innerHTML = '检索完成：共 ' + picked.length + ' 篇，其中 '
                      + hitN + ' 篇可加入 1 处正文署名。<b>本次为只读预览，尚未写入任何内容。</b>';
  btn.disabled = false;
}


/* ---------- STEP 3：AI 审核 + 创建任务（逐篇进度渲染） ---------- */
async function doCreate(){
  if(SEL.size===0){ alert("还没有勾选任何文章：请在下方列表里，给想加品牌词的文章打钩（标题左侧的方框），再点本按钮。"); return; }
  const picked = ITEMS.filter(i => SEL.has(i.id) && i.editable);
  if(picked.length===0){ alert("你勾选的都是「想法 / 回答」——它们没有独立标题，改不了。请勾选「文章」类型的条目。"); return; }
  const b = document.getElementById("btnCreate");
  const bTxt = b.innerHTML;
  b.disabled = true;
  const plans = {};
  const useAI = document.getElementById("fAI").checked;
  const wantBody = document.getElementById("fBody").checked;
  try{
    if(useAI){
      const box = document.getElementById("scanBox");
      box.classList.remove("hide");
      box.innerHTML = '<div class="scanhd">🤖 AI 审核中：逐篇决定加几处、加在哪里… <span id="scanPct">0%</span></div>'
        + '<div class="pbar" style="margin:8px 0"><i id="scanBar" style="width:0%"></i></div>'
        + '<div id="scanList"></div>';
      box.scrollIntoView({block:"nearest",behavior:"smooth"});
      const list = document.getElementById("scanList");
      let doneN = 0;
      for(const it of picked){
        const row = document.createElement("div");
        row.className = "scanrow"; row.id = "ar-"+it.id;
        row.innerHTML = '<span class="spin"></span><b>AI 审核中</b> · ' + esc(it.title.slice(0,40));
        list.appendChild(row);
        row.scrollIntoView({block:"nearest",behavior:"smooth"});
        const tr = document.getElementById("row-"+it.id);
        if(tr) tr.classList.add("doing");
        let r = null;
        try{
          r = await fetch(API+"/api/qy/ai-review-single",{
            method:"POST", headers:{"Content-Type":"application/json"},
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
          row2.innerHTML = '<span class="dot err"></span><b>审核失败</b> · ' + esc(it.title.slice(0,40))
            + '<div class="scand">'+esc((r&&r.detail)||"网络异常；该篇将按内置规则处理")+'</div>';
          continue;
        }
        plans[it.id] = {title_add:r.title_add, picks:r.picks, used_ai:r.used_ai};
        AIP[it.id] = r;
        const n = (r.picks||[]).length;
        const tag = r.used_ai ? '<span class="revtag ok">AI 已审核</span>'
                              : '<span class="revtag fall">规则兜底</span>';
        row2.className = "scanrow okr";
        row2.innerHTML = '<span class="dot ok"></span><b>方案：标题'+(r.title_add?"加 1 处":"不加")
          +' · 正文加 '+n+' 处</b>'+tag+' · '+esc(it.title.slice(0,34))
          + '<div class="scand">'
          + (esc((r.picks||[]).map(function(p){return "「"+(p.reason||"")+"」";}).join("；")) || "本文正文无需植入")
          + '</div>';
        renderTable();
      }
      const hd = box.querySelector(".scanhd");
      if(hd) hd.innerHTML = "AI 审核完成：共 " + picked.length + " 篇。正在生成修改任务…";
    }
    const r2 = await fetch(API+"/api/qy/jobs",{
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        items: picked.map(i=>({id:i.id,type:i.type,kind_label:i.kind_label,
                               title:i.title,url:i.url,excerpt:i.excerpt,
                               ai_plan:plans[i.id]||null})),
        mode:"local",
        title:  document.getElementById("fTitle").checked,
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
    document.getElementById("taskCard").scrollIntoView({behavior:"smooth"});
    loadLaunchers();
    openStream(JOB.job_id);
  }catch(e){
    alert("创建任务失败："+e.message);
  }finally{
    b.disabled = false; b.innerHTML = bTxt;
  }
}

function dl(kind){
  const w = window.open("", "_blank");
  fetch(API+"/api/qy/executor/launcher").then(r=>r.json()).then(j=>{
    if(kind==="script"){
      w.location = API+"/api/qy/executor/script"; return;
    }
    const os = kind==="bat" ? j.platforms.windows : j.platforms.macos;
    const blob = new Blob([os.launcher], {type:"text/plain;charset=utf-8"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = os.launcher_file;
    a.click();
    if(w) w.close();
  });
}

async function loadLaunchers(){
  try{
    const r = await fetch(API+"/api/qy/executor/launcher");
    const j = await r.json();
    document.getElementById("winCmd").textContent = j.platforms.windows.one_liner;
    document.getElementById("macCmd").textContent = j.platforms.macos.one_liner;
    document.getElementById("agPrompt").textContent = j.antigravity_prompt;
  }catch(e){}
}
function copyAg(){
  const t = document.getElementById("agPrompt").textContent;
  navigator.clipboard.writeText(t).then(()=>alert("已复制，可直接粘贴给 Antigravity"));
}

/* ---------- live progress ---------- */
function openStream(jobId){
  if(ES) ES.close();
  ES = new EventSource(API+"/api/qy/jobs/"+jobId+"/stream");
  ES.onmessage = ev => {
    try{ renderJob(JSON.parse(ev.data)); }catch(e){}
  };
  ES.addEventListener("end", ()=>{ if(ES) ES.close(); ES=null; });
  ES.onerror = ()=>{ /* auto reconnect by browser */ };
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
  const [lbl,cls] = map[job.status]||["—","mute"];
  const el = document.getElementById("jobStatus");
  el.textContent = lbl + (job.status==="running"?" "+pct+"%":"");
  el.className = "chip "+cls + (job.status==="running"?" pulse":"");

  const w = job.worker||{};
  if(w.id) document.getElementById("jobId").textContent =
    "任务编号 "+job.job_id+" · 执行器 "+w.id;

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
    const map2 = {done:["已注入","ok"],skipped:["已含/跳过","ok"],
      failed:["失败","err"],saved_not_published:["待发布","warn"],
      unsupported:["不可改","mute"],pending:["待处理","warn"]};
    const [l2,c2] = map2[it.status]||["—","mute"];
    if(cell.querySelector(".chip").className.indexOf(c2)<0){
      cell.innerHTML = `<span class="chip ${c2}">${l2}</span>`;
      if(it.status==="done"){ row.classList.add("rowdone"); }
    }
  });
}

async function resetJob(){ if(!JOB) return; await fetch(API+"/api/qy/jobs/"+JOB.job_id+"/reset",{method:"POST"}); }
async function cancelJob(){ if(!JOB||!confirm("确定取消该任务？")) return;
  await fetch(API+"/api/qy/jobs/"+JOB.job_id+"/cancel",{method:"POST"}); }

/* ---------- STEP 4 ---------- */
async function showOverview(){
  if(!JOB) return;
  const r = await fetch(API+"/api/qy/jobs/"+JOB.job_id);
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

  changed.forEach((it,idx)=>{
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
  c.scrollIntoView({behavior:"smooth"});
}
/* ---------- 每日上限 ---------- */

const PERDAY_KEY = "qy.perDay";
const DAILY_KEY  = "qy.dailyUsed";

function loadPerDay(){
  const v = localStorage.getItem(PERDAY_KEY) || "120";
  const sel = document.getElementById("perDay");
  if (sel) sel.value = v;
  refreshDailyMeter();
  return parseInt(v, 10);
}

function savePerDay(){
  const sel = document.getElementById("perDay");
  if (!sel) return;
  localStorage.setItem(PERDAY_KEY, sel.value);
  toast("每日上限已设为 " + (sel.value === "0" ? "不限（不建议）" : sel.value + " 篇/天"));
  refreshDailyMeter();
}

function dailyUsed(){
  const raw = localStorage.getItem(DAILY_KEY);
  if (!raw) return {day:"",used:0};
  try{
    const o = JSON.parse(raw);
    const today = new Date().toISOString().slice(0,10);
    if (o.day !== today) return {day:today,used:0};
    return o;
  }catch(e){ return {day:"",used:0}; }
}

function setDailyUsed(n){
  localStorage.setItem(DAILY_KEY, JSON.stringify({
    day: new Date().toISOString().slice(0,10), used: n
  }));
  refreshDailyMeter();
}

function refreshDailyMeter(){
  const el = document.getElementById("dcapMeter");
  if (!el) return;
  const sel = document.getElementById("perDay");
  const lim = sel ? parseInt(sel.value,10) : 120;
  const u = dailyUsed().used;
  el.textContent = "今日 " + u + " / " + (lim === 0 ? "∞" : lim);
  if (lim > 0 && u >= lim){
    el.style.color = "var(--err)";
    el.textContent += " · 已达上限，执行器将自动停止";
  }else{
    el.style.color = "";
  }
}

loadPerDay();


/* ---------- 一键执行器包 ---------- */
async function dlBundle(){
  const ck = document.getElementById("ck").value.trim();
  // v4：凭证可选 —— 包内自带自动部署器，会读取本机浏览器登录
  const b = document.getElementById("btnBundle");
  const t = b.innerHTML;
  b.disabled = true; b.innerHTML = '<span class="spin"></span> 正在打包…';
  try{
    const r = await fetch(API+"/api/qy/executor/bundle",{
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({cookie:ck})
    });
    if(!r.ok){ const j = await r.json().catch(()=>({})); throw new Error(j.detail||"打包失败"); }
    const bl = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(bl);
    a.download = "qingyi_executor.zip";
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href), 5000);
    document.getElementById("bundleHint").textContent = "已下载：解压后双击「一键部署」，它会自动读取你的知乎登录";
  }catch(e){
    alert("下载失败："+e.message);
  }finally{
    b.disabled = false; b.innerHTML = t;
  }
}

/* ---------- 步步教学：聚光灯 + 幕布 ---------- */
const TOUR_STEPS = [
  {sel:"#btnLoadCred", t:"第 1 步：让系统认识你（全自动）",
   d:"先点「⬇️ 下载部署包」，在你的电脑上双击「一键部署」—— 它会自动读取你浏览器的知乎登录（零粘贴、零 F12）。然后回到这里点「📥 载入凭证」。"},
  {sel:"#btnInspect", t:"点这里开始检索",
   d:"系统会只读列出你名下的文章 / 想法 / 回答，不会写入任何内容。"},
  {sel:"#tabs", t:"第 2 步：挑文章",
   d:"用这里的标签切换 文章 / 想法 / 回答。能加品牌词的只有「文章」。"},
  {sel:"#tbody", t:"给想改的文章打钩",
   d:"标题左边的方框就是开关；也可以用上方「全选」「选前 20」快捷选择。"},
  {sel:"#btnCreate", t:"第 3 步：AI 审核 + 创建任务",
   d:"点这一下，AI（DeepSeek）会逐篇阅读你的文章，决定每篇加几处、加在哪里，然后生成修改任务。"},
  {sel:"#btnBundle", t:"第 4 步：下载部署包",
   d:"包内自带自动部署器。解压后双击「一键部署」，修改就在你自己的电脑上开始（写入走你本人的网络身份）。"},
  {sel:"#perDay", t:"每日上限",
   d:"默认每天最多 120 篇，到量自动停止，保护账号。可以改。"}
];
let TOUR_I = -1;
function tourEnd(mark){
  const h = document.getElementById("tourHl"); if(h) h.remove();
  const p = document.getElementById("tourTip"); if(p) p.remove();
  TOUR_I = -1;
  if(mark){ try{ localStorage.setItem("qy_tour_done","1"); }catch(e){} }
}
function tourShow(i){
  const st = TOUR_STEPS[i];
  if(!st){ tourEnd(true); return; }
  const el = document.querySelector(st.sel);
  if(!el){ tourEnd(false); return; }
  el.scrollIntoView({block:"center",behavior:"smooth"});
  setTimeout(function(){
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
    const first = i===0, last = i===TOUR_STEPS.length-1;
    tip.innerHTML = '<b><span class="t-n">'+(i+1)+'</span>'+st.t+'</b>'+st.d
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
function tourNext(){ TOUR_I++; tourShow(TOUR_I); }
function tourPrev(){ if(TOUR_I>0){ TOUR_I--; tourShow(TOUR_I); } }
function startTour(force){ tourEnd(false); TOUR_I = 0; tourShow(0); }
try{
  if(!localStorage.getItem("qy_tour_done")){
    setTimeout(function(){ TOUR_I = 0; tourShow(0); }, 1400);
  }
}catch(e){}
</script>
</body>
</html>
"""


def get_page() -> str:
    return QY_PAGE_HTML
