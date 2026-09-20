/**
 * 后台（MV3 classic service worker）
 *
 * 唯一职责：把本浏览器里已登录的知乎凭证同步到控制台的「凭证柜」。
 *
 * 为什么要这么做：浏览器运行时会独占锁定它自己的 Cookie 数据库，
 * 任何外部程序（Python 直读 / 复制文件 / CreateFileW / sqlite immutable）
 * 都拿不到 —— 这是操作系统层面的锁，绕不过去。
 * 而扩展是跑在浏览器内部的，读自己的 Cookie 是天经地义的，
 * 所以「先关掉浏览器」这一步就被彻底消掉了。
 */
importScripts("config.js");

// 控制台页面的真实路径（首页上的入口也指向这里；该页不需要密钥即可打开）
const CONSOLE_PATH = "/api/qy/console";

const BADGE = {
  ok: "#10b981",
  busy: "#0ea5e9",
  warn: "#f59e0b",
  err: "#ef4444"
};

function setBadge(text, color) {
  try {
    chrome.action.setBadgeText({ text: text || "" });
    if (color) chrome.action.setBadgeBackgroundColor({ color });
  } catch (e) {
    /* 扩展被卸载/重载时可能抛错，忽略 */
  }
}

async function readZhihuCookie() {
  const all = await chrome.cookies.getAll({ domain: "zhihu.com" });
  const map = new Map();
  for (const c of all) {
    if (!c || !c.name) continue;
    map.set(c.name, c.value == null ? "" : c.value);
  }
  const names = Array.from(map.keys()).sort();
  const cookie = names.map((n) => n + "=" + map.get(n)).join("; ");
  const zc0 = map.get("z_c0") || "";
  return { cookie, names, loggedIn: zc0.length > 0, sessionLen: zc0.length };
}

async function saveLast(rec) {
  try {
    await chrome.storage.local.set({ [K.LAST]: rec });
  } catch (e) {
    /* ignore */
  }
}

async function getLast() {
  try {
    const o = await chrome.storage.local.get(K.LAST);
    return o[K.LAST] || null;
  } catch (e) {
    return null;
  }
}

/** 主流程：读 Cookie → 上报云端凭证柜。 */
async function sync(trigger) {
  setBadge("…", BADGE.busy);
  const cfg = await loadCfg();

  let zk;
  try {
    zk = await readZhihuCookie();
  } catch (err) {
    const r = {
      ok: false, reason: "cookie", at: Date.now(), trigger,
      note: "读取浏览器 Cookie 失败：" + String((err && err.message) || err)
    };
    await saveLast(r);
    setBadge("!", BADGE.err);
    return r;
  }

  if (!zk.loggedIn) {
    const r = {
      ok: false, reason: "no_login", at: Date.now(), trigger,
      cookies: zk.names.length,
      note: "这个浏览器里没有知乎登录态（缺少 z_c0）。"
          + "请先用本浏览器打开 zhihu.com 并登录，然后再点一次同步。"
    };
    await saveLast(r);
    setBadge("!", BADGE.warn);
    return r;
  }

  // 顺带把云端记录的「每日上限」一起带上，保证与网页上的选择一致
  let perDay = 0;
  try {
    const cr = await fetch(cfg.server + "/api/qy/config", {
      headers: { "X-API-Key": cfg.key, "Accept": "application/json" },
      cache: "no-store"
    });
    if (cr.ok) {
      const cj = await cr.json();
      if (cj && cj.ok) perDay = parseInt(cj.per_day, 10) || 0;
    }
  } catch (e) {
    /* 取不到就用 0（不限），不影响凭证同步 */
  }

  let res, body;
  try {
    res = await fetch(cfg.server + "/api/qy/credential-deposit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": cfg.key,
        "Accept": "application/json"
      },
      body: JSON.stringify({
        key: cfg.key,
        cookie: zk.cookie,
        note: "浏览器扩展",
        per_day: perDay
      })
    });
    body = await res.json().catch(() => ({}));
  } catch (err) {
    const r = {
      ok: false, reason: "network", at: Date.now(), trigger,
      note: "连不上控制台：" + String((err && err.message) || err)
    };
    await saveLast(r);
    setBadge("!", BADGE.err);
    return r;
  }

  if (!res.ok || !body || !body.ok) {
    const r = {
      ok: false, reason: "server", at: Date.now(), trigger,
      http: res.status,
      note: (body && (body.detail || body.note)) || ("服务端返回 HTTP " + res.status)
    };
    await saveLast(r);
    setBadge("!", BADGE.err);
    return r;
  }

  const r = {
    ok: true, at: Date.now(), trigger,
    token: body.token,
    ttl: body.ttl,
    per_day: perDay,
    cookies: zk.names.length,
    note: "已同步成功（凭证编号 " + body.token + "，云端保留 6 小时）"
  };
  await saveLast(r);
  setBadge("✓", BADGE.ok);
  return r;
}

/** 定时同步：默认每 30 分钟刷新一次，保证凭证柜里始终是新鲜的。 */
async function ensureAlarm(force) {
  const cfg = await loadCfg();
  try {
    await chrome.alarms.clear("qy-sync");
    const min = force ? 30 : (cfg.interval > 0 ? cfg.interval : 0);
    if (min > 0 && cfg.auto) {
      chrome.alarms.create("qy-sync", {
        delayInMinutes: 1,
        periodInMinutes: min
      });
    }
  } catch (e) {
    /* ignore */
  }
}

async function status() {
  const cfg = await loadCfg();
  const last = await getLast();
  let zk = null;
  try {
    zk = await readZhihuCookie();
  } catch (e) {
    /* ignore */
  }
  return {
    ok: true,
    version: QY.VERSION,
    server: cfg.server,
    auto: cfg.auto,
    interval: cfg.interval > 0 ? cfg.interval : 30,
    loggedIn: !!(zk && zk.loggedIn),
    cookies: zk ? zk.names.length : 0,
    last
  };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      if (!msg || !msg.type) return sendResponse({ ok: false });
      if (msg.type === "sync") return sendResponse(await sync("manual"));
      if (msg.type === "status") return sendResponse(await status());
      if (msg.type === "openConsole") {
        const cfg = await loadCfg();
        await chrome.tabs.create({ url: cfg.server + CONSOLE_PATH });
        return sendResponse({ ok: true });
      }
      if (msg.type === "saveCfg") {
        await ensureAlarm(true);
        return sendResponse({ ok: true });
      }
      return sendResponse({ ok: false, note: "unknown message" });
    } catch (err) {
      return sendResponse({
        ok: false,
        note: String((err && err.message) || err)
      });
    }
  })();
  return true; // 保持消息通道，异步回包
});

chrome.alarms.onAlarm.addListener((a) => {
  if (a && a.name === "qy-sync") sync("alarm");
});

chrome.runtime.onInstalled.addListener(() => {
  ensureAlarm(true);
  sync("install");
});

chrome.runtime.onStartup.addListener(() => {
  ensureAlarm(true);
  sync("startup");
});

// 登录态变化（重新登录、退出）时自动补一次同步，防抖 4 秒
let debounce = null;
chrome.cookies.onChanged.addListener((info) => {
  const c = info && info.cookie;
  if (!c) return;
  if (!/(^|\.)zhihu\.com$/.test(c.domain || "")) return;
  if (["z_c0", "_xsrf", "d_c0"].indexOf(c.name) < 0) return;
  if (debounce) clearTimeout(debounce);
  debounce = setTimeout(() => sync("cookie-change"), 4000);
});

// service worker 冷启动时补一次（例如浏览器刚打开、用户直接点图标）
ensureAlarm(true);
