# -*- coding: utf-8 -*-
"""web.py 修复：
1) 根因：restCurlInspect / restCurlBatch 两个 JS 单引号字符串里嵌了 curl 的 -d '{...}'，
   把整段 29KB 应用脚本炸出 SyntaxError -> Vue 永不挂载 -> 裸模板 + 4 层遮罩糊脸。
   改成单行反引号模板字符串（无反斜杠、无内嵌换行，raw 与否都安全）。
2) 加固：v-cloak 防裸模板闪现 + 启动失败兜底横幅（Vue 60 次重试失败后给明确提示）。
3) 门禁弹窗补一段「这个系统是干什么的」。
全部精确锚点 + 计数断言，任何一条不命中就整体退出、不落盘。
"""
import re, sys, py_compile
sys.stdout.reconfigure(encoding="utf-8")

P = "/opt/zhihu-scraper/zhihu_scraper/app/web.py"
s = open(P, "r", encoding="utf-8", newline="").read()
orig = s

if "v13.2-web-fix" in s or "__bootTries" in s:
    print("ALREADY_APPLIED"); sys.exit(0)

steps = []

# ---- 1. 修两个炸掉的 curl 字符串 ----
NEW_INSPECT = ('const restCurlInspect = `curl -X POST "https://zh.samuraiguan.cloud/api/inspect" '
               '-H "Content-Type: application/json" -H "Authorization: Bearer guanjun2026" '
               '-d \'{"url":"https://www.zhihu.com/pin/2079702939531321857","max_items":100,"drill_column":false}\'`;')
NEW_BATCH = ('const restCurlBatch = `curl -X POST "https://zh.samuraiguan.cloud/api/scrape/batch" '
             '-H "Content-Type: application/json" -H "Authorization: Bearer guanjun2026" '
             '-d \'{"items":[{"id":"2079668307335050654","type":"article","title":"文章标题"}],'
             '"options":{"export_formats":["pdf","epub","zip"],"save_markdown":true,"save_comments":true}}\'`;')

pat_i = re.compile(r"const restCurlInspect = 'curl .*?'';", re.S)
pat_b = re.compile(r"const restCurlBatch = 'curl .*?'';", re.S)
if len(pat_i.findall(s)) != 1:
    print("ANCHOR_FAIL restCurlInspect:", len(pat_i.findall(s))); sys.exit(2)
if len(pat_b.findall(s)) != 1:
    print("ANCHOR_FAIL restCurlBatch:", len(pat_b.findall(s))); sys.exit(2)
s = pat_i.sub(lambda m: NEW_INSPECT, s, count=1)
s = pat_b.sub(lambda m: NEW_BATCH, s, count=1)
steps.append("curl-strings")

# ---- 2. v-cloak ----
if s.count('<div id="app">') != 1:
    print("ANCHOR_FAIL #app:", s.count('<div id="app">')); sys.exit(3)
s = s.replace('<div id="app">', '<div id="app" v-cloak>', 1)
i = s.find("</style>")
if i < 0:
    print("NO_STYLE"); sys.exit(4)
s = s[:i] + "    [v-cloak]{display:none !important}\n" + s[i:]
steps.append("v-cloak")

# ---- 3. 启动失败兜底 ----
OLD_BOOT = ("        function initApp() {\n"
            "            if (typeof Vue === 'undefined') {\n"
            "                setTimeout(initApp, 100);\n"
            "                return;\n"
            "            }\n")
if s.count(OLD_BOOT) != 1:
    print("ANCHOR_FAIL initApp:", s.count(OLD_BOOT)); sys.exit(5)
NEW_BOOT = ("        let __bootTries = 0;\n"
            "        function initApp() {\n"
            "            if (typeof Vue === 'undefined') {\n"
            "                if (++__bootTries > 60) {\n"
            "                    var fb = document.getElementById('bootFallback');\n"
            "                    if (fb) fb.style.display = 'flex';\n"
            "                    return;\n"
            "                }\n"
            "                setTimeout(initApp, 100);\n"
            "                return;\n"
            "            }\n")
s = s.replace(OLD_BOOT, NEW_BOOT, 1)

FALLBACK = ('    <div id="bootFallback" style="display:none;position:fixed;inset:0;z-index:99999;'
            'background:#0f172a;color:#f8fafc;align-items:center;justify-content:center;'
            'flex-direction:column;gap:10px;font-family:system-ui,sans-serif;text-align:center;">\n'
            '        <div style="font-size:16px;font-weight:700;">系统界面脚本加载失败</div>\n'
            '        <div style="font-size:13px;opacity:.8;">核心脚本未能加载，界面无法启动。'
            '请检查网络后刷新页面重试。</div>\n'
            '    </div>\n')
j = s.find('<div id="app"')
if j < 0:
    print("NO_APP"); sys.exit(6)
s = s[:j] + FALLBACK + s[j:]

OLD_MOUNT = "}).mount('#app');"
if s.count(OLD_MOUNT) != 1:
    print("ANCHOR_FAIL mount:", s.count(OLD_MOUNT)); sys.exit(7)
s = s.replace(OLD_MOUNT,
              "}).mount('#app');\n"
              "            var __a = document.getElementById('app');\n"
              "            if (__a) __a.removeAttribute('v-cloak');", 1)
steps.append("boot-fallback")

# ---- 4. 门禁弹窗补说明 ----
OLD_DESC = ('<div class="modal-desc">请输入系统访问密码以解锁 Scraper 定向排查与批量存证系统</div>')
if s.count(OLD_DESC) != 1:
    print("ANCHOR_FAIL modal-desc:", s.count(OLD_DESC)); sys.exit(8)
INTRO = (
    OLD_DESC +
    '\n                <div style="margin:14px 0 4px;padding:12px 14px;'
    'background:var(--bg-soft,#f6f8fb);border:1px solid rgba(125,140,165,.28);'
    'border-radius:10px;text-align:left;font-size:12.5px;line-height:1.78;color:#4b5768;">'
    '<b style="color:#0b1220;">这个系统是干什么的？</b><br>'
    '给知乎创作者做<b>定向排查与批量存证</b>：贴入一条知乎链接（回答 / 文章 / 想法 / 专栏），'
    '系统定向检索该内容与评论区，逐条生成<b>网页原生截图 + 正文 Markdown + 评论 JSON</b>，'
    '一键打包为 <b>ZIP / EPUB / PDF</b> 证据包 —— 用于内容盘点、舆情留档与侵权取证。'
    '</div>')
s = s.replace(OLD_DESC, INTRO, 1)
steps.append("gate-intro")

open(P, "w", encoding="utf-8", newline="").write(s)
try:
    py_compile.compile(P, doraise=True, cfile=P + ".pyc")
except py_compile.PyCompileError as e:
    print("PY_COMPILE_FAIL", e); sys.exit(9)

print("steps:", steps)
print("bytes %d -> %d" % (len(orig.encode("utf-8")), len(s.encode("utf-8"))))
print("PATCH_OK")
