/**
 * 弹窗逻辑：只做「显示状态」和「点一下同步」，不放任何业务规则。
 * 真正的同步全在 background.js 里，保证关掉弹窗也能继续。
 */
const $ = (id) => document.getElementById(id);

function ago(ts) {
  if (!ts) return "从未";
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return s + " 秒前";
  if (s < 3600) return Math.floor(s / 60) + " 分钟前";
  if (s < 86400) return Math.floor(s / 3600) + " 小时前";
  return Math.floor(s / 86400) + " 天前";
}

function send(type) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type }, (r) => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, note: chrome.runtime.lastError.message });
      } else {
        resolve(r || { ok: false, note: "no response" });
      }
    });
  });
}

function paintNote(text, cls) {
  const el = $("note");
  el.className = "note" + (cls ? " " + cls : "");
  el.textContent = text;
  el.hidden = !text;
}

function render(st) {
  $("ver").textContent = "v" + (st.version || "");
  if (st.server) {
    $("btnConsole").textContent = "打开控制台（" +
      st.server.replace(/^https?:\/\//, "") + "）";
  }

  // 本浏览器登录态
  const dl = $("dotLogin");
  if (st.loggedIn) {
    dl.className = "dot d-ok";
    $("vLogin").textContent = "已登录（" + st.cookies + " 条 Cookie）";
  } else {
    dl.className = "dot d-bad";
    $("vLogin").textContent = "未登录";
  }

  // 云端凭证柜
  const ds = $("dotSync");
  const last = st.last;
  if (last && last.ok) {
    ds.className = "dot d-ok";
    $("vSync").textContent = ago(last.at);
  } else if (last) {
    ds.className = "dot d-bad";
    $("vSync").textContent = "同步失败";
  } else {
    ds.className = "dot d-idle";
    $("vSync").textContent = "未同步过";
  }

  if (last && last.ok) {
    const cap = (last.per_day === 0 || last.per_day == null)
      ? "不限" : (last.per_day + " 篇/天");
    paintNote("已同步成功（编号 " + last.token + "，"
              + ago(last.at) + "）。云端保留 6 小时，每 30 分钟自动刷新。"
              + "每日上限：" + cap + "。", "ok");
  } else if (last && last.note) {
    paintNote(last.note, last.reason === "no_login" ? "warn" : "bad");
  } else if (!st.loggedIn) {
    paintNote("这个浏览器里还没有知乎登录。请先在本浏览器打开 zhihu.com "
              + "登录，再回来点「立即同步」。", "warn");
  } else {
    paintNote("还没同步过，点下面的按钮即可。");
  }
}

async function load() {
  const st = await send("status");
  if (st && st.ok) render(st);
  else paintNote((st && st.note) || "读取状态失败", "bad");
}

$("btnSync").addEventListener("click", async () => {
  const b = $("btnSync");
  b.disabled = true;
  b.innerHTML = '<span class="spin"></span>同步中…';
  paintNote("正在把本浏览器的知乎登录送到云端…");
  const r = await send("sync");
  b.disabled = false;
  b.textContent = "立即同步到云端";
  await load();
  if (r && r.ok) paintNote(r.note || "同步完成。", "ok");
});

$("btnConsole").addEventListener("click", () => send("openConsole"));
$("btnOpt").addEventListener("click", () => chrome.runtime.openOptionsPage());
$("lnkHelp").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.tabs.create({ url: chrome.runtime.getURL("help.html") });
});

load();
