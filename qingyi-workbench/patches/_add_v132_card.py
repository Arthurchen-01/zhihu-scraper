# -*- coding: utf-8 -*-
"""给验收报告插入「第十四轮 · v13.2 引导与提示」卡片，并把首屏统计数字对齐。"""
import sys, os, re, io
sys.stdout.reconfigure(encoding='utf-8')

P = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35\qy_local\验收报告.html"
s = open(P, "r", encoding="utf-8", newline="").read()
MARK = "第十四轮 · 收尾"
if MARK in s:
    print("ALREADY_APPLIED"); sys.exit(0)

CARD = '''<!-- ================= 0 · v13.2 更新 ================= -->
<div class="card">
  <h2><span class="n">◆</span> 第十四轮 · 收尾：新手引导与轻提示也换成同一套语言</h2>
  <div class="meta">
    上一轮把<b>卡片 / 按钮 / 折叠块 / 表格</b>过了设计系统，但页面里还有两处没跟上：
    <b>新手引导的聚光灯气泡</b>，和<b>底部那条 toast 轻提示</b>。<br>
    而且查证时发现一个自己埋的雷：<b>v13 那层把 toast 改成了浅色玻璃，
    v13.1 那层又把它按回深色</b> —— 两层在同一个类上互相覆盖，最终生效的是后一层，
    等于 v13 对 toast 的改造<b>白做了</b>。这一轮把它一次定死。
  </div>

  <h3>A. 病根（还是逐条查证，不是感觉）</h3>
  <table>
    <tr><th style="width:180px">位置</th><th>改之前是什么样</th></tr>
    <tr><td><b>toast 轻提示</b></td>
        <td>一块<b>深色实心方块</b>：跟页面浅色底完全不搭；
            所有提示<b>同一种颜色</b>，出错和成功长得一模一样；
            没有关闭手段，只能干等 2.6 秒；连点几下就<b>糊一屏</b>，没有上限。</td></tr>
    <tr><td><b>新手引导气泡</b></td>
        <td>只继承了圆角和一层阴影，里面的<b>序号圆、标题行、说明段、按钮组、
            跳过链接</b>全是上一代写法：天蓝实心圆点、灰色跳过字、
            说明文字跟标题挤在同一行没有分段。</td></tr>
    <tr><td><b>聚光灯</b></td>
        <td>单圈蓝边 + 整屏压暗。能看清，但<b>没有层次</b>，位置切换时也没有过渡感。</td></tr>
    <tr><td><b>操作方式</b></td>
        <td>只能点按钮。<b>不能点步骤点跳转、没有键盘操作</b>；
            窄屏下气泡定位按 340px 写死，<b>会顶出屏幕外</b>。</td></tr>
  </table>

  <h3>B. toast 现在是什么样</h3>
  <table>
    <tr><th style="width:180px">能力</th><th>说明</th></tr>
    <tr><td><b>浅色玻璃卡</b></td><td>白底 93% + 背景虚化，跟页面同一套语言；边框 + 三层阴影保证在浅底上也立得住</td></tr>
    <tr><td><b>语义色条</b></td>
        <td>左侧 3px 竖条自动按内容归色 —— <span class="pill">蓝=普通</span>
            <span class="pill">绿=成功</span> <span class="pill warn">红=出错提示</span>，
            不用改任何一处调用</td></tr>
    <tr><td><b>驻留进度条</b></td><td>底部一条 2px 细线按语义色走完 2.6 秒，<b>看得见还剩多久</b></td></tr>
    <tr><td><b>点击即关 / Esc 清空</b></td><td>不想等的点一下就没；连按 Esc 一次全清</td></tr>
    <tr><td><b>叠层上限 4 条</b></td><td>再多的提示从最老的开始顶掉，不会糊一屏</td></tr>
    <tr><td><b>零改动接入</b></td>
        <td>页面里 <b>40 多处</b> <code>toast("…")</code> 调用一行没动 ——
            新函数第二个参数可省，省了就按内容自动判色</td></tr>
  </table>

  <h3>C. 引导气泡现在是什么样</h3>
  <table>
    <tr><th style="width:180px">元素</th><th>升级后</th></tr>
    <tr><td>序号圆 <code>.t-n</code></td><td>蓝→青渐变圆，白色数字，带投影（跟页面里其它序号圆同一套）</td></tr>
    <tr><td>标题行</td><td>序号圆 + 标题<b>并排对齐</b>，不再是挤在一坨</td></tr>
    <tr><td>说明段 <code>.t-d</code></td><td>单独成段，次级灰、行高 1.75，长文读起来不累</td></tr>
    <tr><td><b>步骤点</b></td><td>底部 10 个圆点，当前一步拉成长条；<b>点任意一点直接跳过去</b></td></tr>
    <tr><td>键位提示</td><td>右下角一行 <code>← → 切换</code>，明说能敲键盘</td></tr>
    <tr><td>聚光灯</td><td>改成<b>双层光环</b>（实边 + 外发光）+ 整屏压暗，移动时有过渡</td></tr>
    <tr><td>入场</td><td>气泡轻微上浮淡入，聚光灯淡入</td></tr>
    <tr><td>键盘</td><td><b>← → 切换、Enter 下一步、Esc 跳过</b></td></tr>
    <tr><td>窄屏</td><td>气泡自动钳回视口内（老定位写死 340px 会顶出屏幕）</td></tr>
  </table>

  <h3>D. 怎么验的（真机，不是"应该没问题"）</h3>
  <table>
    <tr><th style="width:180px">检查项</th><th>结果</th></tr>
    <tr><td>改前漂移检查</td><td>远端文件 md5 与本地基线一致，<b>确认没被人动过</b>才动手</td></tr>
    <tr><td>备份</td><td><code>qingyi_page.py.bak-v132</code>（106,003 字节）</td></tr>
    <tr><td>语法</td><td>改后本地 + 远端各跑一次 <code>py_compile</code>，均通过</td></tr>
    <tr><td>替换方式</td><td>先落到 <code>/tmp</code> 校验 md5 一致，再原子替换，最后 <code>systemctl restart</code></td></tr>
    <tr><td>服务</td><td><code>active</code>；页面 <code>200</code>，<b>111,390 字节</b>（改前 106,003）</td></tr>
    <tr><td>浏览器控制台</td><td><b>0 报错 0 警告</b></td></tr>
    <tr><td>点击关闭</td><td>3 条 → 点掉 1 条 → 剩 2 条 ✅</td></tr>
    <tr><td>Esc 清空</td><td>2 条 → 0 条 ✅</td></tr>
    <tr><td>键盘切步</td><td>引导步骤 <code>0 → 1</code> ✅</td></tr>
    <tr><td>Esc 关引导</td><td>气泡与聚光灯同时消失，且<b>不再自动重现</b> ✅</td></tr>
    <tr><td>叠层上限</td><td>连发 4 条只留 4 条 ✅</td></tr>
  </table>
  <div class="note">
    <b>教训（跟上一轮同一条）：</b>同一个类被<b>两层覆盖层先后改过</b>时，
    后一层会把前一层的意图悄悄推翻。改视觉层之前先数清<b>这个类被几层碰过</b>，
    否则会出现"我明明改了却没生效"这种最耗时间的假故障。
  </div>

  <h3>E. 截图</h3>
  <div class="shot">
    <img src="shots/21_v132_tour.png" alt="新手引导气泡 · 重做后">
    <div class="cap"><b>新手引导气泡（重做后）</b>：渐变序号圆 + 并排标题 + 独立说明段 +
      底部 10 个步骤点 + 右下角「← → 切换」键位提示；被聚光灯罩住的按钮是双层光环。
      截图时站在第 1 步。</div>
  </div>
  <div class="shot">
    <img src="shots/22_v132_toast.png" alt="toast 轻提示 · 三种语义">
    <div class="cap"><b>toast 三种语义同时在场</b>（从上到下）：普通（蓝条）、
      出错提示（红条）、成功（绿条）。底色统一是浅色玻璃卡，左侧 3px 色条区分语义，
      底部细线是驻留进度。<span style="color:#92400e">注：三条是同时发出的，
      截图前把页面内驻留时间临时拉长，只为呈现同框；线上代码未做任何改动。</span></div>
  </div>
</div>

'''

anchor = "<!-- ================= 0 · v13 更新 ================= -->"
n = s.count(anchor)
if n != 1:
    print("ANCHOR_FAIL count=%d" % n); sys.exit(2)
s = s.replace(anchor, CARD + anchor, 1)

reps = [
    ('<div class="qy-hero-tag">可视化验收报告 · 2026-09-20（v13）</div>',
     '<div class="qy-hero-tag">可视化验收报告 · 2026-09-20（v13.2）</div>'),
    ('<div class="n" data-count="12">12</div><div class="l">轮迭代全部落地（v2~v13）</div>',
     '<div class="n" data-count="13">13</div><div class="l">轮迭代全部落地（v2~v13.2）</div>'),
    ('<div class="n" data-count="20">20</div><div class="l">张页面截图逐屏留证</div>',
     '<div class="n" data-count="22">22</div><div class="l">张页面截图逐屏留证</div>'),
]
for old, new in reps:
    if s.count(old) != 1:
        print("REP_FAIL:", old[:60], s.count(old)); sys.exit(3)
    s = s.replace(old, new, 1)

# 页面标题里的版本号
t = re.search(r'<title>(.*?)</title>', s, re.S)
if t and "(v13)" in t.group(1):
    s = s.replace(t.group(0), t.group(0).replace("(v13)", "(v13.2)"), 1)
    print("title ->", t.group(1).replace("(v13)", "(v13.2)").strip())

open(P, "w", encoding="utf-8", newline="").write(s)
print("bytes:", len(s.encode("utf-8")))
print("cards:", s.count('<div class="card">'))
print("OK")
