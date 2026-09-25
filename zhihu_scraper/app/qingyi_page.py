"""清一新教育 · 文章修改工作台 前端页面（v5）。

交互设计（每一步只做一件事）：
  第 1 步  下载一键程序 → 双击 → 回来点「载入凭证」→ 自动检索（零粘贴、零 F12）
         （可选加速：装浏览器扩展，之后连「关浏览器」都不需要）
  第 2 步  打钩挑文章 → 点一个大按钮
  第 3 步  把改动推到你的知乎（双击一键程序）→ 进度实时回传
  第 4 步  执行进度与云端复核 → 逐篇对照（品牌词模式另附正文指纹比对）

v5 相对 v4 的改动：
  * 所有请求统一带上站点密钥 → 直接打开/收藏本页也能用（不再 401 天书）
  * 「每日上限」真正下发到执行器（随包 perday.txt），并显示执行器实际生效值
  * 「今日已写入」改为读取服务端真实计数（原来是永不更新的假数字）
  * 修 savePerDay 调用未定义 toast 的 ReferenceError
  * 修检索完成后按钮文案被改写、下载包没有任何反馈
  * 部署指引与手动下载从页面主体收进「高级」，消除重复与自相矛盾
  * 用户可见文案去掉「傻瓜」二字；报错文案去掉「粘贴」措辞

v5 追加（云端预算内容 + 云端独立复核）：
  * 任务建好后云端立刻算出每篇「最终标题 + 最终正文」并缓存（POST /prepare）
  * 本地执行器只按 /agent/payload 取回原样上传，不再自行判断怎么改
  * 写入完成后云端回读线上文章逐篇复核（POST /verify），页面显示 ✓/✗ 与原因
  * 「发给助手的指令」一键复制（GET /agent/brief）
  * 刷新页面不再丢失进行中的任务（localStorage 记住 job_id）
  * 凭证柜有效期 10 分钟 → 6 小时
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
.agentbox{margin:14px 0 6px;padding:16px 16px 14px;border:1px solid var(--line);border-radius:var(--radius);background:var(--panel-2)}
.agenthd{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.agenthd strong{font-size:14.5px;color:var(--text)}
.vrow{display:flex;gap:10px;align-items:flex-start;padding:10px 0;border-top:1px dashed var(--line);font-size:12.8px;color:var(--text-2)}
.vrow .vt{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.vrow .vr{color:var(--text-3);font-size:12px;margin-top:3px;white-space:normal}
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
<style>
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
</style>
</head>
<body>
<div class="wrap">

<!-- ============ 赞助与联系（页首 · 小巧） ============ -->
<div class="sponsor">
  🤝 <b>清一新教育-冠军一班-谢迪安友情资助</b>
  <span class="tip">｜本工具免费提供，用于让有价值的教学内容更容易被检索到</span><br>
  📞 支持本计划 / 企业 AI 供应对接：<b>谢迪安 / 陈冠宇</b>
  <!-- 待补：微信号。填好后删掉本注释，改成 · 微信号：<span class="ph">你的号码</span> -->
  <span class="tip">（本页署名与联系方式仅供联系使用，<b>不会写入任何文章正文</b>）</span>
</div>

<header class="top">
  <h1>清一新教育文章修改工作台</h1>
  <span class="badge">默认：替换正文 / 可选：只加品牌词</span>
</header>
<div class="sub">
  云端负责检索与进度，真正的写入在你自己电脑上完成（走你本人的网络身份）。
  <a href="/" style="color:var(--brand-2)">← 返回存证系统</a>
  · <a href="javascript:void(0)" role="button" tabindex="0" onclick="startTour(true)" style="color:var(--brand-2);cursor:pointer">❓ 新手引导</a>
  · <a href="javascript:void(0)" role="button" tabindex="0" onclick="showHelp()" style="color:var(--brand-2);cursor:pointer">❔ 常见问题</a>
</div>

<details class="adv" style="margin-bottom:16px">
  <summary>本工具会改动什么？（点开看完整声明）</summary>
  <div class="body">
    第 2 步的「文章修改与替换内容设置」里有两种模式，<strong>默认是第 ① 种</strong>：<br>
    <strong>① 替换正文模式（默认）</strong> —— 把选中的文章<strong>标题与正文整篇替换</strong>为
    一篇 1,000~2,500 字的正规长文（中国法律法规条文 / 国学名篇，按文章 ID 确定性分配；
    可在设置里切换文库，或改成自填标题与正文）。<strong>原有正文会被整篇替换掉，不是加字。</strong><br>
    <strong>② 品牌词模式</strong> —— <strong>标题</strong>最前面加入 <code>【清一新教育】</code> 1 处（固定）；
    <strong>正文</strong>只在句末做署名式括注 <code>（清一新教育）</code>（1~5 处自选，默认 1 处）。
    此模式<strong>不删除、不改写、不替换任何原有文字</strong>。<br>
    <strong>两种模式在改动前都会把你电脑上的原文备份下来，可一键还原。</strong>
    除此之外不会改动专栏归属、话题、评论设置、图片与发布状态。
  </div>
</details>

<!-- ============ 第 1 步 ============ -->
<div class="card">
  <h2><span class="step">1</span> 让系统认识你 <span class="chip" id="osChip" style="margin-left:8px">🖥️ 识别设备中…</span></h2>
  <div class="hint">下面两步，不用粘贴、不用按 F12。做完这一步，第 2 步的列表就出来了。</div>

  <ol class="mini">
    <li>
      <div class="ttl">下载「一键程序」→ 双击 → 完</div>
      <div class="tiptext">就一个文件：不用解压、不用打开终端、不用安装任何东西。它会自动读到你浏览器里的知乎登录。</div>
      <div class="act">
        <button class="btn-primary" id="btnExe" onclick="dlExe('btnExe')">⬇️ 下载 Windows 一键程序</button>
        <span class="tiptext" id="hint1">下好直接双击就能跑（首次运行若被 Windows 拦一下，点「更多信息」→「仍要运行」）</span>
      </div>
      <div class="act" style="margin-top:8px">
        <button class="btn-primary" id="btnMacArm" onclick="dlMac('arm','btnMacArm')">⬇️ 下载 Mac 版（Apple 芯片）</button>
        <button class="btn-ghost" id="btnMacIntel" onclick="dlMac('intel','btnMacIntel')">⬇️ 下载 Mac 版（Intel）</button>
      </div>
      <div class="tiptext" style="margin-top:6px">
        Mac 同样双击即用，不用装 Python、不用开终端。按芯片选一个（<b>2020 年后的 Mac 基本都是 Apple 芯片</b>，
        不确定就点左上角苹果标 →「关于本机」看「芯片」那一行）。首次打开要在 App 上
        <b>点右键 →「打开」</b>（内部工具未做苹果公证，直接双击会被系统拦下）；
        首次读取登录会弹一次钥匙串授权，点「始终允许」即可。
      </div>
      <div class="act" style="margin-top:8px">
        <button class="btn-primary" id="btnClient" onclick="dlClient('btnClient')">⬇️ 下载用户端（逐篇确认版 · 推荐）</button>
      </div>
      <div class="tiptext" style="margin-top:6px">
        推荐用这个：解压后双击「一键启动-用户端」，会自动打开一个<b>本地控制台</b>。
        云端只负责算好每篇的建议稿，<b>每一篇文章在提交到知乎之前，都要你在控制台上勾选确认</b>
        —— 没勾选就不会写。一次最多同时确认并修改 <b>5 篇</b>，不用一篇一篇等。
        想用老的一键程序（全自动、事后看结果）就点上面那排按钮。
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
      </details>
      <details class="adv" style="margin-top:8px">
        <summary>其他方式：交给 AI 助手 / 仍想用部署包</summary>
        <div class="body">
          <div class="act">
            <button class="btn-ghost btn-sm" id="btnBundle1" onclick="dlBundle('btnBundle1')">⬇️ 下载部署包（zip）</button>
            <span class="tiptext">需要解压，再双击里面的「<span id="deployTip2">一键部署</span>」。本机需要 Python 3.9+，是一键程序跑不起来时的兜底路径。</span>
          </div>
          <div class="tiptext" style="margin-top:8px">
            交给 AI 助手：把 <a href="https://github.com/Arthurchen-01/zh-editor" target="_blank">github.com/Arthurchen-01/zh-editor</a> 发给他，让他照仓库里的 AGENTS.md 执行即可。
          </div>
        </div>
      </details>
    </li>
    <li>
      <div class="ttl">回到这里，点一下「载入凭证」</div>
      <div class="tiptext">凭证保留 6 小时，过期重新双击一次部署包就行。之后每篇文章改什么由云端统一算好，你电脑上只负责提交。</div>
      <div class="act">
        <button class="btn-primary" id="btnLoadCred" onclick="doLoadCred()">📥 载入凭证</button>
        <span class="tiptext" id="credState">还没有载入</span>
      </div>
    </li>
  </ol>

  <div id="inspectMsg" class="hint" style="margin-top:10px"></div>

  <details class="adv" open>
    <summary>🔑 手动填写知乎登录凭证 (Cookie) / 上传云端 / 重新检索（无需关闭浏览器）</summary>
    <div class="body">
      <label class="f" for="ck">知乎登录凭证（含 <code>z_c0=</code>；可直接手动粘贴，无需关闭 Edge/Chrome 浏览器）</label>
      <textarea id="ck" placeholder="在此处直接粘贴知乎 Cookie（包含 z_c0=...），或点上方「📥 载入凭证」自动填入"></textarea>

      <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        <button class="btn-primary" id="btnUploadCred" onclick="doUploadCred()">☁️ 保存并上传凭证到云端</button>
        <button class="btn-ghost btn-sm" id="btnPasteCred" onclick="doPasteCred()">📋 从剪贴板粘贴</button>
        <button class="btn-primary btn-sm" id="btnInspect" onclick="doInspect()" style="background:#0284c7;">🔍 立即检索我的知乎内容</button>
      </div>
      <div class="hint" id="uploadState" style="margin-top:8px">
        把凭证粘贴进上面的框 → 点「☁️ 保存并上传凭证到云端」或「🔍 立即检索我的知乎内容」。上传之后，本地客户端与一键部署包可直接拉取使用，无需关闭浏览器。
      </div>
      <div class="hint" style="margin-top:4px">检索是只读的，不会写入任何内容。</div>
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
  <h2><span class="step">2</span> 选择修改内容方案（四书五经 / 法律条文 / 自定义）并打钩挑文章</h2>
  <div class="hint">
    可选择<strong>《大学》《中庸》《论语》《孟子》等四书五经</strong>、<strong>《宪法》《民法典》等国家现行法律条文</strong>，或<strong>直接自定义填写标题与正文</strong>。<br>
    点完之后，<strong>云端会先把每篇文章的最终标题和正文算好</strong>（只读，不会改动任何内容），之后可在本地用户端预览确认并提交。
  </div>
  <div class="tabs" id="tabs"></div>

  <!-- 文章修改与替换内容设置 -->
  <div style="background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:14px 0 16px;">
    <div style="font-weight:700;font-size:14.5px;margin-bottom:10px;display:flex;align-items:center;gap:8px;">
      <span>⚙️ 文章修改与替换内容设置</span>
      <span style="font-size:12px;color:var(--text-3);font-weight:normal">（支持四书五经、法律条文、自定义标题与正文，或品牌词模式）</span>
    </div>
    
    <div style="display:flex;flex-direction:column;gap:12px;">
      <!-- 模式单选 -->
      <div style="display:flex;gap:24px;flex-wrap:wrap;">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:600;">
          <input type="radio" name="actionMode" id="modeReplace" value="replace_content" checked onchange="onModeChange()">
          <span>📜 替换正文模式（四书五经 / 法律条文 / 自定义内容 · 默认）</span>
        </label>
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;color:var(--text-2);">
          <input type="radio" name="actionMode" id="modeBrand" value="brand_signature" onchange="onModeChange()">
          <span>🏷️ 品牌词模式（标题前置【清一新教育】+ 正文句末括注）</span>
        </label>
      </div>

      <!-- 预设选择器 (当为 replace_content 时显示) -->
      <div id="replaceContentOptions" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 14px;">
        <span style="font-size:13.5px;font-weight:600;">选择替换文库预设：</span>
        <select id="essayPreset" onchange="onPresetChange()" style="padding:6px 12px;border-radius:6px;border:1px solid var(--line);font-size:13.5px;background:#fff;font-weight:500;max-width:100%;">
          <optgroup label="🏛️ 分类自动轮换方案">
            <option value="classics" selected>📚 四书五经与国学经典全库轮换（《大学》《中庸》《论语》《孟子》《诗经》等 12 篇）</option>
            <option value="sishu">📖 四书经典专项轮换（《大学》《中庸》《论语》《孟子》）</option>
            <option value="wujing">📜 五经与国学名篇轮换（《诗经》《尚书》《礼记》《周易》《春秋左传》等）</option>
            <option value="law">⚖️ 中国现行法律条文轮换（《宪法》《民法典》《爱国主义教育法》《义务教育法》等 8 部）</option>
            <option value="random_all">🏛️ 法律法规 + 四书五经混合轮换（全库 20 篇）</option>
          </optgroup>
          <optgroup label="📚 指定单篇 · 四书五经与国学经典">
            <option value="daxue">📘 《礼记·大学》—— 明明德、亲民、止于至善与八条目研读</option>
            <option value="zhongyong">📘 《礼记·中庸》—— 诚者天之道、博学审问慎思明辨笃行研读</option>
            <option value="lunyu">📘 《论语》—— 为学修身与君子人格经典章句导读</option>
            <option value="mengzi">📘 《孟子》—— 仁义礼智四端与浩然之气经典选读</option>
            <option value="shijing">📗 《诗经》—— 风雅颂经典名篇与温柔敦厚诗教传统研读</option>
            <option value="shangshu">📗 《尚书》—— 敬德保民、惟精惟一与洪范九畴政道文献研读</option>
            <option value="xueji">📗 《礼记·学记》—— 教学相长、豫时孙摩与中国古代教育哲学考论</option>
            <option value="ruxing">📗 《礼记·儒行》—— 儒者风骨、自立自强与刚毅特立人格精神考述</option>
            <option value="zhouyi">📗 《周易》—— 自强不息、厚德载物与君子修省之道研读</option>
            <option value="chunqiu">📗 《春秋左传》—— 立德立功立言三不朽与居安思危历史镜鉴</option>
            <option value="quanxue">📙 《荀子·劝学》—— 积善成德、锲而不舍与终身治学方法论</option>
            <option value="shishuo">📙 韩愈《师说》—— 传道受业解惑与尊师重道治学传统探微</option>
          </optgroup>
          <optgroup label="⚖️ 指定单部 · 国家现行法律条文">
            <option value="law_xianfa">⚖️ 《中华人民共和国宪法》公民基本权利与义务条文研读</option>
            <option value="law_minfa">⚖️ 《中华人民共和国民法典》民事权利能力与诚实信用原则条文导读</option>
            <option value="law_aiguo">⚖️ 《中华人民共和国爱国主义教育法》核心条文与文化传承规范研读</option>
            <option value="law_jiaoyu">⚖️ 《中华人民共和国义务教育法》与素质教育法定职责条文释义</option>
            <option value="law_weichengnian">⚖️ 《中华人民共和国未成年人保护法》六大保护体系条文研读</option>
            <option value="law_kexue">⚖️ 《中华人民共和国科学技术进步法》基础研究与青年科技人才培养条文导读</option>
            <option value="law_zhuzuoquan">⚖️ 《中华人民共和国著作权法》作品权利保护与合理使用制度条文研读</option>
            <option value="law_jiatingjiaoyu">⚖️ 《中华人民共和国家庭教育促进法》立德树人与家庭责任条文导读</option>
          </optgroup>
          <optgroup label="✍️ 自定义修改内容">
            <option value="custom">✏️ 直接填写自定义标题与正文内容</option>
          </optgroup>
        </select>
        <span id="presetTip" style="font-size:12.5px;color:var(--text-2);">✨ 支持直接指定《大学》等四书五经、国家现行法律条文或自定义文本（安全合规）</span>
      </div>

      <!-- 自定义输入区 (当选择 custom 时展开) -->
      <div id="customContentBox" class="hide" style="background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px 14px;">
        <div style="margin-bottom:8px;">
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:4px;">自定义标题：</label>
          <input type="text" id="customTitle" oninput="renderTable()" style="width:100%;max-width:500px;padding:6px 10px;border-radius:6px;border:1px solid var(--line);" placeholder="例如：《礼记·大学》三纲领八条目研读 / 自定义标题">
        </div>
        <div>
          <label style="display:block;font-size:13px;font-weight:600;margin-bottom:4px;">自定义正文 HTML / 纯文本：</label>
          <textarea id="customContent" rows="5" style="width:100%;padding:8px 10px;border-radius:6px;border:1px solid var(--line);font-family:monospace;font-size:13px;" placeholder="<h2>一、经典原文</h2><p>大学之道，在明明德，在亲民，在止于至善...</p>"></textarea>
        </div>
      </div>
    </div>
  </div>

  <div class="toolbar" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
    <button class="btn-ghost btn-sm" onclick="selAll(true)">全选当前筛选</button>
    <button class="btn-ghost btn-sm" onclick="selAll(false)">取消全选</button>
    <button class="btn-ghost btn-sm" onclick="selFirst(20)">选前 20</button>
    <button class="btn-ghost btn-sm" onclick="selFirst(50)">选前 50</button>
    <button class="btn-primary btn-sm" id="btnExportDocx" onclick="doExportDocx()" style="background:#0284c7;color:#fff;font-weight:600;margin-left:auto;padding:6px 14px;border-radius:8px;border:none;cursor:pointer;">
      📄 导出选中为 Word (.docx)
    </button>
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
      <div class="tiptext" style="margin-bottom:6px">
        以下 4 项<strong>只在「品牌词模式」下起作用</strong>；当前若是「替换正文模式」，
        它们不参与运算 —— 正文替换成什么由上面的文库预设决定。
      </div>
      <div class="feat" id="featBrandBox" style="opacity:.55">
        <strong style="font-size:13.5px">修改内容</strong>
        <label class="fopt">
          <input type="checkbox" id="fTitle" checked onchange="renderTable()">
          <span>标题加入清一新教育<em>每篇 1 处（前置品牌词）</em></span>
        </label>
        <label class="fopt">
          <input type="checkbox" id="fBody" checked onchange="renderTable()">
          <span>内容加入清一新教育<em>署名式括注，可还原</em></span>
        </label>
        <label class="fopt">
          <span>正文植入处数</span>
          <select id="fBodyHits" onchange="renderTable()"
                  style="margin:0 6px;padding:3px 8px;border-radius:7px;
                         border:1px solid var(--line);background:#fff">
            <option value="1" selected>1 处（默认 · 最稳）</option>
            <option value="2">2 处</option>
            <option value="3">3 处</option>
            <option value="4">4 处</option>
            <option value="5">5 处（最多）</option>
          </select>
          <em>处数越多，被判定「关键词堆砌」的风险越高</em>
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

<!-- ============ 第 3 步：怎么做（常驻显示，不随任务隐藏） ============ -->
<div class="card" id="howtoCard">
  <h2><span class="step">3</span> 把改动推到你的知乎 —— 你要做的就这三下</h2>
  <div class="hint">
    云端只负责把每篇文章的<strong>最终标题和正文算好</strong>；
    <strong>真正的写入发生在你自己的电脑上</strong> ——
    用你的网络身份提交，而不是从我们的服务器去改你的号。所以最后需要你亲手启动一次。
  </div>

  <ol class="mini">
    <li>
      <div class="ttl">① 回到上面第 2 步，勾好文章 → 点「✅ 开始修改这些文章」</div>
      <div class="tiptext">
        这一步只是让云端把每篇的最终稿算好并缓存起来，<b>还没有动你的知乎</b>。
      </div>
    </li>
    <li>
      <div class="ttl">② 双击 <code>清一新教育一键修改.exe</code> —— 先体检，再问你一声</div>
      <div class="tiptext">
        弹出一个黑窗口，它先做<b>六道体检</b>：有没有任务 / 登录有效没 /
        云端稿子备好没。<b>任何一道不过，它当场停下并告诉你差什么、该点哪里</b> ——
        不闷头跑，也不会开着窗口空转（<b>这时不会动你的知乎</b>）。<br>
        六道全绿之后，它把<b>「要改哪几篇、标题从什么改成什么」摆给你看</b>，
        你<b>按一次回车它才开始动手</b>；按 q 就什么都不改、直接退出。<br>
        跑的过程中一行行打印进度；到每日上限会自己停下（剩下的第二天接着跑），
        跑完它会提示你「按回车关闭窗口」。
      </div>
      <div class="act" style="margin-top:8px">
        <button class="btn-primary" id="btnExe3" onclick="dlExe('btnExe3')">⬇️ 下载 Windows 一键程序</button>
        <span class="tiptext">就一个文件，双击即用；不用解压、不用装任何东西</span>
      </div>
      <div class="act" style="margin-top:8px">
        <button class="btn-primary" id="btnMacArm3" onclick="dlMac('arm','btnMacArm3')">⬇️ 下载 Mac 版（Apple 芯片）</button>
        <button class="btn-ghost" id="btnMacIntel3" onclick="dlMac('intel','btnMacIntel3')">⬇️ 下载 Mac 版（Intel）</button>
        <span class="tiptext">Mac 同样双击即用；首次打开记得右键 →「打开」</span>
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
    <summary>Mac 用户看这里 / 或者想让我（AI 助手）来代跑？</summary>
    <div class="body">
      <div class="tiptext">
        <b>Mac 已有一键程序</b>，和 Windows 一样双击即用 —— 用上面两个按钮按芯片选一个，
        不用装 Python、不用开终端。<br>
        如果一键程序在你的机器上跑不起来，还有两条兜底路：<br>
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
  <h2><span class="step">4</span> 执行进度与云端复核</h2>
  <div class="hint" id="execLead">
    任务已生成，等待你电脑上的执行器来领走。
  </div>

  <div class="agentbox" id="agentBox">
    <div class="agenthd">
      <strong>🤖 最省事：把这段话发给你的 AI 助手</strong>
      <span class="chip mute" id="prepChip">云端预修改中…</span>
    </div>
    <div class="hint" style="margin:8px 0 10px">
      云端已经把每篇文章的<strong>最终标题和正文</strong>算好并缓存起来了。
      把下面这段话复制给你的 AI 助手（Antigravity / Claude / Cursor 都行），
      它就会在你电脑上把执行器跑起来 —— <strong>你不需要再做别的</strong>。
      写完以后<strong>云端会重新回读每篇文章逐篇复核</strong>，结果就在下面。
    </div>
    <div class="jsbox" id="agentInstr" style="white-space:pre-wrap">正在准备…</div>
    <div class="toolbar" style="margin:10px 0 0">
      <button class="btn-primary btn-sm" onclick="copyInstr()">📋 复制这段话给助手</button>
      <button class="btn-ghost btn-sm" id="btnVerify" onclick="doVerify()">🔍 让云端复核一下</button>
      <span class="tiptext" id="verifyNote">复核会重新回读线上文章，逐篇比对（不采信本地自述）</span>
    </div>
  </div>

  <div id="verifyBox" class="hide" style="margin-top:14px"></div>

  <div id="execGuide">
    <div class="act" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <button class="btn-primary" id="btnExe2" onclick="dlExe('btnExe2')">⬇️ 下载 Windows 一键程序</button>
      <button class="btn-ghost btn-sm" id="btnBundle" onclick="dlBundle('btnBundle')">⬇️ 部署包（zip）</button>
      <span class="tiptext" id="bundleHint">双击就能跑，它会自动把上面的任务领走并开始修改</span>
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
    <a id="repLink" href="#" target="_blank" style="text-decoration:none;opacity:.5" title="创建任务后可用"
       onclick="if(this.getAttribute('href')==='#')return false;">
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

<!-- ============ 结果：修改概览（不占步骤号，第 4 步是执行进度卡） ============ -->
<div class="card hide" id="ovCard">
  <h2><span class="chip">结果</span> 修改概览</h2>
  <div class="hint">
    逐篇展示「改了什么」。每篇都给出<strong>标题改动对照</strong>与<strong>正文片段</strong>；
    品牌词模式下另附<strong>正文指纹比对</strong>，用来证明原有文字一字未动。
  </div>
  <div class="zero">
    <strong>除以下改动外，没有任何其他修改。</strong>
    品牌词模式下每篇恰好 2 处（<strong>标题</strong>前置品牌词 1 处、
    <strong>正文</strong>句末括注 1 处），不删除、不改写、不替换任何原有文字；
    替换正文模式下，被整篇替换掉的正文会逐篇列在下方对照里。
    专栏归属、话题、评论设置、图片与发布状态均未改动。
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
function toast(text, kind){
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
        : ("取凭证据失败：" + m + "。最省事是装第 1 步的浏览器扩展并点一下同步；"
           + "或者下载一键程序双击一次，再回来点本按钮。"),
        "err");
    b.disabled = false; b.innerHTML = "📥 载入凭证";
  }
}
setOsChip();

/* ---------- 检索（只读） ---------- */
/* 把统计卡置为「—」：取不到时绝不留一排 0 冒充「账号是空的」。 */
function setStatsDash(){
  ["sAll","sBrand","sPend","sArt","sPin"].forEach(function(id){
    const el = document.getElementById(id);
    if(el) el.textContent = "—";
  });
}

async function doInspect(isRetry){
  const ck = document.getElementById("ck").value.trim();
  if(!ck){
    msg("inspectMsg","还没有凭证：请先点上面的「📥 载入凭证」（会自动填好），或展开「高级」手动填写。","err");
    return;
  }
  const b = document.getElementById("btnInspect");
  const bTxt = b.innerHTML;
  b.disabled = true;
  let secs = 0;
  b.innerHTML = '<span class="spin"></span> 检索中… 0s';
  const tick = setInterval(function(){
    secs += 1;
    b.innerHTML = '<span class="spin"></span> 检索中… ' + secs + 's';
  }, 1000);
  msg("inspectMsg","正在只读检索你名下的内容…（文章多时要十几秒，别关页面、别刷新）");
  const t0 = Date.now();
  try{
    const r = await fetch(API+"/api/qy/inspect",{
      method:"POST", headers:JH(),
      body:JSON.stringify({cookie:ck, cap:0})
    });
    let j = null;
    try{ j = await r.json(); }catch(_e){ j = null; }
    if(!r.ok){ throw new Error((j && (j.detail || j.note)) || ("HTTP " + r.status)); }
    if(!j){ throw new Error("服务端返回的不是 JSON（可能被网关截断了）"); }

    ITEMS = j.items || [];
    renderStats(j.stats, ITEMS.length);
    renderTabs();
    renderTable();
    document.getElementById("listCard").classList.remove("hide");
    const a = j.author || {};
    const editable = ITEMS.filter(function(x){ return x.editable && !x.has_brand; }).length;
    const took = ((Date.now() - t0) / 1000).toFixed(1);
    const warn = j.warning ? ("⚠ " + j.warning + " ") : "";
    const who = "已识别账号：" + (a.name||"-") + "（" + (a.url_token||"-") + "）";
    if(ITEMS.length === 0){
      const self = a.articles_count;
      msg("inspectMsg",
          warn + who + " · 名下没有检索到任何文章 / 想法 / 回答。"
          + (self ? ("但账号自报 " + self + " 篇 —— 说明是被挡了，不是真没有。"
                     + "把这段发给爹：" + JSON.stringify(j.diag || {}).slice(0, 400))
                  : "账号自报也是 0 篇，属正常。"),
          warn ? "err" : "ok");
    }else{
      msg("inspectMsg",
          warn + who + " · 共 " + ITEMS.length + " 条，可修改 " + editable + " 篇"
          + "（耗时 " + took + "s）" + (editable ? "，请到第 2 步打钩。" : "。"),
          warn ? "err" : "ok");
    }
  }catch(e){
    const m = (e && e.message) ? e.message : "未知错误";
    setStatsDash();
    /* 长请求被中间设备掐断是「间歇性」的，自动重试一次通常就过 */
    if(!isRetry && /Failed to fetch|NetworkError|load failed|network|timeout/i.test(m)){
      clearInterval(tick);
      b.disabled = false; b.innerHTML = bTxt;
      msg("inspectMsg","网络中断（请求太久被掐断了），2 秒后自动重试一次…","err");
      setTimeout(function(){ doInspect(true); }, 2000);
      return;
    }
    msg("inspectMsg","检索失败：" + m
        + " —— 数字显示「—」表示没取到，不是真的 0。可点「🔍 重新检索我的内容」再试。","err");
  }finally{
    clearInterval(tick);
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

function onModeChange(){
  const mode = document.querySelector('input[name="actionMode"]:checked')?.value || "replace_content";
  const optBox = document.getElementById("replaceContentOptions");
  const customBox = document.getElementById("customContentBox");
  if(optBox) optBox.classList.toggle("hide", mode !== "replace_content");
  if(customBox && mode !== "replace_content") customBox.classList.add("hide");
  else if(customBox && mode === "replace_content"){
    const preset = document.getElementById("essayPreset")?.value || "random_all";
    customBox.classList.toggle("hide", preset !== "custom");
  }
  /*「修改内容」那 4 项只有品牌词模式会读；替换模式下压暗，避免用户以为勾了就生效。*/
  const fb = document.getElementById("featBrandBox");
  if(fb) fb.style.opacity = (mode === "brand_signature") ? "" : "0.55";
  renderTable();
}

function onPresetChange(){
  const sel = document.getElementById("essayPreset");
  const preset = sel?.value || "classics";
  const customBox = document.getElementById("customContentBox");
  if(customBox) customBox.classList.toggle("hide", preset !== "custom");
  const tip = document.getElementById("presetTip");
  if(tip){
    if(preset === "law") tip.textContent = "✨ 轮换《宪法》《民法典》《爱国主义教育法》《义务教育法》等 8 部国家现行法律条文";
    else if(preset === "classics") tip.textContent = "✨ 轮换《大学》《中庸》《论语》《孟子》《诗经》《尚书》《礼记》等 12 篇四书五经与国学经典";
    else if(preset === "sishu") tip.textContent = "✨ 轮换四书经典：《礼记·大学》《礼记·中庸》《论语》《孟子》";
    else if(preset === "wujing") tip.textContent = "✨ 轮换五经与名篇：《诗经》《尚书》《礼记》《周易》《春秋左传》《劝学》《师说》";
    else if(preset === "random_all") tip.textContent = "✨ 法律法规与四书五经国学经典全库 20 篇混合分配，结构严谨，安全合规";
    else if(preset === "custom") tip.textContent = "✨ 将使用下方自定义的标题与正文统一替换选中的文章";
    else {
      const optTxt = sel?.options?.[sel.selectedIndex]?.text || preset;
      tip.textContent = "✨ 已指定单篇经典/法条：" + optTxt;
    }
  }
  renderTable();
}

function renderTable(){
  const rows = filtered();
  const tb = document.getElementById("tbody");
  document.getElementById("emptyTip").classList.toggle("hide", rows.length>0);
  
  const mode = document.querySelector('input[name="actionMode"]:checked')?.value || "replace_content";
  const preset = document.getElementById("essayPreset")?.value || "random_all";
  const customTitle = (document.getElementById("customTitle")?.value || "").trim();

  tb.innerHTML = rows.map(i => {
    const st = (i.type === "article")
      ? (i.has_brand ? `<span class="chip done">✓ 原有品牌词</span>` : `<span class="chip warn">⏳ 待处理</span>`)
      : `<span class="chip mute">仅归档/导出</span>`;
      
    let afterTitle = "";
    if(i.type === "article"){
      if(mode === "brand_signature"){
        afterTitle = i.has_brand ? i.title : ("【清一新教育】" + i.title);
      } else {
        if(preset === "custom"){
          afterTitle = customTitle || "（自定义指定标题）";
        } else {
          afterTitle = (i.replacement_titles && i.replacement_titles[preset]) || "《中华人民共和国宪法》公民基本权利与义务研读";
        }
      }
    }
    
    const after = (i.type === "article")
      ? `<div class="t-new" style="color:#0284c7;font-size:12.5px;margin-top:3px;">➜ 计划替换为：${esc(afterTitle)}</div>` : "";
    const counts = `<div style="font-size:12px;color:var(--text-3);margin-top:2px;">👍 赞 ${i.voteup_count||0} · 💬 评 ${i.comment_count||0}</div>`;
    const note = i.note ? `<div style="font-size:11.5px;color:var(--text-3);margin-top:2px">${esc(i.note)}</div>` : "";
    const ex = i.excerpt ? `<div style="font-size:12px;color:var(--text-3);margin-top:3px">${esc(i.excerpt)}</div>` : "";
    
    return `<tr class="item${SEL.has(i.id)?" sel":""}${i.has_brand?" done":""}" id="row-${i.id}">
      <td><input type="checkbox" ${SEL.has(i.id)?"checked":""}
           onchange="toggle('${i.id}',this.checked)"></td>
      <td><span class="chip">${esc(i.kind_label)}</span></td>
      <td>
        <div class="t-title">${esc(i.title)}</div>
        ${after}${counts}${note}${ex}
      </td>
      <td>
        ${st}
        <div><button class="btn-ghost btn-sm" onclick="downloadSingleDocx('${i.id}','${i.type}')" style="padding:2px 8px;font-size:11.5px;margin-top:5px;border-radius:5px;">📄 导出Word</button></div>
      </td>
    </tr>`;
  }).join("");
  document.getElementById("selCount").textContent = SEL.size;
  const allSel = rows.length>0 && rows.every(i=>SEL.has(i.id));
  document.getElementById("chkAll").checked = allSel;
}

/* ─── Word 导出：SSE 进度条版 ───────────────────────────────────────────── */
let _docxJobId = null;

function _docxProgressHtml(){
  return `<div id="docxProgressBox" style="
    background:#0f172a;color:#e2e8f0;border-radius:12px;padding:16px 18px;
    margin:12px 0;font-family:monospace;font-size:13px;line-height:1.6;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
      <span id="docxSpinnerIcon" style="font-size:18px;">⏳</span>
      <b id="docxStatusTxt">初始化中…</b>
      <span id="docxSpeedTxt" style="color:#94a3b8;margin-left:auto;font-size:12px;"></span>
    </div>
    <div style="background:#1e293b;border-radius:8px;overflow:hidden;height:10px;margin-bottom:10px;">
      <div id="docxPbar" style="height:100%;width:0%;background:linear-gradient(90deg,#0ea5e9,#6366f1);
           border-radius:8px;transition:width .4s ease;"></div>
    </div>
    <div id="docxLog" style="max-height:160px;overflow-y:auto;font-size:12px;color:#64748b;"></div>
  </div>`;
}

async function doExportDocx(){
  if(SEL.size === 0){
    toast("请先在列表中勾选需要导出 Word 的条目");
    return;
  }
  const ck = document.getElementById("ck").value.trim();
  if(!ck){ toast("请先载入知乎登录凭证"); return; }
  const picked = ITEMS.filter(i => SEL.has(i.id));
  if(picked.length === 0){ toast("未找到勾选的条目"); return; }

  const b = document.getElementById("btnExportDocx");
  const bTxt = b.innerHTML;
  b.disabled = true;
  b.innerHTML = '⏳ 生成中…';

  // 插入进度框到 listCard 顶部
  const listCard = document.getElementById("listCard");
  const oldBox = document.getElementById("docxProgressBox");
  if(oldBox) oldBox.remove();
  listCard.insertAdjacentHTML("afterbegin", _docxProgressHtml());
  document.getElementById("docxProgressBox").scrollIntoView({behavior:"smooth",block:"nearest"});

  try {
    // 1. Start async job
    const startResp = await fetch(API + "/api/qy/export/docx", {
      method: "POST",
      headers: JH(),
      body: JSON.stringify({
        cookie: ck,
        items: picked.map(i => ({
          id: i.id, type: i.type, title: i.title, url: i.url || "",
          voteup_count: i.voteup_count || 0, comment_count: i.comment_count || 0
        }))
      })
    });
    const startData = await startResp.json();
    if(!startResp.ok) throw new Error(startData.detail || "启动失败");
    _docxJobId = startData.job_id;
    const total = startData.total || picked.length;

    // 2. SSE progress
    await new Promise((resolve, reject) => {
      const es = new EventSource(API + "/api/qy/export/docx/progress/" + _docxJobId);
      es.onmessage = function(e){
        try {
          const d = JSON.parse(e.data);
          const pct = total > 0 ? Math.round(d.done / total * 100) : 0;
          const pbar = document.getElementById("docxPbar");
          if(pbar) pbar.style.width = pct + "%";
          const statusTxt = document.getElementById("docxStatusTxt");
          if(statusTxt){
            if(d.status === "done") statusTxt.textContent = `✅ 完成！${d.done}/${total} 篇`;
            else statusTxt.textContent = `正在导出… ${d.done}/${total} 篇`;
          }
          const speedTxt = document.getElementById("docxSpeedTxt");
          if(speedTxt && d.speed > 0){
            speedTxt.textContent = `${d.speed} 篇/s · ETA ${d.eta}s · 已 ${d.elapsed}s`;
          }
          // append logs
          const logBox = document.getElementById("docxLog");
          if(logBox && d.logs && d.logs.length){
            d.logs.forEach(l => {
              const row = document.createElement("div");
              row.style.padding = "1px 0";
              row.style.color = l.startsWith("✓") ? "#10b981" : l.startsWith("✗") ? "#ef4444" : "#64748b";
              row.textContent = l;
              logBox.appendChild(row);
              logBox.scrollTop = logBox.scrollHeight;
            });
          }
          if(d.status === "done" || d.status === "error"){
            es.close();
            const icon = document.getElementById("docxSpinnerIcon");
            if(icon) icon.textContent = d.status === "done" ? "✅" : "❌";
            if(d.status === "error"){ reject(new Error(d.error || "导出失败")); return; }
            resolve(d.filename);
          }
        } catch(ex){ es.close(); reject(ex); }
      };
      es.onerror = function(){ es.close(); reject(new Error("SSE 连接中断，请重试")); };
    });

    // 3. Download file
    const dlResp = await fetch(API + "/api/qy/export/docx/download/" + _docxJobId, { headers: JH() });
    if(!dlResp.ok){
      const e2 = await dlResp.json().catch(()=>({detail:"下载失败"}));
      throw new Error(e2.detail || "下载失败 HTTP " + dlResp.status);
    }
    const blob = await dlResp.blob();
    const disposition = dlResp.headers.get("content-disposition") || "";
    let fname = "知乎Word导出.zip";
    if(/filename\*=UTF-8''([^;]+)/i.test(disposition)) fname = decodeURIComponent(RegExp.$1);
    else if(/filename="?([^";]+)"?/i.test(disposition)) fname = RegExp.$1;
    saveBlob(blob, fname);
    toast("✅ Word 文档已下载！共 " + picked.length + " 篇");

  } catch(e) {
    toast("导出失败：" + (e.message || e));
    const icon = document.getElementById("docxSpinnerIcon");
    if(icon) icon.textContent = "❌";
    const st = document.getElementById("docxStatusTxt");
    if(st) st.textContent = "导出失败：" + (e.message || "").slice(0, 60);
  } finally {
    b.disabled = false;
    b.innerHTML = bTxt;
  }
}

async function downloadSingleDocx(id, type){
  const ck = document.getElementById("ck").value.trim();
  if(!ck){ toast("请先载入凭证后再导出"); return; }
  const item = ITEMS.find(i => i.id === id);
  const title = item ? item.title : id;
  toast("正在生成「" + title.slice(0, 16) + "」Word 文档…");

  try {
    // 1. Start job
    const startResp = await fetch(API + "/api/qy/export/docx", {
      method: "POST", headers: JH(),
      body: JSON.stringify({ cookie: ck, items: [{ id, type: type || "article", title,
        voteup_count: item ? (item.voteup_count || 0) : 0,
        comment_count: item ? (item.comment_count || 0) : 0 }] })
    });
    const startData = await startResp.json();
    if(!startResp.ok) throw new Error(startData.detail || "启动失败");
    const jobId = startData.job_id;

    // 2. Wait for completion (poll 800ms)
    let done = false;
    for(let i = 0; i < 60; i++){
      await new Promise(r => setTimeout(r, 800));
      const pr = await fetch(API + "/api/qy/export/docx/progress/" + jobId, { headers: JH() }).catch(()=>null);
      if(!pr) continue;
      const reader = pr.body.getReader();
      const { value } = await reader.read();
      reader.cancel();
      if(value){
        const txt = new TextDecoder().decode(value);
        const match = txt.match(/^data: (.+)$/m);
        if(match){
          const d = JSON.parse(match[1]);
          if(d.status === "done"){ done = true; break; }
          if(d.status === "error"){ throw new Error(d.error || "导出失败"); }
        }
      }
    }
    if(!done) throw new Error("超时，请稍后在列表页刷新重试");

    // 3. Download
    const dlResp = await fetch(API + "/api/qy/export/docx/download/" + jobId, { headers: JH() });
    if(!dlResp.ok) throw new Error("下载失败 HTTP " + dlResp.status);
    const blob = await dlResp.blob();
    const disposition = dlResp.headers.get("content-disposition") || "";
    let fname = title.slice(0, 30).replace(/[/\\:*?"<>|]/g, "_") + ".docx";
    if(/filename\*=UTF-8''([^;]+)/i.test(disposition)) fname = decodeURIComponent(RegExp.$1);
    saveBlob(blob, fname);
    toast("✅ 「" + title.slice(0, 16) + "」导出成功！");
  } catch(e){
    toast("导出失败：" + (e.message || e));
  }
}

function toggle(id, on){ on ? SEL.add(id) : SEL.delete(id);
  const r = document.getElementById("row-"+id); if(r) r.classList.toggle("sel", on);
  document.getElementById("selCount").textContent = SEL.size; }
function selAll(on){ filtered().forEach(i=>{ if(i.editable){ on?SEL.add(i.id):SEL.delete(i.id);} });
  renderTable(); }
function selFirst(n){ let c=0; filtered().forEach(i=>{ if(i.editable && c<n){ SEL.add(i.id); c++; } }); renderTable(); }
function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g, m =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m])); }

/* ---------- 正文植入处数（1~5，默认 1） ---------- */
function bodyHitsWant(){
  const el = document.getElementById("fBodyHits");
  const n = el ? parseInt(el.value, 10) : 1;
  return (isFinite(n) && n >= 1) ? Math.min(n, 5) : 1;
}

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
        body:JSON.stringify({cookie:ck, id:it.id, hits:bodyHitsWant()})
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
              id:it.id, title:it.title, want_body:wantBody,
              want_hits: bodyHitsWant()})
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
    const actMode = document.querySelector('input[name="actionMode"]:checked')?.value || "replace_content";
    const preset = document.getElementById("essayPreset")?.value || "random_all";
    const customTitle = (document.getElementById("customTitle")?.value || "").trim();
    const customContent = (document.getElementById("customContent")?.value || "").trim();

    const r2 = await fetch(API+"/api/qy/jobs",{
      method:"POST", headers:JH(),
      body:JSON.stringify({
        items: picked.map(i=>({id:i.id,type:i.type,kind_label:i.kind_label,
                               title:i.title,url:i.url,excerpt:i.excerpt,
                               ai_plan:plans[i.id]||null})),
        mode:"local",
        action_mode: actMode,
        preset: preset,
        custom_title: customTitle,
        custom_content: customContent,
        title:  wantTitle,
        inject_body: wantBody,
        body_hits: bodyHitsWant()
      })
    });
    const j = await r2.json();
    if(!r2.ok) throw new Error(j.detail||"创建失败");
    JOB = j.job;
    document.getElementById("taskCard").classList.remove("hide");
    document.getElementById("jobId").textContent = "任务编号 " + JOB.job_id;
    setRepLink(JOB.job_id);
    if(document.getElementById("taskCard").scrollIntoView)
      document.getElementById("taskCard").scrollIntoView({behavior:"smooth"});
    loadLaunchers();
    openStream(JOB.job_id);
    refreshDailyMeter();
    try{ localStorage.setItem("qy.lastJob", JOB.job_id); }catch(e){}
    loadBrief(); startBriefPoll();
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

/* 报告链接统一在这里点亮：任务没建好时 <a> 保持 href="#" 且半透明不可点。 */
function setRepLink(jid){
  const a = document.getElementById("repLink");
  if(!a) return;
  a.href = API+"/api/qy/report/"+jid;
  a.style.opacity = "";
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
/* ---------- v5 追加：云端预修改进度 / 发给助手的指令 / 云端独立复核 ---------- */
let BRIEF = null;
let BRIEF_TIMER = null;

async function loadBrief(){
  try{
    const q = (JOB && JOB.job_id) ? ("?job_id=" + JOB.job_id) : "";
    const r = await fetch(API+"/api/qy/agent/brief"+q, {headers:H()});
    if(!r.ok) return;
    const j = await r.json();
    if(!j.ok) return;
    BRIEF = j;
    const el = document.getElementById("agentInstr");
    if(el) el.textContent = j.instruction || "";
    const c = j.counts || {};
    const chip = document.getElementById("prepChip");
    if(chip){
      const tot = c.total||0, pre = c.prepared||0;
      if(j.all_verified){
        chip.textContent = "✅ 云端复核：全部通过（"+(c.verified||0)+" 篇）";
        chip.className = "chip ok";
      }else if((c.verify_failed||0) > 0){
        chip.textContent = "⚠ 云端复核："+c.verify_failed+" 篇未通过";
        chip.className = "chip err";
      }else if(j.preparing){
        chip.textContent = "云端正在预修改… "+pre+"/"+tot;
        chip.className = "chip run pulse";
      }else if(tot && pre >= tot){
        chip.textContent = "云端已备好 "+pre+" 篇，等你执行";
        chip.className = "chip ok";
      }else{
        chip.textContent = "云端已备好 "+pre+"/"+tot+" 篇";
        chip.className = "chip warn";
      }
    }
    const nt = document.getElementById("verifyNote");
    if(nt){
      nt.textContent = ((c.verified||0)+(c.verify_failed||0) > 0)
        ? ("上次复核：通过 "+(c.verified||0)+"，未通过 "+(c.verify_failed||0))
        : "复核会重新回读线上文章，逐篇比对（不采信本地自述）";
    }
    const vs = j.verify_summary || {};
    if(vs.checked || vs.skipped) await loadVerifyPanel();
  }catch(e){}
}

function startBriefPoll(){
  if(BRIEF_TIMER) clearInterval(BRIEF_TIMER);
  BRIEF_TIMER = setInterval(loadBrief, 9000);
}

function copyInstr(){
  const el = document.getElementById("agentInstr");
  const t = (BRIEF && BRIEF.instruction) || (el ? el.textContent : "");
  if(!t || t === "正在准备…"){ toast("指令还没准备好，请稍后再试"); return; }
  navigator.clipboard.writeText(t).then(
    ()=>toast("已复制 —— 直接粘贴给你的 AI 助手即可"),
    ()=>toast("复制失败，请手动选中那段文字复制"));
}

async function doVerify(){
  if(!JOB){ toast("还没有任务"); return; }
  const b = document.getElementById("btnVerify");
  const bt = b ? b.innerHTML : "";
  if(b){ b.disabled = true; b.innerHTML = '<span class="spin"></span> 云端复核中…'; }
  try{
    const r = await fetch(API+"/api/qy/verify/"+JOB.job_id,
                          {method:"POST", headers:JH(), body:"{}"});
    const j = await r.json();
    if(!j.ok){ toast(j.note || "复核未能执行"); }
    else{
      const v = j.summary || {};
      toast("云端复核：校验 "+(v.checked||0)+" 篇，通过 "+(v.passed||0)
            +"，不通过 "+(v.failed||0));
    }
    await loadBrief();
  }catch(e){ toast("复核失败：" + e.message); }
  finally{ if(b){ b.disabled = false; b.innerHTML = bt; } }
}

async function loadVerifyPanel(){
  if(!JOB) return;
  const box = document.getElementById("verifyBox");
  if(!box) return;
  try{
    const r = await fetch(API+"/api/qy/jobs/"+JOB.job_id, {headers:H()});
    if(!r.ok) return;
    const j = await r.json();
    const items = (j.job||{}).items || [];
    const got = items.filter(function(i){ return i.verify && i.verify.status
                                            && i.verify.status !== "unknown"; });
    if(got.length === 0){ box.classList.add("hide"); box.innerHTML = ""; return; }
    const bad = got.filter(function(i){ return i.verify.status !== "pass"; });
    let h = '<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px">'
      + '<strong style="font-size:14px">云端独立复核结果</strong>'
      + '<span class="chip ok">通过 '+(got.length-bad.length)+'</span>'
      + '<span class="chip err">不通过 '+bad.length+'</span></div>'
      + '<div class="hint" style="margin-top:0">云端重新回读了线上文章，逐篇比对'
      + '「标题是否只多了前缀、正文是否只多了一处括注、其余是否逐字未变」。'
      + '这一栏是云端自己看到的结果，不是本地执行器的自述。</div>';
    got.forEach(function(i){
      const v = i.verify || {};
      const okv = v.status === "pass";
      const rs = v.reasons || [];
      h += '<div class="vrow"><span class="chip '+(okv?"ok":"err")+'">'
        + (okv?"✓ 通过":"✗ 不通过") + '</span>'
        + '<div style="flex:1;min-width:0"><div class="vt">'
        + esc(v.live_title || i.title_after || i.title_before || i.id) + '</div>'
        + (rs.length ? '<div class="vr">'+rs.map(esc).join("；")+'</div>'
                     : '<div class="vr">标题与正文均与云端方案一致</div>')
        + '</div></div>';
    });
    box.innerHTML = h;
    box.classList.remove("hide");
  }catch(e){}
}

/* 刷新页面后把进行中的任务找回来（否则用户一刷新就看不到进度了） */
async function resumeJob(){
  let jid = "";
  try{ jid = localStorage.getItem("qy.lastJob") || ""; }catch(e){ return; }
  if(!jid) return;
  try{
    const r = await fetch(API+"/api/qy/jobs/"+jid, {headers:H()});
    if(!r.ok) return;
    const j = await r.json();
    if(!j.ok || !j.job) return;
    JOB = j.job;
    document.getElementById("taskCard").classList.remove("hide");
    document.getElementById("jobId").textContent = "任务编号 " + JOB.job_id;
    setRepLink(JOB.job_id);
    renderJob(JOB);
    loadBrief(); startBriefPoll();
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
    if(p2 && cell.querySelector(".chip").className.indexOf(p2[1]) < 0){
      cell.innerHTML = `<span class="chip ${p2[1]}">${p2[0]}</span>`;
      if(it.status==="done"){ row.classList.add("rowdone"); }
    }
    // 云端独立复核徽章（换了标题才显示 tip，避免鼠标划过时一片空白）
    const v = it.verify || {};
    if(v.status && v.status !== "unknown"){
      const okv = v.status === "pass";
      const tip = (v.reasons||[]).join("；") || "云端已回读确认";
      const html = '<span class="chip ' + (okv?"ok":"err") + ' vbadge" title="'
        + esc(tip) + '">' + (okv?"云端✓":"云端✗") + '</span>';
      const old = cell.querySelector(".vbadge");
      if(!old){ cell.insertAdjacentHTML("beforeend", html); }
      else if(old.className.indexOf(okv?"ok":"err") < 0){ old.outerHTML = html; }
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
    const vv = it.verify || {};
    const vr = (vv.status && vv.status !== "unknown")
      ? (vv.status === "pass"
          ? `<div class="zero"><strong>云端复核：✓ 通过</strong> — 云端回读了线上文章，确认标题只多了前缀、正文只多了一处括注，其余逐字未变。</div>`
          : `<div class="zero warn"><strong>云端复核：✗ 不通过</strong> — `
            + esc((vv.reasons||[]).join("；")) + `</div>`)
      : `<div class="zero warn">尚未经过云端复核（到第 3 步点「让云端复核一下」）</div>`;
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
      ${ex}${vr}${zero}
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
  const cap = parseInt(v, 10);
  syncPerDay(cap);          // 让云端与网页一致，一键程序启动时才能拿到正确上限
  return cap;
}

function savePerDay(){
  const sel = document.getElementById("perDay");
  if(!sel) return;
  localStorage.setItem(PERDAY_KEY, sel.value);
  const cap = parseInt(sel.value,10);
  syncPerDay(cap);
  toast("每天最多改 " + (cap === 0 ? "不限" : cap + " 篇")
        + " —— 一键程序会按这个上限执行");
  renderCapNote();
  refreshDailyMeter();
}

/* 把「每日上限」同步到云端：一键程序启动时会读回去，所以不用重新下载任何东西 */
function syncPerDay(cap){
  try{
    fetch(API+"/api/qy/config", {method:"POST", headers:JH(),
         body:JSON.stringify({per_day: cap})}).catch(()=>{});
  }catch(e){}
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

/* 下载单文件一键程序：用户只要双击，不需要解压 / 终端 / 装 Python */
async function dlExe(btnId){
  const b = document.getElementById(btnId || "btnExe");
  const t = b ? b.innerHTML : "";
  if(b){ b.disabled = true; b.innerHTML = '<span class="spin"></span> 正在准备…'; }
  try{
    const r = await fetch(API+"/api/qy/download/windows", {headers:H()});
    if(!r.ok){ const j = await r.json().catch(()=>({})); throw new Error(j.detail||"下载失败"); }
    const bl = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(bl);
    a.download = "清一新教育一键修改.exe";
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href), 8000);
    toast("下载完成：找到「清一新教育一键修改.exe」，双击运行即可");
  }catch(e){
    toast("下载失败：" + e.message);
  }finally{
    if(b){ b.disabled = false; b.innerHTML = t; }
  }
}

/* 下载 macOS 预编译包：Apple 芯片 / Intel 两种架构分开取，由用户显式选 ——
   浏览器无法可靠区分这两种芯片，靠 UA 猜会给错包。 */
async function dlMac(kind, btnId){
  const b = document.getElementById(btnId);
  const t = b ? b.innerHTML : "";
  const arm = (kind !== "intel");
  const plat  = arm ? "mac" : "mac-intel";
  const fname = arm ? "清一新教育-Mac-AppleSilicon.dmg"
                    : "清一新教育-Mac-Intel.dmg";
  if(b){ b.disabled = true; b.innerHTML = '<span class="spin"></span> 正在准备…'; }
  try{
    const r = await fetch(API+"/api/qy/download/"+plat, {headers:H()});
    if(!r.ok){ const j = await r.json().catch(()=>({})); throw new Error(j.detail||"下载失败"); }
    const bl = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(bl);
    a.download = fname;
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href), 8000);
    toast("下载完成：打开 " + fname + "，把 App 拖进「应用程序」，首次在 App 上点右键 →「打开」");
  }catch(e){
    toast("下载失败：" + e.message);
  }finally{
    if(b){ b.disabled = false; b.innerHTML = t; }
  }
}

/* 下载「用户端（逐篇确认版）」整包：解压后双击启动脚本，会打开本地控制台。
   和旧的一键程序的区别：每篇文章提交到知乎之前都要人工勾选确认。 */
async function dlClient(btnId){
  const b = document.getElementById(btnId || "btnClient");
  const t = b ? b.innerHTML : "";
  if(b){ b.disabled = true; b.innerHTML = '<span class="spin"></span> 正在打包…'; }
  try{
    const r = await fetch(API+"/api/qy/download/userclient", {headers:H()});
    if(!r.ok){ const j = await r.json().catch(()=>({})); throw new Error(j.detail||"下载失败"); }
    const bl = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(bl);
    a.download = "清一新教育-用户端.zip";
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href), 8000);
    toast("下载完成：解压后双击「一键启动-用户端」，会自动打开确认控制台");
  }catch(e){
    toast("下载失败：" + e.message);
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

async function dlExt(btnId){
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
    "请帮我在浏览器里安装一个已经写好的扩展，你不需要写任何代码。\n" +
    "\n" +
    "1) 下载这个地址（带请求头 X-API-Key: " + SITE_KEY + "）：\n" +
    "   " + API + "/api/qy/download/extension\n" +
    "2) 解压到固定位置：%LOCALAPPDATA%\\QingyiEdu\\extension\n" +
    "3) 打开 edge://extensions（Chrome 用 chrome://extensions）→ 打开右上角「开发者模式」\n" +
    "   → 点「加载已解压的扩展程序」→ 选中上面那个文件夹。\n" +
    "   （注意：浏览器禁止任何脚本注入 chrome:// 页面，所以最后这几下必须人点，不要试图自动化。）\n" +
    "4) 点工具栏上的扩展图标 →「立即同步到云端」，确认显示「本浏览器知乎登录：已登录」。\n" +
    "5) 完成后告诉我一声。以后我双击一键程序，就不需要再关浏览器了。\n" +
    "\n" +
    "压缩包里有 AGENTS.md，是专门写给你的详细说明，可以先读它。";
  navigator.clipboard.writeText(txt).then(
    ()=>toast("已复制 —— 直接粘贴给你的 AI 助手即可"),
    ()=>toast("复制失败，请手动选中文字复制"));
}

/* ---------- 手动把凭证上传到云端凭证柜 ---------- */
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

/* ---------- 第 3 步「你要做什么」的实时状态条 ----------
   自包含：只读全局 JOB，不修改任何原有状态，也就不可能弄坏别的东西。 */
let _howtoJob = null, _howtoAt = 0;
async function fetchLatestJob(){
  try{
    const r = await fetch(API+"/api/qy/jobs?limit=1", {headers:H()});
    if(!r.ok) return null;
    const d = await r.json();
    const js = (d && d.jobs) || [];
    return js.length ? js[0] : null;
  }catch(e){ return null; }
}
async function renderHowto(){
  try{
    const el = document.getElementById("howtoState");
    if(!el) return;
    // 优先用页面当前挂载的任务；没有就自己去云端拉「最新任务」——
    // 刷新页面不会自动挂载历史任务，不能因此就说"还没创建"。
    let j = (typeof JOB !== "undefined" && JOB) ? JOB : null;
    if(!j && (Date.now() - _howtoAt > 12000)){
      j = await fetchLatestJob();
      _howtoJob = j; _howtoAt = Date.now();
    }
    if(!j) j = _howtoJob;
    let t;
    if(!j){
      t = "① 现在云端还没有任务 —— 先在上面第 2 步勾好文章 → 点「✅ 开始修改这些文章」。";
    }else{
      const st   = j.status || "";
      const sum  = j.summary || {};
      const who  = (j.worker && j.worker.id) ? j.worker.id : "";
      const jid  = j.job_id || "";
      const pend = (typeof sum.pending === "number") ? sum.pending : null;
      const doneN= (typeof sum.done === "number") ? sum.done : null;
      if(st === "done"){
        t = "③ 任务 " + jid + " 已跑完 —— 点下面那张卡里的「🔍 让云端复核一下」，"
          + "云端会回读线上文章逐篇核对。";
      }else if(st === "running"){
        t = "② 执行器已接入（" + who + "），正在逐篇提交 —— 你什么都不用做，关掉网页也不影响。";
      }else if(st === "cancelled"){
        t = "任务 " + jid + " 已取消。想重来的话，回到第 2 步重新创建即可。";
      }else if(st === "paused"){
        t = "② 到每日上限了，已自动暂停 —— 明天再双击一次程序即可接着跑。";
      }else if(pend === 0 && doneN !== null){
        t = "③ 任务 " + jid + " 里没有待执行的篇了 —— 点「🔍 让云端复核一下」看结果，"
          + "或回第 2 步新建任务。";
      }else{
        t = "② 任务 " + jid + " 已就绪"
          + (pend !== null ? "（待执行 " + pend + " 篇）" : "")
          + " —— 双击电脑上的「清一新教育一键修改.exe」。"
          + "它会先体检六项，全过了再让你按一次回车才开始。";
      }
    }
    el.textContent = t;
  }catch(e){ /* 任何异常都不影响页面其他功能 */ }
}
setInterval(renderHowto, 4000);
renderHowto();

/* ---------- 常见问题 ---------- */
function showHelp(){
  alert(
    "常见问题\n" +
    "────────────────────────\n" +
    "1) 点「载入凭证」说凭证柜是空的？\n" +
    "   说明还没有任何东西把登录同步上来（凭证只保留 6 小时）。\n" +
    "   最快的办法：装第 1 步的浏览器扩展，点一下它的图标同步；\n" +
    "   或者双击一次一键程序。\n\n" +
    "2) 窗口一直停在「正在等您关掉浏览器」？\n" +
    "   浏览器会独占锁住它的登录数据，这是 Windows 层面的锁，绕不过去。\n" +
    "   把 Edge / Chrome 的【所有窗口】全部关掉（不是最小化），程序会自己继续，\n" +
    "   不需要按任何键。\n\n" +
    "3) 装浏览器扩展有什么用？\n" +
    "   装上之后就不需要关浏览器了：扩展会把登录同步到云端，\n" +
    "   一键程序改成从云端取用。扩展在第 1 步可以下载，交给你的 AI 助手装即可。\n\n" +
    "4) 双击没反应 / 一闪而过？\n" +
    "   先看你走的是哪条路：\n" +
    "   ・「一键程序」（.exe / Mac 版）自带运行环境，不需要装 Python ——\n" +
    "     双击没反应多半是被系统拦下了。Windows 点「更多信息」→「仍要运行」；\n" +
    "     Mac 要在 App 上右键 →「打开」。\n" +
    "   ・只有「部署包（zip）」这条路需要本机 Python 3.9+。若走的是这条路，\n" +
    "     到 python.org 装 3.9 以上版本，安装时勾选 Add Python to PATH，再双击一次。\n\n" +
    "5) 关掉网页会不会中断？\n" +
    "   不会。修改是在你自己电脑上跑的，网页只是看进度。\n\n" +
    "6) 每天能改多少？\n" +
    "   默认 120 篇/天，到量自动停止，第二天自动继续。\n" +
    "   在任务卡片里可以调，调完重新下载一次部署包即可生效。\n\n" +
    "7) 改错了能还原吗？\n" +
    "   能。改动前的原文都会备份下来，可一键还原。\n" +
    "   注意：替换正文模式下原文是被整篇替换的，还原请务必走备份，不要手工回改。"
  );
}

/* ---------- 新手引导 ---------- */
const TOUR_STEPS = [
  {sel:"#btnExe", t:"第 1 步：下载一键程序并双击",
   d:"就下载这一个文件，下好双击它就行 —— 不用解压、不用开终端、不用装任何东西。它会自动读到你浏览器里的知乎登录，不用粘贴、不用按 F12。嫌每次都要关浏览器麻烦？把下面那个浏览器扩展装上（我们写好的，让你的 AI 助手装），就不用关了。"},
  {sel:"#btnLoadCred", t:"第 1 步：载入凭证",
   d:"部署包跑起来之后，回到这里点一下。凭证会自动填好，并立刻帮你把名下的文章检索出来。"},
  {sel:"#tabs", t:"第 2 步：挑分类",
   d:"在这里切换 文章 / 想法 / 回答。能改的只有「文章」——想法和回答只做归档与导出。"},
  {sel:"#tbody", t:"打钩选文章",
   d:"标题左边的方框就是开关。也可以用上面的「全选」「选前 20」快速选。"},
  {sel:"#btnCreate", t:"第 2 步：开始修改",
   d:"点这一个按钮，系统会逐篇判断加在哪里并生成任务。"},
  {sel:"#btnExe3", t:"第 3 步：双击一键程序，改动才真正生效",
   d:"前面都只是『准备好』。真正把改好的稿子提交到你知乎的，是这一步：下载这个一键程序并双击它。它会自己取凭证、领任务、逐篇提交；跑完之前别关那个黑窗口。Mac 用旁边的 Mac 版按钮（按芯片选），想让 AI 助手代跑就展开下面的『Mac 用户看这里』。"},
  {sel:"#agentBox", t:"第 4 步：把这段话发给你的 AI 助手",
   d:"云端已经算好每篇文章的最终标题和正文。把这段话复制给你的 AI 助手（Antigravity / Claude / Cursor 等），它就会在你电脑上把任务跑完 —— 你不用再做别的。写完以后云端会重新回读每篇文章逐篇复核，结果就在这一块下面。"},
  {sel:"#taskCard", t:"进度与云端复核",
   d:"修改由你电脑上的执行器完成（走你本人的网络身份），进度实时显示。完成后云端会自己回读线上文章，逐篇给出「通过 / 不通过」和原因。"},
  {sel:"#perDay", t:"每天改多少",
   d:"默认每天最多 120 篇，到量自动停止，保护账号。可以改，改完重新下载一次部署包。"},
  {sel:"#ovCard", t:"结果：修改概览",
   d:"任务开始后，这里会逐篇展示改了什么；品牌词模式下还会给出正文指纹比对，证明原有文字没被动过。"}
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
    let dots = "";
    for(let k=0;k<TOUR_STEPS.length;k++){
      dots += '<i class="'+(k===TOUR_I?'on':'')+'" onclick="tourShow('+k+')" title="第 '+(k+1)+' 步"></i>';
    }
    tip.innerHTML = '<div class="tour-hd"><span class="t-n">'+(TOUR_I+1)+'</span><b>'+st.t+'</b></div>'
      + '<p class="t-d">'+st.d+'</p>'
      + '<div class="tour-dots">'+dots+'<span class="hint">← → 切换</span></div>'
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
try{ resumeJob(); }catch(e){}
try{
  if(!localStorage.getItem("qy_tour_done")){
    setTimeout(function(){ tourShow(0); }, 1400);
  }
}catch(e){}
</script>
<style>
/* ============ v13.1 · 覆盖层修正 ============
   上一版把几处「语义不同」的类盖错了，这一层按原意改回：
   .step 是序号圆点 / .notice 是琥珀警示 / .logs·.diff 是深色终端块 /
   .zero 是绿色成功块 / .jsbox 是浅色代码框 / .scanbox 要能滚。 */
.wrap{max-width:1080px;padding:30px 18px 96px}

.step{
  display:inline-flex;align-items:center;justify-content:center;
  width:24px;height:24px;border-radius:50%;flex:none;
  background:var(--grad);color:#fff;font-size:12.5px;font-weight:750;
  box-shadow:0 5px 14px -6px rgba(37,99,235,.85);
}

.notice{
  background:linear-gradient(135deg,#fffdf5 0%,#fffbeb 68%);
  border:1px solid #fde68a;border-left:3px solid #f59e0b;border-radius:12px;
  color:#92400e;
}
.notice strong{color:#7c2d12}

.logs{
  background:#0b1220;color:#cbd5e1;border-radius:13px;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 14px 30px -16px rgba(11,18,32,.75);
}
.logs div{border-bottom:1px solid rgba(255,255,255,.07)}
.logs div:hover{background:rgba(255,255,255,.045)}
.logs div:last-child{border-bottom:none}
.logs .t{color:#64748b}

.diff{
  background:#0b1220;border-radius:12px;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.07),0 14px 30px -16px rgba(11,18,32,.75);
}
.diff .del{background:rgba(239,68,68,.16);color:#fca5a5;border-left:3px solid #ef4444}
.diff .add{background:rgba(16,185,129,.16);color:#6ee7b7;border-left:3px solid #10b981}

.jsbox{
  background:var(--bg-soft2);border:1px solid var(--line);border-radius:11px;
  color:var(--text-2);
}

.zero{background:#ecfdf5;border:1px solid #a7f3d0;color:#065f46;border-radius:12px}
.zero.warn{background:#fffbeb;border-color:#fde68a;color:#92400e}

.excerpt{
  background:var(--bg-soft2);border:1px solid var(--line);
  border-left:3px solid var(--brand);border-radius:0 10px 10px 0;
}
.detail{
  background:var(--bg-soft2);border:1px solid var(--line);border-radius:12px;
  padding:14px;margin-top:4px;color:var(--text);
}

.scanbox{overflow:auto;background:#fff;border-radius:13px}

.tabs{background:transparent;border:none;border-radius:0;padding:0}
.tab{background:#fff;border:1px solid var(--line-2)}
.tab.on{background:var(--brand-soft);border-color:#c3d8ff;color:var(--brand-2);
  box-shadow:none}

.badge{
  background:var(--brand-soft);color:var(--brand-2);border:1px solid #d8e6ff;
  box-shadow:none;
}

.chip{background:#f1f5f9;border:1px solid #e2e8f0;color:#475569}

.toast{
  background:rgba(15,23,42,.95);color:#f8fafc;border:none;border-radius:13px;
  box-shadow:0 24px 56px -18px rgba(2,6,23,.62);
  -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);
}
</style>
<style>
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
</style>

<script>
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


<script>
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
</script>
</body>
</html>
"""


def get_page() -> str:
    """返回页面 HTML，并把站点密钥注入到脚本常量（不在静态文件里硬编码）。"""
    import os
    key = os.environ.get("QY_SITE_KEY", "guanjun2026")
    return QY_PAGE_HTML.replace("__QY_SITE_KEY__", key)
