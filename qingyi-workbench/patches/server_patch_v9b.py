# -*- coding: utf-8 -*-
"""v9b：状态条在「页面尚未挂载任务」时也要说对话。

页面重新打开时不会自动挂载已存在的任务（JOB 仍是 null），
原来的文案就会说「① 还没创建任务」——而用户其实已经建过了。
一键程序始终领的是「最新任务」，所以直接告诉他：
建过没建过都可以往下走。
"""
from pathlib import Path
import py_compile

P = Path("/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py")
src = P.read_text(encoding="utf-8")
orig = src

old = '''    if(!j){
      t = "① 还没创建任务 —— 先完成上面第 2 步（勾文章 → 点「创建修改任务」）。";
    }else{'''
new = '''    if(!j){
      // 注意：刚打开页面时不会自动挂载历史任务，所以这里不能武断说"还没创建"。
      // 一键程序领的永远是「最新任务」，建过没建过都可以直接往下走。
      t = "① 还没建任务的话：先在上面第 2 步勾好文章 → 点「创建修改任务」。"
        + "已经建过任务的，可以直接跳到 ② —— 双击「清一新教育一键修改.exe」，"
        + "它会自动领走最新那个任务。";
    }else{'''

if old not in src:
    print("SKIP（未匹配）")
elif src.count(old) != 1:
    print("FAIL 出现 %d 次" % src.count(old))
else:
    bak = P.with_suffix(".py.bak-v9b")
    if not bak.exists():
        bak.write_text(orig, encoding="utf-8")
    P.write_text(src.replace(old, new, 1), encoding="utf-8")
    print("OK 状态条文案")

py_compile.compile(str(P), doraise=True)
print("编译校验通过")
