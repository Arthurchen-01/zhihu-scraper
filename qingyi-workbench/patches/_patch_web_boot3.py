# -*- coding: utf-8 -*-
"""web.py 修复第 3 批：cookie 正则里的 \\r\\n\\t 被非 raw 页面串吃成真控制符，
正则字面量里出现真实换行 -> 非法。改为双反斜杠，让 JS 拿到转义序列。"""
import sys, py_compile
sys.stdout.reconfigure(encoding="utf-8")

P = "/opt/zhihu-scraper/zhihu_scraper/app/web.py"
BS = chr(92)
s = open(P, "r", encoding="utf-8", newline="").read()
orig = s

old = ('const m = cookie.value.match(/z_c0="?([^"; '
       + BS + "r" + BS + "n" + BS + "t" + ']+)"?/);')
new = ('const m = cookie.value.match(/z_c0="?([^"; '
       + BS + BS + "r" + BS + BS + "n" + BS + BS + "t" + ']+)"?/);')

n = s.count(old)
if n != 1:
    print("ANCHOR_FAIL regex:", n); sys.exit(2)
s = s.replace(old, new, 1)

open(P, "w", encoding="utf-8", newline="").write(s)
try:
    py_compile.compile(P, doraise=True, cfile=P + ".pyc")
except py_compile.PyCompileError as e:
    print("PY_COMPILE_FAIL", e); sys.exit(4)
print("bytes %d -> %d" % (len(orig.encode("utf-8")), len(s.encode("utf-8"))))
print("PATCH3_OK")
