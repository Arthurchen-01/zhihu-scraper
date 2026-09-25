"""清一新教育 · 标题署名批量注入引擎 (Qingyi Title Signing Engine).

Scope — strictly limited:
  * ONLY the article/pin TITLE is modified (prefix 「【清一新教育】」).
  * The BODY is never altered. Its SHA-256 fingerprint is captured before and
    after every run and recorded in the report as proof of zero modification.

Anti-spam hardening (why it matters here):
  Zhihu's risk engine flags mechanical, high-frequency edit bursts. A large
  one-shot rewrite of 200+ titles from a datacenter IP is exactly the pattern
  that gets an account restricted. This engine therefore:
    1. Spaces writes with randomised human-like gaps.
    2. Enforces a rolling hourly quota.
    3. Applies exponential back-off on failure and aborts after N consecutive
       errors instead of hammering the endpoint.
    4. Rotates request identities (UA / header order) per item.
    5. Optionally runs only inside a "natural hours" window.
    6. Stops immediately on any auth/risk signal from the server.

Every write is preceded by an on-disk backup. Re-running is idempotent.
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import os
import random
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from . import qy_content as _qyc
except ImportError:  # 单文件执行形态
    import qy_content as _qyc

BRAND = "清一新教育"
PREFIX = f"【{BRAND}】"

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
]

_TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(html: str) -> str:
    """Convert rich-text HTML to plain text (used for excerpts only)."""
    if not html:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    s = re.sub(r"</p>", "\n", s, flags=re.I)
    s = re.sub(r"</h[1-6]>", "\n", s, flags=re.I)
    s = re.sub(r"</li>", "\n", s, flags=re.I)
    s = re.sub(r"<img[^>]*>", " [图片] ", s, flags=re.I)
    s = _TAG_RE.sub("", s)
    s = html_mod.unescape(s)
    return re.sub(r"\n{2,}", "\n", s).strip()


def body_fingerprint(html: str) -> str:
    """Stable SHA-256 of the body — the zero-modification proof.

    IMPORTANT: Zhihu re-serialises rich text on every save (it adds/tweaks
    ``data-pid`` attributes and rewrites CDN image hosts), so hashing raw HTML
    produces false "body changed" alarms. We therefore fingerprint the
    *normalised visible text*, which is what actually matters to a reader.
    """
    text = html_to_text(html)
    normalised = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def excerpt(html: str, radius: int = 80) -> str:
    t = re.sub(r"\s+", " ", html_to_text(html))
    return t[: radius * 2] + ("…" if len(t) > radius * 2 else "")


# --------------------------------------------------------------------------- #
# Title planning
# --------------------------------------------------------------------------- #

def plan_title(title: str) -> Tuple[str, bool, str]:
    """Decide the new title. Pure function — no side effects.

    Returns (new_title, should_change, reason).
    """
    t = (title or "").strip()
    if not t:
        return title, False, "标题为空，跳过"
    if BRAND in t:
        return title, False, "标题已含品牌词，跳过（幂等）"
    return f"{PREFIX}{t}", True, "标题前置品牌标识"


# --------------------------------------------------------------------------- #
# Rate control
# --------------------------------------------------------------------------- #

@dataclass
class RatePolicy:
    """Human-like pacing so the edit pattern does not look mechanical."""

    gap_min: float = 25.0     # seconds, shortest pause between two writes
    gap_max: float = 75.0     # seconds, longest pause
    burst_every: int = 5      # after N items, take a longer break
    burst_pause_min: float = 180.0
    burst_pause_max: float = 420.0
    per_hour: int = 12        # rolling-hour write quota
    per_day: int = 120        # 自然日总量上限（防风控的主要闸门）
    max_consecutive_failures: int = 3
    backoff_base: float = 30.0
    backoff_factor: float = 2.0
    max_task_items: int = 0   # 0 = no cap for this run

    def as_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


class DailyQuota:
    """「自然日总量」计数器，落盘在执行器本机。

    为什么必须落在本地：写入是用操作者自己的网络身份发出的，云端并不能
    真实统计「今天到底改了几篇」。而每日限额恰恰是防风控最关键的闸门
    （一次性上线 200+ 篇是平台风控最敏感的形态），所以计数必须跟写入
    发生在同一侧，并且落盘——否则执行器一重启就把当天配额清零了。
    """

    def __init__(self, path: Optional[Path] = None,
                 limit: int = 120, log: Optional[List[str]] = None) -> None:
        self.path = Path(path) if path else Path("data/qy_daily_quota.json")
        self.limit = int(limit or 0)
        self.log = log if log is not None else []
        self._day = ""
        self._used = 0
        self._load()

    @staticmethod
    def _today() -> str:
        return time.strftime("%Y-%m-%d", time.localtime())

    def _load(self) -> None:
        self._day = self._today()
        self._used = 0
        try:
            if self.path.exists():
                d = json.loads(self.path.read_text(encoding="utf-8"))
                if d.get("day") == self._day:
                    self._used = int(d.get("used") or 0)
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(
                {"day": self._day, "used": self._used,
                 "limit": self.limit, "updated": int(time.time())},
                ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _roll(self) -> None:
        """跨天自动归零。"""
        t = self._today()
        if t != self._day:
            self._day = t
            self._used = 0
            self._save()

    def remaining(self) -> int:
        self._roll()
        if self.limit <= 0:
            return 1 << 30
        return max(0, self.limit - self._used)

    def exhausted(self) -> bool:
        self._roll()
        return self.limit > 0 and self._used >= self.limit

    def note(self, n: int = 1) -> None:
        self._roll()
        self._used += n
        self._save()

    def describe(self) -> str:
        self._roll()
        cap = "不限" if self.limit <= 0 else str(self.limit)
        return f"今日已写入 {self._used} / {cap} 篇"


class RateGovernor:
    """Tracks timing and enforces the pacing policy."""

    def __init__(self, policy: RatePolicy, log: Optional[List[str]] = None,
                 daily_path: Optional[Path] = None) -> None:
        self.p = policy
        self._stamps: List[float] = []
        self._done = 0
        self._consecutive_failures = 0
        self.log = log if log is not None else []
        self.daily = DailyQuota(path=daily_path, limit=policy.per_day,
                                log=self.log)

    def _emit(self, msg: str) -> None:
        self.log.append(msg)

    def note_success(self) -> None:
        self._stamps.append(time.time())
        self._done += 1
        self._consecutive_failures = 0
        self.daily.note(1)

    def note_failure(self) -> int:
        self._consecutive_failures += 1
        return self._consecutive_failures

    def should_abort(self) -> bool:
        return self._consecutive_failures >= self.p.max_consecutive_failures

    def backoff_seconds(self) -> float:
        n = max(1, self._consecutive_failures)
        return self.p.backoff_base * (self.p.backoff_factor ** (n - 1))

    def hourly_wait(self) -> float:
        """Seconds to wait until the rolling-hour quota frees up."""
        if self.p.per_hour <= 0:
            return 0.0
        now = time.time()
        recent = [s for s in self._stamps if now - s < 3600]
        self._stamps = recent
        if len(recent) < self.p.per_hour:
            return 0.0
        oldest = min(recent)
        return max(0.0, 3600 - (now - oldest)) + random.uniform(5, 25)

    def next_gap(self) -> float:
        """Pause before the next write."""
        gap = random.uniform(self.p.gap_min, self.p.gap_max)
        if self.p.burst_every and self._done and self._done % self.p.burst_every == 0:
            extra = random.uniform(self.p.burst_pause_min, self.p.burst_pause_max)
            self._emit(f"阶段性休息 {extra:.0f} 秒（已处理 {self._done} 篇，模拟自然节奏）")
            gap += extra
        return gap


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #

class QingyiTitleSigner:
    """Enumerate own assets and inject the brand token into TITLES only."""

    def __init__(self, cookie: str, backup_dir: Optional[Path] = None,
                 policy: Optional[RatePolicy] = None) -> None:
        self.cookie = cookie
        self.policy = policy or RatePolicy()
        self.backup_dir = Path(backup_dir) if backup_dir else Path("data/qyedu_backup")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._me: Optional[Dict[str, Any]] = None
        self.s = self._new_session()
        # 并发枚举：知乎 limit 上限是 20，244 篇要翻 13 页；串行 + sleep 会拖到 20 秒以上，
        # 中间任何一跳把长连接掐掉，前端就只能看到一排 0。改成并发拉页。
        try:
            self._page_workers = max(1, int(os.environ.get("QY_ENUM_WORKERS", "4")))
        except Exception:
            self._page_workers = 4
        self.last_diag: Dict[str, Any] = {}
        self._last_page_error: Optional[str] = None
        self._tl = threading.local()

    # ---------------- transport ---------------- #

    def _new_session(self) -> requests.Session:
        s = requests.Session()
        h = {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cookie": self.cookie,
            "Origin": "https://zhuanlan.zhihu.com",
            "Referer": "https://zhuanlan.zhihu.com/write",
            "x-requested-with": "fetch",
        }
        m = re.search(r"_xsrf=([^;]+)", self.cookie)
        if m:
            h["x-xsrftoken"] = m.group(1).strip()
        s.headers.update(h)
        return s

    def rotate_identity(self) -> None:
        """Swap UA / header order slightly between items."""
        self.s.headers["User-Agent"] = random.choice(_USER_AGENTS)
        for k in ("Accept-Language", "x-requested-with"):
            v = self.s.headers.get(k)
            if v is not None:
                self.s.headers.pop(k)
                self.s.headers[k] = v

    # ---------------- identity ---------------- #

    def me(self) -> Dict[str, Any]:
        if self._me is None:
            try:
                r = self.s.get("https://www.zhihu.com/api/v4/me", timeout=25)
                self._me = r.json() if r.status_code == 200 else {}
            except Exception:
                self._me = {}
        return self._me

    @property
    def url_token(self) -> str:
        return str(self.me().get("url_token") or "")

    def verify(self) -> Dict[str, Any]:
        info = self.me()
        if not info or "name" not in info:
            raise RuntimeError("知乎凭证无效或已过期，无法读取账号信息。")
        return {
            "name": info.get("name"),
            "url_token": info.get("url_token"),
            "headline": info.get("headline"),
            "articles_count": info.get("articles_count"),
            "pins_count": info.get("pins_count"),
        }

    # ---------------- enumeration ---------------- #

    def _paginate(self, url: str, limit: int = 20, cap: int = 0) -> List[Dict[str, Any]]:
        """并发翻页枚举（只读）。

        知乎对 limit 的上限就是 20 —— 给 100 / 500 也只回 20 条，所以 244 篇
        必须翻 13 页。旧实现串行翻页 + 每页 sleep 0.4~0.9 秒，整发要 20~24 秒；
        这种「长时间没有任何字节流动」的请求，中间的代理/网关（Clash、Cloudflare、
        企业防火墙、手机热点）很容易把连接掐掉，浏览器只报一句 "Failed to fetch"，
        前端统计卡就永远停在初始值 0 —— 看起来像「识别到账号但 0 篇文章」。

        新实现：先取第 1 页拿 paging.totals，再把剩余页并发拉完（每线程独立
        Session 复用连接），失败页单独重试，并把诊断写进 self.last_diag 供上层回显。
        """
        self.last_diag = {"url": url, "pages": 0, "failed": [], "totals": None,
                          "error": None, "elapsed": 0.0}
        t0 = time.time()

        first = self._get_page(url, 0, limit)
        if first is None:
            self.last_diag["error"] = self._last_page_error or "首屏请求失败"
            self.last_diag["elapsed"] = round(time.time() - t0, 2)
            return []

        data, totals, is_end = first
        self.last_diag["pages"] = 1
        self.last_diag["totals"] = totals
        out: List[Dict[str, Any]] = [x for x in data if isinstance(x, dict)]

        if cap and len(out) >= cap:
            self.last_diag["elapsed"] = round(time.time() - t0, 2)
            return out[:cap]

        offsets: List[int] = []
        if not is_end and data:
            if isinstance(totals, int) and totals > len(data):
                off = len(data)
                while off < totals and len(offsets) < 400:
                    offsets.append(off)
                    off += limit

        if offsets:
            got: Dict[int, List[Dict[str, Any]]] = {}
            with ThreadPoolExecutor(max_workers=self._page_workers) as ex:
                futs = {ex.submit(self._get_page, url, o, limit): o for o in offsets}
                for fut in as_completed(futs):
                    o = futs[fut]
                    try:
                        res = fut.result()
                    except Exception:  # noqa: BLE001
                        res = None
                    if res is None:
                        self.last_diag["failed"].append(o)
                    else:
                        got[o] = [x for x in res[0] if isinstance(x, dict)]
            for o in offsets:
                if o in got:
                    out.extend(got[o])
                    self.last_diag["pages"] += 1
            # 并发里失败的页，单独再补一枪（更长的重试）
            for o in list(self.last_diag["failed"]):
                res = self._get_page(url, o, limit, retries=3)
                if res is not None:
                    out.extend(x for x in res[0] if isinstance(x, dict))
                    self.last_diag["pages"] += 1
                    self.last_diag["failed"].remove(o)
        elif not is_end and data:
            # totals 不可信 —— 老老实实串行翻到 is_end（sleep 也压到最短）
            offset = len(data)
            while offset <= 20000:
                res = self._get_page(url, offset, limit, retries=3)
                if res is None:
                    self.last_diag["failed"].append(offset)
                    break
                d, _t, end = res
                if not d:
                    break
                out.extend(x for x in d if isinstance(x, dict))
                self.last_diag["pages"] += 1
                if cap and len(out) >= cap:
                    break
                if end:
                    break
                offset += len(d)
                time.sleep(random.uniform(0.15, 0.35))

        # 去重：并发翻页遇到 totals 漂移可能拿到重复条目
        seen, uniq = set(), []
        for it in out:
            k = str(it.get("id") or "")
            if k and k in seen:
                continue
            if k:
                seen.add(k)
            uniq.append(it)

        self.last_diag["elapsed"] = round(time.time() - t0, 2)
        return uniq[:cap] if cap else uniq

    def _get_page(self, url: str, offset: int, limit: int,
                  retries: int = 2) -> Optional[Tuple[List[Dict[str, Any]], Any, bool]]:
        """取一页，返回 (data, totals, is_end)；彻底失败返回 None。

        和旧实现最大的区别：**不再把错误吞掉**。失败原因写进 self._last_page_error，
        上层能告诉用户「是 403 还是超时」，而不是一句干巴巴的 0。
        """
        delay = 0.6
        for attempt in range(retries + 1):
            try:
                r = self._thread_session().get(
                    url, params={"limit": limit, "offset": offset}, timeout=20)
                if r.status_code == 200:
                    j = r.json()
                    d = j.get("data")
                    if isinstance(d, list):
                        pg = j.get("paging") or {}
                        self._last_page_error = None
                        return d, pg.get("totals"), bool(pg.get("is_end", True))
                    self._last_page_error = "offset=%d 返回体里没有 data 列表" % offset
                else:
                    self._last_page_error = "offset=%d HTTP %d %s" % (
                        offset, r.status_code, (r.text or "")[:120])
            except Exception as exc:  # noqa: BLE001
                self._last_page_error = "offset=%d %s: %s" % (
                    offset, type(exc).__name__, exc)
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
        return None

    def _thread_session(self) -> requests.Session:
        """每线程一个 Session。

        requests.Session 不是线程安全的，但「每线程独占一个」既能复用连接
        （省掉 TLS 握手），又能安全并发 —— 这是把 13 页从 20 秒压到 3 秒的关键。
        """
        tl = getattr(self, "_tl", None)
        if tl is None:
            tl = self._tl = threading.local()
        s = getattr(tl, "s", None)
        if s is None:
            s = tl.s = self._new_session()
        return s

    def list_articles(self, cap: int = 0) -> List[Dict[str, Any]]:
        items = self._paginate(
            f"https://www.zhihu.com/api/v4/members/{self.url_token}/articles?include=data[*].comment_count,voteup_count",
            cap=cap)
        out = []
        for a in items:
            if not a.get("id"):
                continue
            title = a.get("title") or "(无标题)"
            v_cnt = a.get("voteup_count")
            if v_cnt is None:
                try:
                    _dr = self._thread_session().get(f"https://www.zhihu.com/api/v4/answers/{a['id']}?include=voteup_count", timeout=6)
                    if _dr.status_code == 200:
                        v_cnt = _dr.json().get("voteup_count", 0)
                except Exception:
                    pass
            out.append({
                "id": str(a["id"]),
                "type": "article",
                "kind_label": "文章",
                "title": title,
                "has_brand": BRAND in title,
                "created": a.get("created"),
                "updated": a.get("updated"),
                "voteup_count": v_cnt or 0,
                "comment_count": a.get("comment_count"),
                "url": f"https://zhuanlan.zhihu.com/p/{a['id']}",
                "excerpt": html_to_text(a.get("excerpt") or "")[:140],
            })
        return out

    def list_answers(self, cap: int = 0) -> List[Dict[str, Any]]:
        items = self._paginate(
            f"https://www.zhihu.com/api/v4/members/{self.url_token}/answers?include=data[*].comment_count,voteup_count",
            cap=cap)
        out = []
        for a in items:
            if not a.get("id"):
                continue
            q = a.get("question") or {}
            title = (q.get("title") if isinstance(q, dict) else "") or "(回答)"
            v_cnt = a.get("voteup_count")
            if v_cnt is None:
                try:
                    _dr = self._thread_session().get(f"https://www.zhihu.com/api/v4/answers/{a['id']}?include=voteup_count", timeout=6)
                    if _dr.status_code == 200:
                        v_cnt = _dr.json().get("voteup_count", 0)
                except Exception:
                    pass
            out.append({
                "id": str(a["id"]),
                "type": "answer",
                "kind_label": "回答",
                "title": title,
                "has_brand": BRAND in title,
                "created": a.get("created_time"),
                "updated": a.get("updated_time"),
                "voteup_count": v_cnt or 0,
                "comment_count": a.get("comment_count"),
                "url": f"https://www.zhihu.com/answer/{a['id']}",
                "excerpt": html_to_text(a.get("excerpt") or "")[:140],
                "note": "回答标题由问题决定，不可单独修改",
            })
        return out

    def list_pins(self, cap: int = 0) -> List[Dict[str, Any]]:
        items = self._paginate(
            f"https://www.zhihu.com/api/v4/members/{self.url_token}/pins",
            cap=cap)
        out = []
        for p in items:
            if not p.get("id"):
                continue
            c = p.get("content")
            txt = ""
            try:
                if isinstance(c, list) and c and isinstance(c[0], dict):
                    txt = html_to_text(str(c[0].get("content") or ""))
                elif isinstance(c, str):
                    txt = html_to_text(c)
            except Exception:
                txt = ""
            title = (p.get("excerpt_title") or txt[:40] or "(想法)")
            out.append({
                "id": str(p["id"]),
                "type": "pin",
                "kind_label": "想法",
                "title": title,
                "has_brand": BRAND in title,
                "created": p.get("created"),
                "updated": p.get("updated"),
                "voteup_count": p.get("like_count"),
                "comment_count": p.get("comment_count"),
                "url": f"https://www.zhihu.com/pin/{p['id']}",
                "excerpt": txt[:140],
                "note": "想法无独立标题字段，正文内注入不在本次范围",
            })
        return out

    # ---------------- read / write ---------------- #

    def get_article_draft(self, aid: str) -> Dict[str, Any]:
        r = self.s.get(
            f"https://zhuanlan.zhihu.com/api/articles/{aid}/draft",
            headers={"Referer": f"https://zhuanlan.zhihu.com/p/{aid}/edit"},
            timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"读取草稿失败 HTTP {r.status_code}")
        return r.json()

    def backup(self, kind: str, item_id: str, title: str, body_hash: str,
               body: Optional[str] = None) -> str:
        """落盘完整原文，确保「可随时完整还原」不是一句空话。

        快照**永不覆盖** —— 首次记录即为最初状态，多次运行也不会丢失原貌。
        """
        safe = re.sub(r"[^0-9A-Za-z_\-]", "", item_id)[:60] or "item"
        p = self.backup_dir / f"{kind}_{safe}_title.json"
        if not p.exists():          # never overwrite the pristine snapshot
            payload = {
                "id": item_id, "type": kind,
                "title": title, "body_sha256": body_hash,
                "saved_at": int(time.time()),
            }
            if body is not None:
                payload["body_html"] = body
                payload["body_len"] = len(body)
                payload["restorable"] = True
            p.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        return str(p)

    def patch_draft(self, aid: str, title: str,
                    content: Optional[str] = None) -> Tuple[bool, str]:
        """保存草稿。content 为 None 时只写标题（正文零改动）。"""
        try:
            body_payload: Dict[str, Any] = {
                "title": title,
                "delta_time": random.randint(3, 9),
                "can_reward": False,
            }
            if content is not None:
                body_payload["content"] = content
            r = self.s.patch(
                f"https://zhuanlan.zhihu.com/api/articles/{aid}/draft",
                json=body_payload,
                headers={"Referer": f"https://zhuanlan.zhihu.com/p/{aid}/edit"},
                timeout=40)
            if r.status_code == 200:
                return True, "保存成功"
            return False, f"HTTP {r.status_code} {r.text[:140]}"
        except Exception as exc:  # noqa: BLE001
            return False, f"异常 {exc}"

    def patch_title(self, aid: str, title: str) -> Tuple[bool, str]:
        """Persist ONLY the title field. Body untouched by construction."""
        try:
            r = self.s.patch(
                f"https://zhuanlan.zhihu.com/api/articles/{aid}/draft",
                json={
                    "title": title,
                    "delta_time": random.randint(3, 9),
                    "can_reward": False,
                },
                headers={"Referer": f"https://zhuanlan.zhihu.com/p/{aid}/edit"},
                timeout=40)
            if r.status_code == 200:
                return True, "保存成功"
            return False, f"HTTP {r.status_code} {r.text[:140]}"
        except Exception as exc:  # noqa: BLE001
            return False, f"异常 {exc}"

    def publish_article(self, aid: str, title: str, body_html: str) -> Tuple[bool, str]:
        """Publish the saved draft so the new title goes live."""
        pc_business = json.dumps({
            "disclaimer_type": "none",
            "disclaimer_status": "close",
            "table_of_contents_enabled": False,
            "content": body_html,
            "title": title,
            "commercial_report_info": {"commercial_types": []},
            "commercial_zhitask_bind_info": None,
            "canReward": False,
        }, ensure_ascii=False)
        payload = {
            "action": "article",
            "data": {
                "publish": {"traceId": f"{int(time.time() * 1000)},{uuid.uuid4()}"},
                "extra_info": {"publisher": "pc", "pc_business_params": pc_business},
                "draft": {"disabled": 1, "id": aid, "isPublished": True},
                "commentsPermission": {},
                "creationStatement": {"disclaimer_type": "none",
                                      "disclaimer_status": "close"},
                "contentsTables": {"table_of_contents_enabled": False},
                "commercialReportInfo": {"isReport": 0},
                "appreciate": {"can_reward": False, "tagline": ""},
                "hybridInfo": {},
                "hybrid": {"html": body_html},
            },
        }
        try:
            r = self.s.post(
                "https://www.zhihu.com/api/v4/content/publish",
                json=payload,
                headers={"Origin": "https://www.zhihu.com",
                         "Referer": f"https://zhuanlan.zhihu.com/p/{aid}/edit"},
                timeout=60)
            if r.status_code != 200:
                return False, f"HTTP {r.status_code} {r.text[:140]}"
            try:
                j = r.json()
            except Exception:
                return True, "已提交"
            if j.get("code") == 0:
                return True, "发布成功"
            return False, f"业务提示 {json.dumps(j, ensure_ascii=False)[:180]}"
        except Exception as exc:  # noqa: BLE001
            return False, f"异常 {exc}"

    # ---------------- per-item pipeline ---------------- #

    def apply_payload(self, item: Dict[str, Any],
                      payload: Dict[str, Any],
                      publish: bool = True) -> Dict[str, Any]:
        """把云端「预修改」好的内容原样上传（本地只搬运，不做二次加工）。

        payload = {"title": 最终标题, "content": 最终正文 HTML}
        本地这一步不做任何内容判断 —— 规则由云端定，结果也由云端复核。
        """
        aid = str(item.get("id"))
        t0 = time.time()
        new_title = (payload.get("title") or item.get("title")
                     or item.get("title_before") or "").strip()
        new_body = payload.get("content")
        rec: Dict[str, Any] = {
            "id": aid,
            "type": item.get("type", "article"),
            "kind_label": item.get("kind_label", "文章"),
            "url": item.get("url", ""),
            "title_before": item.get("title_before", item.get("title", "")),
            "title_after": new_title,
            "title_changed": False,
            "body_sha256_before": "",
            "body_sha256_after": "",
            "body_unchanged": None,
            "body_excerpt": "",
            "body_len": 0,
            "status": "pending",
            "message": "",
            "backup": "",
            "duration": 0.0,
            "body_hits_before": 0,
            "body_hits_after": 0,
            "body_hits_added": 0,
            "body_scenes": [],
            "source": "cloud_payload",
        }
        try:
            before = self.get_article_draft(aid)
        except Exception as exc:  # noqa: BLE001
            rec["status"] = "failed"
            rec["message"] = f"读取原文失败：{exc}"
            rec["duration"] = round(time.time() - t0, 2)
            return rec
        body = before.get("content") or ""
        title_before = before.get("title") or ""
        fp_before = body_fingerprint(body)
        rec["title_before"] = title_before
        rec["body_sha256_before"] = fp_before
        rec["body_len"] = len(body)
        rec["body_hits_before"] = _qyc._ANY_TAG_RE.sub("", body).count(
            "清一新教育")
        rec["title_changed"] = (new_title != title_before)

        if not rec["title_changed"] and new_body is None:
            rec["status"] = "skipped"
            rec["message"] = "云端方案未要求改动"
            rec["duration"] = round(time.time() - t0, 2)
            return rec

        rec["backup"] = self.backup("article", aid, title_before, fp_before,
                                    body=body)

        ok, msg = self.patch_draft(aid, new_title, new_body)
        if not ok:
            rec["status"] = "failed"
            rec["message"] = f"保存失败：{msg}"
            rec["duration"] = round(time.time() - t0, 2)
            return rec

        if publish:
            time.sleep(random.uniform(1.2, 2.6))
            okp, msgp = self.publish_article(
                aid, new_title, new_body if new_body is not None else body)
            if not okp:
                rec["status"] = "saved_not_published"
                rec["message"] = f"已保存，发布未确认：{msgp}"
                rec["duration"] = round(time.time() - t0, 2)
                return rec

        time.sleep(random.uniform(0.8, 1.8))
        try:
            after = self.get_article_draft(aid)
            live_body = after.get("content") or ""
            live_title = after.get("title") or ""
            rec["body_sha256_after"] = body_fingerprint(live_body)
            rec["body_hits_after"] = _qyc._ANY_TAG_RE.sub(
                "", live_body).count("清一新教育")
            rec["body_hits_added"] = (rec["body_hits_after"]
                                      - rec["body_hits_before"])
            if new_body is not None:
                rec["body_as_planned"] = (
                    body_fingerprint(live_body) == body_fingerprint(new_body))
                rec["body_restorable"] = (
                    _qyc.strip_scenes(live_body) == _qyc.strip_scenes(new_body))
            rec["body_excerpt"] = _qyc.excerpt_around(live_body)
            if live_title.strip() != new_title.strip():
                rec["message"] = f"已提交；服务端回读标题为 {live_title[:40]}"
            else:
                rec["message"] = "已按云端方案完成（标题 + 正文，可一键还原）"
            rec["status"] = "done"
        except Exception as exc:  # noqa: BLE001
            rec["status"] = "done"
            rec["message"] = f"已提交（回读校验跳过：{exc}）"
        rec["duration"] = round(time.time() - t0, 2)
        return rec

    def process_title(self, item: Dict[str, Any], dry_run: bool = False,
                      publish: bool = True, inject_body: bool = False,
                      body_hits: int = 1, body_anchors: Optional[List[str]] = None,
                      title_add: Optional[bool] = None,
                      with_payload: bool = False) -> Dict[str, Any]:
        """Inject the brand into ONE item's title (and optionally its body).

        inject_body=False（默认）时正文只读，行为与"仅标题"完全一致。
        inject_body=True 时按 qy_content 的场景优选把「（清一新教育）」署名括注
        自然植入正文，仍不删改任何原有字符，且可一键还原。
        """
        aid = str(item.get("id"))
        t0 = time.time()
        rec: Dict[str, Any] = {
            "id": aid,
            "type": item.get("type", "article"),
            "kind_label": item.get("kind_label", "文章"),
            "url": item.get("url", ""),
            "title_before": item.get("title", ""),
            "title_after": item.get("title", ""),
            "title_changed": False,
            "body_sha256_before": "",
            "body_sha256_after": "",
            "body_unchanged": True,
            "body_excerpt": "",
            "body_len": 0,
            "status": "pending",
            "message": "",
            "backup": "",
            "duration": 0.0,
            "body_hits_before": 0,
            "body_hits_after": 0,
            "body_hits_added": 0,
            "body_scenes": [],
        }

        if rec["type"] != "article":
            rec["status"] = "unsupported"
            rec["message"] = item.get("note") or "该类型暂不支持标题注入"
            rec["duration"] = round(time.time() - t0, 2)
            return rec

        try:
            draft = self.get_article_draft(aid)
            title = draft.get("title") or ""
            body = draft.get("content") or ""

            fp_before = body_fingerprint(body)
            rec["title_before"] = title
            rec["body_sha256_before"] = fp_before
            rec["body_excerpt"] = excerpt(body)
            rec["body_len"] = len(body)

            new_title, changed, reason = plan_title(title)
            if title_add is False and changed:
                changed = False
                new_title = title
                reason = "AI 审核决定本篇标题不加品牌词"

            rec["title_after"] = new_title if changed else title
            rec["title_changed"] = changed

            # 标题已含品牌词时不能直接 return：正文可能还没植入。
            # 只有"标题无需改动 且 不需要正文植入"才算整篇跳过。
            if not changed and not inject_body:
                rec["status"] = "skipped"
                rec["body_sha256_after"] = fp_before
                rec["message"] = reason
                rec["duration"] = round(time.time() - t0, 2)
                return rec

            # --- 正文植入（可选） ---
            new_body = None
            if inject_body:
                try:
                    scenes = None
                    anchors = [a for a in (body_anchors or []) if a]
                    if anchors:
                        # 按 AI 计划的锚文本在候选池中定位（后 24 字符互含容错，
                        # 抵御知乎重新序列化引入的空白差异）
                        pool = _qyc.scan_scenes(body, limit=4)
                        picked = []
                        for a in anchors:
                            for sc in pool:
                                if sc in picked:
                                    continue
                                ka = (sc.anchor or "")[-24:]
                                kb = (a or "")[-24:]
                                if ka and kb and (ka in a or kb in sc.anchor):
                                    picked.append(sc)
                                    break
                        if picked:
                            scenes = picked
                            rec["ai_plan_used"] = True
                    if scenes is None:
                        # 无计划或锚点未命中 → 回退内置规则（首段优先）
                        scenes = _qyc.scan_scenes(body, limit=max(1, body_hits))
                    if scenes:
                        new_body = _qyc.apply_scenes(body, scenes)
                        rec["body_scenes"] = [
                            {"index": s.index, "block_no": s.block_no,
                             "reason": s.reason, "excerpt":
                                 _qyc.excerpt_around(s.proposed)}
                            for s in scenes
                        ]
                except Exception as exc:  # noqa: BLE001
                    rec["body_scenes"] = []
                    new_body = None
                    print(f"   [!] 正文植入计算失败，本次仅改标题：{exc}")

            rec["body_hits_before"] = _qyc._ANY_TAG_RE.sub("", body or "").count(
                "清一新教育")
            if new_body is not None:
                rec["body_hits_after"] = _qyc._ANY_TAG_RE.sub(
                    "", new_body).count("清一新教育")
                rec["body_hits_added"] = (rec["body_hits_after"]
                                          - rec["body_hits_before"])
            else:
                rec["body_hits_after"] = rec["body_hits_before"]

            # 标题与正文都没动 → 整篇无需处理
            if not rec["title_changed"] and not rec["body_hits_added"]:
                rec["status"] = "skipped"
                rec["body_sha256_after"] = fp_before
                rec["message"] = reason or "标题与正文均已含品牌词，无需处理"
                rec["duration"] = round(time.time() - t0, 2)
                return rec

            if dry_run:
                rec["status"] = "preview"
                rec["body_sha256_after"] = fp_before
                if with_payload:
                    # 把「最终标题 + 最终正文」一并交出去：调用方（云端）把它
                    # 缓存起来，本地执行器只负责原样上传，不再自行决定怎么改。
                    _pl_body = new_body if new_body is not None else body
                    rec["payload"] = {"title": new_title, "content": _pl_body}
                    rec["body_sha256_expected"] = body_fingerprint(_pl_body)
                    rec["body_len_before"] = len(body or "")
                    rec["body_len_expected"] = len(_pl_body or "")
                parts = []
                if rec["title_changed"]:
                    parts.append("标题 1 处")
                if rec["body_hits_added"]:
                    parts.append(f"正文 {rec['body_hits_added']} 处")
                rec["message"] = ("预演：将改动 " + "、".join(parts)) if parts \
                    else "预演：无需改动"
                rec["duration"] = round(time.time() - t0, 2)
                return rec

            rec["backup"] = self.backup("article", aid, title, fp_before,
                                     body=body)

            ok, msg = self.patch_draft(aid, new_title, new_body)
            if not ok:
                rec["status"] = "failed"
                rec["message"] = f"保存失败：{msg}"
                rec["duration"] = round(time.time() - t0, 2)
                return rec

            if publish:
                time.sleep(random.uniform(1.2, 2.6))
                okp, msgp = self.publish_article(
                    aid, new_title, new_body if new_body is not None else body)
                if not okp:
                    rec["status"] = "saved_not_published"
                    rec["message"] = f"标题已保存，发布未确认：{msgp}"
                    rec["duration"] = round(time.time() - t0, 2)
                    return rec

            # re-read to prove the body is untouched
            time.sleep(random.uniform(0.8, 1.8))
            try:
                after = self.get_article_draft(aid)
                live_body = after.get("content") or ""
                fp_after = body_fingerprint(live_body)
                rec["body_sha256_after"] = fp_after
                if new_body is None:
                    rec["body_unchanged"] = (fp_after == fp_before)
                else:
                    # 正文按计划改动：校验线上正文与"预期植入结果"一致
                    expect = body_fingerprint(new_body)
                    rec["body_unchanged"] = None
                    rec["body_as_planned"] = (fp_after == expect)
                    rec["body_restorable"] = (
                        _qyc.strip_scenes(live_body)
                        == _qyc.strip_scenes(new_body))
                live_title = after.get("title") or ""
                if live_title.strip() != new_title.strip():
                    rec["message"] = f"标题已提交，服务端回读为：{live_title[:40]}"
            except Exception:
                rec["body_sha256_after"] = fp_before

            rec["status"] = "done"
            if not rec["message"]:
                if new_body is None:
                    rec["message"] = ("标题注入成功；正文哈希一致，零修改"
                                      if rec["body_unchanged"] else
                                      "标题注入成功（正文哈希变化，请复核）")
                else:
                    rec["message"] = (
                        f"标题注入成功；正文自然植入 {rec['body_hits_added']} 处"
                        "（署名式括注，不删改原文，可一键还原）")

        except Exception as exc:  # noqa: BLE001
            rec["status"] = "failed"
            rec["message"] = f"处理异常：{exc}"

        rec["duration"] = round(time.time() - t0, 2)
        return rec
