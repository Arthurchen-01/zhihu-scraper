/**
 * 全扩展共用的常量与默认配置。
 * 后台（classic service worker，importScripts）与弹窗/设置页（<script src>）共用本文件。
 */
const QY = Object.freeze({
  VERSION: "1.0.0",
  // 控制台与接口所在站点
  SERVER: "https://zh.samuraiguan.cloud",
  // 站点密钥（与控制台页面里用的是同一个）
  SITE_KEY: "guanjun2026",
  // 自动同步间隔（分钟）。凭证在云端保留 6 小时，每 30 分钟刷一次足够新鲜。
  DEFAULT_INTERVAL_MIN: 30
});

// chrome.storage 里用到的键名，集中一处，避免写错
const K = Object.freeze({
  SERVER: "qy_server",
  KEY: "qy_site_key",
  INTERVAL: "qy_interval",
  AUTO: "qy_auto",
  LAST: "qy_last"
});

/** 读取配置（带默认值）。 */
async function loadCfg() {
  const got = await chrome.storage.sync.get({
    [K.SERVER]: QY.SERVER,
    [K.KEY]: QY.SITE_KEY,
    [K.INTERVAL]: QY.DEFAULT_INTERVAL_MIN,
    [K.AUTO]: true
  });
  return {
    server: (got[K.SERVER] || QY.SERVER).replace(/\/+$/, ""),
    key: got[K.KEY] || QY.SITE_KEY,
    interval: Math.max(0, parseInt(got[K.INTERVAL], 10) || 0),
    auto: got[K.AUTO] !== false
  };
}
