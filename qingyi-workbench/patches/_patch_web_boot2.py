# -*- coding: utf-8 -*-
"""web.py 修复第 2 批：mcpClaudeConfig 同样是「单引号 JS 字符串里嵌真换行」。
源文件里它是一行带 \\n 转义的物理行；页面渲染后变成多行单引号字符串 -> 非法 JS。
改成反引号模板字符串（模板字面量天然允许多行）。"""
import re, sys, py_compile
sys.stdout.reconfigure(encoding="utf-8")

P = "/opt/zhihu-scraper/zhihu_scraper/app/web.py"
s = open(P, "r", encoding="utf-8", newline="").read()
orig = s

pat = re.compile(r"const mcpClaudeConfig = '(.*?)';(?=\n\s*const mcpCursorConfig)", re.S)
hits = pat.findall(s)
if len(hits) != 1:
    print("ANCHOR_FAIL mcpClaudeConfig:", len(hits)); sys.exit(2)
mid = hits[0]
if "`" in mid:
    print("UNEXPECTED_BACKTICK"); sys.exit(3)
new = "const mcpClaudeConfig = `" + mid + "`;"
s = pat.sub(lambda m: new, s, count=1)

open(P, "w", encoding="utf-8", newline="").write(s)
try:
    py_compile.compile(P, doraise=True, cfile=P + ".pyc")
except py_compile.PyCompileError as e:
    print("PY_COMPILE_FAIL", e); sys.exit(4)
print("bytes %d -> %d" % (len(orig.encode("utf-8")), len(s.encode("utf-8"))))
print("PATCH2_OK")
