# -*- coding: utf-8 -*-
"""v7c：FAQ 第 1 条改为「扩展优先」的措辞。"""
from pathlib import Path
import py_compile

P = Path("/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py")
src = P.read_text(encoding="utf-8")

old = ('''    "1) 点「载入凭证」说凭证柜是空的？\\n" +
    "   说明你电脑上的部署包还没跑，或者跑了超过 6 小时。\\n" +
    "   重新双击一次「一键部署」即可。\\n\\n" +''')
new = ('''    "1) 点「载入凭证」说凭证柜是空的？\\n" +
    "   说明还没有任何东西把登录同步上来（凭证只保留 6 小时）。\\n" +
    "   最快的办法：装第 1 步的浏览器扩展，点一下它的图标同步；\\n" +
    "   或者双击一次一键程序。\\n\\n" +''')

if old not in src:
    print("SKIP  FAQ 第 1 条（未匹配）")
elif src.count(old) != 1:
    print("FAIL  出现 %d 次" % src.count(old))
else:
    bak = P.with_suffix(".py.bak-v7c")
    if not bak.exists():
        bak.write_text(src, encoding="utf-8")
    P.write_text(src.replace(old, new, 1), encoding="utf-8")
    print("OK    FAQ 第 1 条")

py_compile.compile(str(P), doraise=True)
print("编译校验通过")
