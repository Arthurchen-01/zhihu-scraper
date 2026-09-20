# -*- coding: utf-8 -*-
"""清一新教育 · 一键修改程序（Windows 单文件版）

给最终用户的东西只有这一个 .exe：
    双击 → 取得登录态 → 同步云端 → 请云端算好最终稿 → 自动开始修改。

登录态有两条路，自动选：
    A. 浏览器扩展「清一新教育 · 修改助手」把本机登录同步进了云端凭证柜
       → 直接取用。**浏览器可以一直开着**，程序不碰它的 Cookie 数据库。
    B. 没装扩展 → 回退到直接读本机浏览器的登录数据（此时需要关掉浏览器，
       因为浏览器会独占锁定 Cookie 数据库）。

刻意*不需要*用户做这些事：
    · 不需要解压（就一个文件）
    · 不需要打开终端、不需要敲任何命令
    · 不需要安装 Python、不需要 pip install
    · 不需要粘贴 Cookie、不需要 F12

工作文件（cookie / 每日计数 / 原文备份）落在固定的用户目录，而不是 exe 旁边 ——
因为 PyInstaller 单文件模式每次运行都把自身解压到一个新的临时目录，
放在 exe 旁边的文件每次运行都会"消失"。
"""

import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVER = "https://zh.samuraiguan.cloud"
SITE_KEY = "guanjun2026"
MAX_TRY = 5
DEFAULT_PER_DAY = 120
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def work_dir() -> Path:
    """持久工作目录：绝不能用 exe 所在目录（单文件模式是临时目录）。"""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    d = (Path(base) if base else Path.home()) / "QingyiEdu"
    d.mkdir(parents=True, exist_ok=True)
    return d


def setup_console():
    # line_buffering：把每行立刻刷出去。用户在双击出来的窗口里能看到实时进度，
    # 而不是等程序结束时一口气冒出来。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace",
                               line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace",
                              line_buffering=True)
    except Exception:  # noqa: BLE001
        pass
    if platform.system() != "Windows":
        return
    # 打开虚拟终端（VT）处理，Windows 10 起支持；不成功就退回纯文本。
    try:
        import ctypes
        k = ctypes.windll.kernel32
        opened = False
        for h in (k.GetStdHandle(-11), k.GetStdHandle(-12)):
            mode = ctypes.c_uint32()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                if k.SetConsoleMode(h, mode.value | 0x0004):
                    opened = True
        COLOR[0] = opened
    except Exception:  # noqa: BLE001
        COLOR[0] = False
    try:
        os.system("chcp 65001 >nul 2>nul")
        os.system("title 清一新教育 · 一键修改")
    except Exception:  # noqa: BLE001
        pass


COLOR = [platform.system() != "Windows"]   # 非 Windows 默认支持 ANSI


def c(text, code):
    """按需上色。终端不支持 ANSI 时原样返回，绝不吐出转义序列。"""
    if not COLOR[0] or not code:
        return text
    return "\x1b[%sm%s\x1b[0m" % (code, text)


DIM, BOLD, OK, WARN, ERR = "2", "1", "32", "33", "31"
BRAND, ACCENT = "38;5;63", "38;5;38"


def rule(ch="─", n=64, code=DIM):
    print(c(ch * n, code))


def _dw(s) -> int:
    """终端显示宽度：CJK 全角算 2 列，其余算 1 列（否则右边框会对不齐）。"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in s)


def _pad(s, w) -> str:
    return s + " " * max(0, w - _dw(s))


BANNER_W = 58


def banner():
    lines = [
        ("  清一新教育 · 文章一键修改", BOLD + ";" + ACCENT),
        ("  Qingyi Edu · Article One-Click Editor", DIM),
        ("  双击即用 · 无需安装 · 自动读取登录", DIM),
    ]
    print()
    print(c("  ╭" + "─" * BANNER_W + "╮", BRAND))
    for text, style in lines:
        print(c("  │", BRAND) + c(_pad(text, BANNER_W), style)
              + c("│", BRAND))
    print(c("  ╰" + "─" * BANNER_W + "╯", BRAND))
    print()


def step(n, total, text):
    print(c(" [%d/%d] " % (n, total), BOLD + ";" + ACCENT) + c(text, BOLD))


def pause(msg="按回车关闭本窗口..."):
    try:
        input(msg)
    except (EOFError, KeyboardInterrupt):
        pass


def api(path, body=None, timeout=30):
    data = None
    hdr = {"User-Agent": UA, "Accept": "application/json",
           "X-API-Key": SITE_KEY}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(SERVER + path, data=data, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def cloud_credential():
    """从云端凭证柜取一份由浏览器扩展同步上来的登录态。

    返回 (cookie, 距今秒数, 来源备注)；没有时返回 ("", 0, "")。
    """
    try:
        j = api("/api/qy/credential-latest", timeout=15)
        if j.get("ok") and j.get("cookie"):
            return (str(j["cookie"]), int(j.get("age") or 0),
                    str(j.get("note") or ""))
    except Exception:  # noqa: BLE001
        pass
    return "", 0, ""


def credential_alive(qe, ck):
    """确认这份凭证还能用（顺便拿到账号名，方便用户核对是不是本人）。"""
    try:
        info = qe.QingyiTitleSigner(ck).verify()
        return True, str(info.get("name") or "")
    except Exception:  # noqa: BLE001
        return False, ""


def cloud_per_day(fallback=DEFAULT_PER_DAY) -> int:
    """每日上限以网页上的选择为准（网页会把选择同步到云端）。"""
    for path in ("/api/qy/config",):
        try:
            j = api(path, timeout=12)
            if j.get("ok"):
                return max(0, int(j.get("per_day") or 0))
        except Exception:  # noqa: BLE001
            pass
    return fallback


def selftest() -> int:
    """打包自检：确认依赖真的被塞进 exe 了（单文件打包最常死在这里）。"""
    print("=== 自检 ===")
    print("frozen        :", getattr(sys, "frozen", False))
    print("python        :", sys.version.split()[0])
    print("platform      :", platform.system())
    print("work dir      :", work_dir())
    ok = True
    for mod in ("requests", "win32crypt", "Crypto.Cipher.AES"):
        try:
            __import__(mod)
            print(f"  [OK]   {mod}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"  [FAIL] {mod}: {type(exc).__name__}: {exc}")
    try:
        import qingyi_executor as qe
        print("  [OK]   qingyi_executor",
              "(auto_detect_cookie:", callable(getattr(qe, "auto_detect_cookie", None)),
              "| main:", callable(getattr(qe, "main", None)), ")")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"  [FAIL] qingyi_executor: {type(exc).__name__}: {exc}")
    print("=== 自检", "通过" if ok else "失败", "===")
    return 0 if ok else 1

# --------------------------------------------------------------------------- #
# 门禁：能不能开始，一次讲清。NO-GO 就绝不写入任何东西。
# --------------------------------------------------------------------------- #

WEB_CONSOLE = SERVER + "/api/qy/console"

# 每种「停」的原因，配一句人话标题
STOP_TITLES = {
    "platform":  "这台机器不是 Windows",
    "cloud":     "连不上云端工作台",
    "empty":     "云端还没有任务",
    "done":      "这单已经跑完了",
    "cancelled": "这单已被取消",
    "running":   "这单正在被另一个窗口执行",
    "nothing":   "这单里没有待执行的篇",
    "cred":      "还没拿到知乎登录",
    "prepare":   "云端没能备好最终稿",
    "sample":    "稿子抽查没通过",
}


def _stop(reason, lines):
    """打印「为什么停」+「你该做什么」，并强调没有任何修改发生。"""
    print()
    rule("━", 64, ERR)
    print(c("  ■ 先停一下 —— " + STOP_TITLES.get(reason, "暂时不能开始"),
            BOLD + ";" + ERR))
    rule("━", 64, ERR)
    for ln in lines:
        print("  " + ln)
    print()
    print(c("  这轮对你的知乎没有任何改动，可以放心。", OK))
    print()


def _jobs(limit=5):
    """取云端任务列表；连不上返回 None（与「没有任务」严格区分开）。"""
    try:
        return api("/api/qy/jobs?limit=%d" % limit, timeout=20).get("jobs") or []
    except Exception:  # noqa: BLE001
        return None


def _job(jid):
    """取单个任务详情（含 items）。失败返回 None。"""
    try:
        j = api("/api/qy/jobs/" + jid, timeout=25)
        return j.get("job") if j.get("ok") else None
    except Exception:  # noqa: BLE001
        return None


def _payload(jid, iid):
    """取某一篇的云端最终稿。没有就返回 None。"""
    try:
        return api("/api/qy/agent/payload/%s/%s" % (jid, iid), timeout=25)
    except Exception:  # noqa: BLE001
        return None


def gate_task():
    """闸门：云端到底有没有「可以跑」的任务。返回 (job|None, 原因, 说明行)。"""
    jobs = _jobs()
    if jobs is None:
        return None, "cloud", [
            "网络或云端服务暂时不通，读不到任务列表。",
            "",
            "你可以：① 等一两分钟再双击一次；",
            "        ② 确认这台电脑能打开 " + WEB_CONSOLE,
        ]
    if not jobs:
        return None, "empty", [
            "云端现在一个任务都没有 —— 还不该跑。",
            "",
            "你要做的（就这两下）：",
            "  1. 打开工作台网页 → 第 2 步勾选要改的文章 → 点「创建修改任务」",
            "  2. 回来重新双击本程序",
            "",
            "网页地址：" + WEB_CONSOLE,
        ]

    jid = jobs[0].get("job_id") or ""
    job = _job(jid) or jobs[0]
    summ = job.get("summary") or {}
    items = job.get("items") or []
    total = int(summ.get("total") or len(items) or 0)
    pend = int(summ.get("pending") or 0)
    done_n = int(summ.get("done") or 0)
    st = (job.get("status") or "").lower()

    if st == "done" or (total and done_n >= total):
        return None, "done", [
            "最新那单（%s）已经跑完了：%d 篇全部完成。" % (jid, done_n or total),
            "",
            "· 还想改别的文章 → 回网页创建新任务；",
            "· 只是想核对结果 → 回网页点「让云端复核一下」。",
        ]
    if st in ("cancelled", "canceled"):
        return None, "cancelled", [
            "最新那单（%s）是「已取消」状态，不会执行。" % jid,
            "",
            "回网页：把这一单「重置」成待执行，或者新建一单。",
        ]
    if st == "running":
        w = (job.get("worker") or {}).get("id")
        return None, "running", [
            "最新那单（%s）正在执行中%s。" % (jid, ("（worker: %s）" % w) if w else ""),
            "",
            "不要同时开第二个 —— 两边抢同一单会把节奏和计数打乱。",
            "等它跑完，或者先关掉另一个窗口，再双击本程序。",
        ]
    if total and pend == 0:
        return None, "nothing", [
            "最新那单（%s）共 %d 篇，但没有「待执行」的篇。" % (jid, total),
            "",
            "可能已经全部完成，或者都被跳过/失败了。",
            "回网页看一眼任务状态；要重跑就先点「重置」。",
        ]
    return job, None, []


def gate_credential(qe, ck_file):
    """闸门：登录态。返回 (cookie, 账号名)；拿不到就 ("", "")。"""
    ck = ""
    who = ""

    # 路线 A ── 扩展已经把本机登录同步进云端凭证柜：用一个取一个。
    # 这条路完全不碰浏览器的 Cookie 数据库，所以浏览器可以一直开着。
    cloud_ck, age, cnote = cloud_credential()
    if cloud_ck:
        print("        [i] 云端凭证柜里有一份（%s，%d 秒前同步），正在校验…"
              % (cnote or "来源未知", age))
        ok, who = credential_alive(qe, cloud_ck)
        if ok:
            ck = cloud_ck
            print("        %s 凭证有效，账号：%s"
                  % (c("[OK]", OK), who or "（未设置昵称）"))
            print("        %s 浏览器不用关，本程序不会再碰它。" % c("[OK]", OK))
        else:
            print("        %s 云端那一份已经失效（一般是刚重新登录过）。"
                  % c("[!]", WARN))
            print("            小提示：浏览器里点一下「清一新教育 · 修改助手」"
                  "图标 →「立即同步」，它会立刻刷新。")
    else:
        print("        [i] 云端凭证柜还是空的。")
        print("            装了「清一新教育 · 修改助手」扩展的话，"
              "点一下它的图标同步即可；")
        print("            没装也没关系，下面会自动回退到直接读本机浏览器。")
        print("")

    # 路线 B ── 回退：直接读本机浏览器的登录数据。
    # 浏览器运行时会独占锁定 Cookie 数据库（实测：python 直读 / 复制 /
    # CreateFileW 带宽松共享标志 / sqlite immutable 四种方式全部失败），
    # 这个锁绕不过去。所以这里不要求用户"回来按回车"，而是自动等 ——
    # 用户只要关掉浏览器，程序会自己继续。
    err = ""
    deadline = time.time() + 300
    warned = False
    last_tick = 0.0
    lock_words = ("锁定", "正在使用", "being used", "Permission", "denied",
                  "WinError 32", "Access is denied")
    if not ck:
        print("        [i] 转为读取本机浏览器里的知乎登录"
              "（不需要粘贴、不需要 F12）…")
    while not ck:
        try:
            ck, src = qe.auto_detect_cookie()
            if ck:
                print("        %s 已读取（来源：%s）" % (c("[OK]", OK), src))
                break
        except Exception as exc:  # noqa: BLE001
            err = str(exc).splitlines()[0][:110]

        now = time.time()
        if now >= deadline:
            break

        is_lock = any(w.lower() in err.lower() for w in lock_words)
        if not is_lock and warned:
            break                      # 不是"浏览器锁着"，等下去也没用
        if not warned:
            print("        %s %s" % (c("[!]", WARN), err or "暂时读不到登录态"))
            print("")
            if is_lock:
                print(c("        >>> 请把 Edge / Chrome 的【所有窗口】全部关掉"
                        "（不是最小化）。", BOLD))
                print(c("            我在这里自动等您，关掉之后会自动继续"
                        " —— 不用按任何键。", OK))
                print(c("            下次想省掉这一步：装「清一新教育 · "
                        "修改助手」扩展，", OK))
                print(c("            它会自动把登录同步到云端，"
                        "本程序就不需要关浏览器了。", OK))
            else:
                print("        请确认浏览器里已经登录 zhihu.com，"
                      "我稍后再试几次…")
            warned = True
            last_tick = now
            if not is_lock:
                deadline = time.time() + 20   # 非锁类错误：只重试一小会儿
        if now - last_tick >= 15:
            last_tick = now
            print(c("        … 仍在等待浏览器解锁（剩余约 %d 秒）"
                    % int(deadline - now), DIM))

        time.sleep(2.5)

    if not ck and ck_file.exists():
        txt = ck_file.read_text(encoding="utf-8", errors="replace")
        for line in txt.splitlines():
            if "z_c0=" in line and not line.strip().startswith("#"):
                ck = line.strip()
                print("        [i] 自动读取没成功，"
                      "改用工作目录里已有的 cookie.txt。")
                break

    if ck and not who:
        _ok, who = credential_alive(qe, ck)
    return ck, who


def _ask_start() -> bool:
    """参与感：动手前让用户按一次回车。返回 True 表示用户同意开始。"""
    print()
    rule("═", 64, ACCENT)
    print(c("  一切就绪 —— 按【回车】开始修改；输入 q 再回车 = 什么都不改，退出。",
            BOLD))
    rule("═", 64, ACCENT)
    print()
    try:
        ans = input(c("  >>> ", BOLD + ";" + ACCENT)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return ans not in ("q", "quit", "exit", "n", "no", "取消", "退出")


def main() -> int:
    setup_console()
    argv = sys.argv[1:]
    if "--selftest" in argv:
        return selftest()
    # 只做「体检 + 汇总」，绝不写入任何文章（用于验证/排障）
    prep_only = "--prep-only" in argv
    # 无人值守（计划任务等）：结束后不等待按键
    no_pause = "--no-pause" in argv
    # 跳过「按回车确认」（无人值守 / 已确认过的续跑）
    auto_yes = "--yes" in argv
    # 值守模式：跑完当前这单不退出，继续等你在网页上建新任务
    watch = "--watch" in argv

    def done(msg="按回车关闭本窗口..."):
        if not no_pause:
            pause(msg)

    try:
        import qingyi_executor as qe
    except Exception as exc:  # noqa: BLE001
        print(c("[!] 程序内部模块加载失败：", ERR), exc)
        print("    请重新下载本程序。")
        done()
        return 1

    work = work_dir()
    ck_file = work / "cookie.txt"
    backup = work / "backup"
    daily = work / "daily.json"

    os_name = platform.system()
    v = sys.version_info
    banner()

    # ── 闸 1/6 · 设备 ──────────────────────────────────────────────────
    step(1, 6, "设备识别")
    print("        系统     : %s" % os_name)
    print("        运行环境 : 内置 Python %d.%d（无需安装）" % (v.major, v.minor))
    print("        工作目录 : %s" % work)
    rule()

    if os_name != "Windows":
        _stop("platform", [
            "本程序是 Windows 版，当前系统是 %s。" % os_name,
            "",
            "macOS 请用仓库里的方式：https://github.com/Arthurchen-01/zh-editor",
        ])
        done()
        return 1

    # ── 闸 2/6 · 云端任务（「云端还没搞定就双击」就拦在这里）────────────
    step(2, 6, "先问云端：有没有等着改的任务")
    job, reason, lines = gate_task()
    if job is None:
        _stop(reason, lines)
        done()
        return 2

    jid = job.get("job_id") or ""
    summ = job.get("summary") or {}
    items = job.get("items") or []
    total = int(summ.get("total") or len(items) or 0)
    pend = int(summ.get("pending") or 0)
    print("        %s 任务 %s：共 %d 篇，待执行 %d 篇"
          % (c("[OK]", OK), jid, total, pend))
    rule()

    # ── 闸 3/6 · 每日上限 ──────────────────────────────────────────────
    cap = cloud_per_day()
    step(3, 6, "每日上限")
    print("        %s（以你在网页上的选择为准）"
          % c("不限" if cap == 0 else "%d 篇/天" % cap, OK))

    # ── 闸 4/6 · 登录态 ────────────────────────────────────────────────
    step(4, 6, "取得知乎登录态（优先用浏览器扩展同步到云端的凭证）")
    ck, who = gate_credential(qe, ck_file)
    if not ck:
        _stop("cred", [
            "等了一会儿，还是没拿到知乎登录 —— 卡在这一步就停住，不往下走。",
            "",
            "最省事：装「清一新教育 · 修改助手」扩展，点一下图标同步。",
            "其次  ：把 Edge / Chrome 的所有窗口全部关掉，再双击一次本程序。",
            "最后  ：手动把知乎 Cookie 粘贴到这个文件里：%s" % ck_file,
        ])
        done()
        return 4

    ck_file.write_text(ck + "\n", encoding="utf-8")

    # 凭证暂存到云端：网页上点「载入凭证」即可看到同一个登录态
    try:
        r = api("/api/qy/credential-deposit",
                {"key": SITE_KEY, "cookie": ck, "note": os_name,
                 "per_day": cap}, timeout=20)
        if r.get("ok"):
            print("        %s 凭证已同步到云端（网页上可直接点「载入凭证」）"
                  % c("[OK]", OK))
    except Exception as exc:  # noqa: BLE001
        print("        [i] 凭证同步失败（不影响本机运行）：%s" % str(exc)[:80])
    rule()

    # ── 闸 5/6 · 云端备稿（本地不自己算，只负责搬运）────────────────────
    step(5, 6, "请云端把这 %d 篇的最终稿算好并缓存" % pend)
    try:
        pj = api("/api/qy/prepare", {"job_id": jid, "cookie": ck}, timeout=600)
    except Exception as exc:  # noqa: BLE001
        pj = {"ok": False, "note": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    if not pj.get("ok"):
        _stop("prepare", [
            "云端没能把这单的最终稿备好，所以先不动你的知乎。",
            "",
            "云端给的原因：" + str(pj.get("note") or pj.get("detail") or "未知"),
            "",
            "常见情况：登录刚失效 / 文章被删或改动了 / 云端暂时繁忙。",
            "你可以：① 回网页确认任务还在；② 稍等片刻再双击一次。",
        ])
        done()
        return 5

    got = pj.get("prepared")
    if got is None:
        got = pj.get("cached")
    print("        %s 云端最终稿已就绪（本次新备 %s 篇 / 无需改动 %s 篇 / 失败 %s 篇）"
          % (c("[OK]", OK), got, pj.get("skipped"), pj.get("failed")))
    rule()

    # 备完稿重新拉一次任务详情，拿到最新的 items 与前后对照
    job = _job(jid) or job
    items = job.get("items") or []
    pending_items = [it for it in items if (it.get("status") or "") == "pending"]
    if not pending_items:
        _stop("nothing", [
            "云端备完稿之后，这单里已经没有「待执行」的篇了。",
            "",
            "回网页看一眼任务状态；要重跑就先点「重置」。",
        ])
        done()
        return 5

    # ── 闸 6/6 · 动手前抽查：每一篇的稿子是不是都取得到 ────────────────
    step(6, 6, "动手前抽查：确认这 %d 篇的最终稿都取得到" % len(pending_items))
    ready = 0
    missing = []
    for it in pending_items[:200]:
        iid = str(it.get("id") or "")
        pl = _payload(jid, iid) if iid else None
        if pl and (pl.get("title") or pl.get("content")):
            ready += 1
        else:
            missing.append(iid or "（缺 id）")
    if missing:
        _stop("sample", [
            "云端说备好了，但有 %d 篇的稿子取不到（共 %d 篇待执行）。"
            % (len(missing), len(pending_items)),
            "",
            "为稳妥起见，先不动你的知乎 —— 免得只改一半、留下半成品。",
            "取不到的是：" + "、".join(missing[:8])
            + ("…" if len(missing) > 8 else ""),
            "",
            "请把这句反馈给技术人员：payload 缺失（job=%s）" % jid,
        ])
        done()
        return 6
    print("        %s 抽查通过：%d 篇的标题与正文都拿到了" % (c("[OK]", OK), ready))
    rule()

    # ── 汇总 · 让用户看清「接下来要发生什么」──────────────────────────
    print()
    rule("═", 64, ACCENT)
    print(c("  一切就绪 · 接下来这几篇会被修改", BOLD))
    rule("═", 64, ACCENT)
    print("  任务号     %s" % jid)
    print("  账号       %s" % (who or "（未设置昵称）"))
    print("  本次执行   %d 篇（这单共 %d 篇）" % (len(pending_items), total))
    print("  每日上限   %s" % ("不限" if cap == 0 else "%d 篇/天" % cap))
    print("  改动位置   每篇：标题 1 处 + 正文 1 处（正文其余内容一字不改）")
    print()
    show_n = min(5, len(pending_items))
    for i in range(show_n):
        it = pending_items[i]
        b = (it.get("title_before") or "").strip()
        a = (it.get("title_after") or b).strip()
        print("  第 %d 篇" % (i + 1))
        print("    原标题：%s" % (b or "（云端将回读）"))
        if a and a != b:
            print("    新标题：%s" % c(a, OK))
        else:
            print("    新标题：（无需改动）")
    if len(pending_items) > show_n:
        print("  … 其余 %d 篇同上处理" % (len(pending_items) - show_n))
    print()

    # ── prep-only：体检完就停，绝不写入 ────────────────────────────────
    if prep_only:
        print(c("  [prep-only] 体检全部通过、云端最终稿已备好；", OK))
        print(c("              本轮没有执行任何写入，安全退出。", OK))
        print()
        done()
        return 0

    # ── 参与感：确认之后才动手 ─────────────────────────────────────────
    if auto_yes:
        print(c("  [--yes] 已确认，直接开始。", OK))
    else:
        if not _ask_start():
            print()
            print(c("  好的，这轮什么都不改。", WARN))
            print("  想清楚了再双击一次即可，云端的东西都还在。")
            print()
            done()
            return 0

    # ── 执行 ───────────────────────────────────────────────────────────
    print()
    print("  Ctrl+C 可随时安全停止；到量会自动停，剩余的次日继续。")
    rule()
    rc = 0
    run_args = ["--server", SERVER, "--key", SITE_KEY,
                "--cookie", ck,
                "--cookie-file", str(ck_file),
                "--backup-dir", str(backup),
                "--daily-file", str(daily),
                "--per-day", str(cap)]
    if not watch:
        # 默认只跑一轮：跑完当前这单就收工退出，绝不留一个空转的窗口
        run_args.append("--once")
    try:
        rc = qe.main(run_args)
    except KeyboardInterrupt:
        print(c("\n[i] 已手动停止。进度都保存在云端，下次继续即可。", WARN))
    except Exception as exc:  # noqa: BLE001
        print(c("\n[!] 运行中断：%s: %s"
                % (type(exc).__name__, str(exc)[:200]), ERR))
        rc = 1

    rule()
    print()
    print(c("  跑完了。回到网页点「让云端复核一下」——", BOLD))
    print("  云端会重新回读你线上的真实文章，告诉你哪几篇按要求完成了、哪几篇没有。")
    print("  网页地址：%s" % WEB_CONSOLE)
    if watch:
        print()
        print(c("  [--watch] 值守模式：我继续等着你在网页上建下一个任务"
                "（Ctrl+C 退出）。", DIM))
    print()
    done()
    return rc


if __name__ == "__main__":
    sys.exit(main())
