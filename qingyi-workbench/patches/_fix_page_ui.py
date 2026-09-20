# -*- coding: utf-8 -*-
"""修正层：覆盖层误盖了语义不同的类，按原意改回并做质感升级。"""
import os
import subprocess
import sys

ROOT = "/opt/zhihu-scraper"
PY = ROOT + "/zhihu_scraper/app/qingyi_page.py"

FIX = r"""<style>
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
"""


def sh(cmd, timeout=240):
    r = subprocess.run(["ssh", "server3", cmd], capture_output=True,
                       timeout=timeout, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def main():
    subprocess.run(["ssh", "server3", "cat > /tmp/qy_ui_fix.html"],
                   input=FIX.encode("utf-8"), capture_output=True, timeout=120)

    patch = r'''
import io, sys, os
PY = "/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py"
s = io.open(PY, encoding="utf-8").read()
n0 = len(s)
if "v13.1 · 覆盖层修正" in s:
    print("已打过修正层，跳过"); sys.exit(0)

ANCHOR = "<script>\n/* ===== v13 交互增强"
if s.count(ANCHOR) != 1:
    print("ERROR: 锚点次数 =", s.count(ANCHOR)); sys.exit(1)
fix = io.open("/tmp/qy_ui_fix.html", encoding="utf-8").read()
if '"""' in fix:
    print("ERROR: 含三引号"); sys.exit(1)

s = s.replace(ANCHOR, fix + ANCHOR, 1)
tmps = PY + ".tmp"
io.open(tmps, "w", encoding="utf-8", newline="\n").write(s)
os.replace(tmps, PY)
print("OK %d -> %d (+%d)" % (n0, len(s), len(s) - n0))
'''
    r = subprocess.run(["ssh", "server3", "python3 -"], input=patch,
                       capture_output=True, timeout=180, encoding="utf-8",
                       errors="replace")
    print(r.stdout)
    if r.returncode != 0:
        print("ERR:", r.stderr[-600:])
        return 1

    rc, out, err = sh("cd %s && python3 -m py_compile zhihu_scraper/app/qingyi_page.py "
                      "&& echo COMPILE_OK && systemctl restart zhihu-scraper "
                      "&& sleep 3 && systemctl is-active zhihu-scraper" % ROOT)
    print(out.strip())
    rc, out, err = sh("curl -s -o /dev/null -w 'console=%{http_code} size=%{size_download}\\n' "
                      "http://127.0.0.1:8775/api/qy/console")
    print(out.strip())
    rc, out, err = sh("cd %s && grep -c 'v13.1 · 覆盖层修正' zhihu_scraper/app/qingyi_page.py"
                      % ROOT)
    print("修正层标记:", out.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
