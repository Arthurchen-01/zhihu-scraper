/** 设置页：读写 chrome.storage.sync，保存后让后台重建定时器。 */
const $ = (id) => document.getElementById(id);

function flash(text, cls) {
  const m = $("msg");
  m.className = "msg" + (cls ? " " + cls : "");
  m.textContent = text;
  if (text) setTimeout(() => { m.textContent = ""; }, 2600);
}

function send(type) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type }, (r) => {
      resolve(chrome.runtime.lastError
        ? { ok: false, note: chrome.runtime.lastError.message }
        : (r || { ok: false }));
    });
  });
}

async function load() {
  const got = await chrome.storage.sync.get({
    [K.SERVER]: QY.SERVER,
    [K.KEY]: QY.SITE_KEY,
    [K.INTERVAL]: QY.DEFAULT_INTERVAL_MIN,
    [K.AUTO]: true
  });
  $("server").value = got[K.SERVER];
  $("key").value = got[K.KEY];
  $("interval").value = got[K.INTERVAL];
  $("auto").checked = got[K.AUTO] !== false;

  const st = await send("status");
  const lines = [];
  lines.push("扩展版本：" + QY.VERSION);
  if (st && st.ok) {
    lines.push("本浏览器知乎登录：" + (st.loggedIn
      ? "已登录（读到 " + st.cookies + " 条 Cookie）"
      : "未登录 —— 请先在本浏览器登录 zhihu.com"));
    lines.push("定时同步：" + (st.auto
      ? "开启，每 " + st.interval + " 分钟一次" : "已关闭"));
    const last = st.last;
    if (last && last.ok) {
      lines.push("上次同步：成功，凭证编号 " + last.token + "，"
        + new Date(last.at).toLocaleString());
    } else if (last) {
      lines.push("上次同步：失败 —— " + last.note);
    } else {
      lines.push("上次同步：还没有同步过");
    }
  } else {
    lines.push("读取后台状态失败：" + ((st && st.note) || "未知"));
  }
  $("status").textContent = lines.join("\n");
}

$("save").addEventListener("click", async () => {
  const server = $("server").value.trim().replace(/\/+$/, "") || QY.SERVER;
  const key = $("key").value.trim() || QY.SITE_KEY;
  let interval = parseInt($("interval").value, 10);
  if (!interval || interval < 5) interval = 30;
  if (interval > 360) interval = 360;
  await chrome.storage.sync.set({
    [K.SERVER]: server,
    [K.KEY]: key,
    [K.INTERVAL]: interval,
    [K.AUTO]: $("auto").checked
  });
  flash("已保存", "ok");
  await load();
});

$("test").addEventListener("click", async () => {
  flash("同步中…");
  const r = await send("sync");
  flash(r && r.ok ? "同步成功" : ("失败：" + ((r && r.note) || "未知")),
        r && r.ok ? "ok" : "");
  await load();
});

$("auto").addEventListener("change", () => {
  $("save").click();
});

load();
