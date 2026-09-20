# -*- coding: utf-8 -*-
"""把「第十三轮 · 界面重做」卡片插进验收报告，并更新截图计数。"""
import io
import os
import sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "验收报告.html")
s = io.open(P, encoding="utf-8").read()
before = len(s)

# ---------- 1) Hero 截图计数 16 -> 20 ----------
old_cnt = ('<div class="stat ok"><div class="n" data-count="16">16</div>'
           '<div class="l">张页面截图逐屏留证</div></div>')
new_cnt = ('<div class="stat ok"><div class="n" data-count="20">20</div>'
           '<div class="l">张页面截图逐屏留证</div></div>')
if s.count(old_cnt) != 1:
    print("计数锚点异常:", s.count(old_cnt)); sys.exit(1)
s = s.replace(old_cnt, new_cnt, 1)

# ---------- 2) 新卡片 ----------
CARD = """
<!-- ================= 0 · v13 更新 ================= -->
<div class="card">
  <h2><span class="n">◆</span> 第十三轮 · 界面重做：从「一堆白盒子」到有层次、有反馈</h2>
  <div class="meta">
    你提的原话：「<b>这个各种渲染看起来极其低级啊，就是完全没有任何交互的感觉</b>」。<br>
    爹把你看到的两样东西（这份<b>验收报告</b> + <b>工作台页面</b>）都摊开逐行看了 ——
    你说得对，而且是同一个病根。这一轮就是把两边的界面重做一遍。
  </div>

  <h3>A. 病根在哪（逐条查证，不是感觉）</h3>
  <table>
    <tr><th style="width:150px">位置</th><th>原来是什么样</th></tr>
    <tr>
      <td><b>验收报告</b></td>
      <td>15 张卡片<b>同一种白盒子</b>（1px 边框 + 一层阴影）；没有折叠、
          没有悬停反馈、没有进场动效；16 张截图<b>不能点开</b>；
          代码块<b>没法复制</b>；50 多 KB 一路滚到底，中途没有任何路标。</td>
    </tr>
    <tr>
      <td><b>工作台页面</b></td>
      <td>97 个选择器基本靠 <b>1px 边框 + 纯色块</b>拼出来：卡片之间没有层次、
          按钮<b>没有按下反馈</b>、折叠块直接蹦开没有过渡、滚动<b>没有任何反馈</b>。</td>
    </tr>
    <tr>
      <td><b>最扎眼的那个</b></td>
      <td>报告里 9 张卡片带着历史上不同时期留下的<b>杂色 inline 边框</b> ——
          琥珀 / 红 / 紫 / 绿 / 天蓝……<b>同一个东西 9 种颜色</b>。
          这就是「低级」最直接的来源。</td>
    </tr>
  </table>

  <h3>B. 报告页现在能干什么</h3>
  <table>
    <tr><th style="width:200px">能力</th><th>说明</th></tr>
    <tr><td><b>顶部粘性工具栏</b></td><td>毛玻璃质感，右侧带一条<b>阅读进度条</b>，随时知道读到哪了</td></tr>
    <tr><td><b>左侧目录 + 滚动高亮</b></td><td>宽屏常驻；窄屏点「目录」拉出抽屉（带遮罩，Esc 关）。
        当前所在章节实时高亮</td></tr>
    <tr><td><b>卡片折叠</b></td><td>标题整行可点，历史轮次<b>默认折起</b>并留一行摘要预览；
        顶部有「全部折叠 / 全部展开」</td></tr>
    <tr><td><b>搜索</b></td><td>输入即过滤章节、实时计数、无结果给提示（快捷键 <code>/</code>）</td></tr>
    <tr><td><b>截图灯箱</b></td><td>点任意截图放大，暗底毛玻璃，Esc 或点任意处关闭</td></tr>
    <tr><td><b>代码块复制</b></td><td>悬停出现「复制」，复制成功变绿提示</td></tr>
    <tr><td><b>进场动画</b></td><td>卡片滚动进入视口时轻微上浮淡入；顶部的数字从 0 滚上去</td></tr>
    <tr><td><b>其余</b></td><td>回到顶部按钮、表格行悬停、打印样式（自动展开 + 隐藏工具栏）、
        尊重 <code>prefers-reduced-motion</code></td></tr>
  </table>

  <h3>C. 工作台页面现在有什么</h3>
  <table>
    <tr><th style="width:200px">元素</th><th>升级后</th></tr>
    <tr><td>整体</td><td>统一色板 / 圆角 / <b>三层阴影</b> / 渐变主色 / 细滚动条</td></tr>
    <tr><td>按钮</td><td>渐变底 + 悬停上浮 + <b>按下缩放</b> + 键盘焦点环</td></tr>
    <tr><td>序号圆点 <code>.step</code></td><td>蓝→青渐变圆，白字，带投影</td></tr>
    <tr><td>状态胶囊 <code>.chip</code></td><td>跑动中的胶囊带<b>脉冲小点</b></td></tr>
    <tr><td>进度条 <code>.pbar</code></td><td>渐变填充 + <b>流动微光</b></td></tr>
    <tr><td>页面顶部</td><td>2px <b>滚动进度条</b></td></tr>
    <tr><td>卡片</td><td>进场时轻微上浮（<b>跳过 <code>.dim</code>/<code>.hide</code></b>，不破坏原有语义）</td></tr>
    <tr><td>折叠块 <code>details</code></td><td>展开有过渡动效，右侧箭头旋转</td></tr>
  </table>

  <h3>D. 覆盖层第一次盖错了 —— 自己抓出来修掉</h3>
  <p>第一版覆盖层是「按类名批量改样式」，结果<b>盖错了几处语义完全不同的类</b>。
     爹在页面上逐个核对原规则后，补了一层修正层：</p>
  <table>
    <tr><th style="width:170px">类</th><th style="width:230px">它的真实语义</th><th>第一版盖成</th></tr>
    <tr><td><code>.step</code></td><td>23px 的<b>序号圆点</b>（不是区块）</td>
        <td><span class="pill warn">盖成灰色区块</span> → 改回渐变圆</td></tr>
    <tr><td><code>.notice</code></td><td><b>琥珀色警示条</b></td>
        <td><span class="pill warn">盖成蓝色</span> → 改回琥珀</td></tr>
    <tr><td><code>.logs</code> / <code>.diff</code></td><td><b>深色终端块</b></td>
        <td><span class="pill warn">盖成白底</span> → 改回深色并加质感</td></tr>
    <tr><td><code>.zero</code></td><td><b>绿色成功块</b></td>
        <td><span class="pill warn">盖成灰色</span> → 改回绿色</td></tr>
    <tr><td><code>.jsbox</code></td><td><b>浅色</b>代码框</td>
        <td><span class="pill warn">盖成深色</span> → 改回浅色</td></tr>
    <tr><td><code>.scanbox</code></td><td>需要<b>能滚动</b>（原有 max-height）</td>
        <td><span class="pill warn">被加了 overflow:hidden</span> → 改回 auto</td></tr>
    <tr><td><code>.badge</code></td><td>柔和的浅蓝小标签</td>
        <td><span class="pill warn">满渐变太抢戏</span> → 改回柔和浅蓝</td></tr>
  </table>
  <div class="note">
    <b>教训：</b>「按类名批量覆盖样式」之前，必须先把<b>每个类的原始规则</b>拉出来读一遍。
    光看类名猜语义（<code>.step</code> 像区块、<code>.zero</code> 像空状态）一定会盖错。
  </div>

  <h3>E. 截图</h3>
  <div class="shot">
    <img src="shots/18_v13_page_ui.png" alt="工作台页面 · 重做后">
    <div class="cap"><b>工作台页面（重做后）</b>：序号变成渐变圆点、按钮是渐变底、
      标题旁的小标签是柔和浅蓝胶囊、赞助条是琥珀渐变，
      顶部有一条 2px 阅读进度条；右侧链接、折叠块箭头都统一了。</div>
  </div>
  <div class="shot">
    <img src="shots/19_v13_page_jobpanel.png" alt="工作台 · 进度与统计面板">
    <div class="cap"><b>工作台 · 进度与统计面板</b>：四个数字卡（成功绿 / 跳过蓝 / 失败红 / 待处理蓝）、
      渐变进度条、深色终端块、以及绿/灰/红三种语义的按钮。
      <span style="color:#92400e">注：该面板平时在 <code>.card.hide</code> 里（要先检索出文章列表才显示），
      截图时临时揭开以便呈现，未做任何修饰。</span></div>
  </div>
  <div class="shot">
    <img src="shots/17_v13_report_ui.png" alt="验收报告 · 重做后">
    <div class="cap"><b>本报告（重做后）</b>：上方是渐变顶栏 + 吸顶工具栏（含搜索框、折叠按钮、目录按钮），
      下面是 Hero 区（渐变顶线、小标签、四个会滚动的数字卡）。</div>
  </div>
  <div class="shot">
    <img src="shots/20_v13_report_toc.png" alt="报告 · 目录抽屉">
    <div class="cap"><b>报告 · 目录抽屉</b>：点右上「目录」拉出全部章节（11 轮迭代 + 6 个常设章节），
      背景遮罩虚化，点任意处或按 Esc 关闭。</div>
  </div>

  <h3>F. 怎么保证没改坏功能</h3>
  <ul>
    <li><b>只加不改</b>：工作台页原有 <code>&lt;style&gt;</code> 原样保留做兜底，
        新的两层样式追加在后面。所有 <code>id</code> / <code>onclick</code> / 业务逻辑一行没动。</li>
    <li>关键符号计数核对：<code>btnCreate</code> / <code>doCreate</code> /
        <code>doInspect</code> / <code>fBodyHits</code> 合计 <b>9 处</b>，改前改后一致。</li>
    <li>两个页面在浏览器里<b>控制台零报错、零警告</b>。</li>
    <li><code>python3 -m py_compile</code> 通过，服务 active，<code>/api/qy/console</code> 返回 200
        （体积 84KB → 104KB，多出来的全是新增样式与脚本）。</li>
    <li>提交 <code>1f9fb92</code>，已确认 <code>HEAD == origin/main</code>，工作区干净。</li>
  </ul>
</div>

"""

anchor = '<!-- ================= 0 · v12 更新 ================= -->'
if s.count(anchor) != 1:
    print("锚点异常:", s.count(anchor)); sys.exit(1)
s = s.replace(anchor, CARD.strip() + "\n\n" + anchor, 1)

# ---------- 3) 页头时间 ----------
s = s.replace("生成时间：2026-09-20（v12 更新）", "生成时间：2026-09-20（v13 更新）", 1)
s = s.replace("可视化验收报告 (v12)", "可视化验收报告 (v13)", 1)
s = s.replace("可视化验收报告 · 2026-09-20（v12）", "可视化验收报告 · 2026-09-20（v13）", 1)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("OK  %d -> %d (+%d)" % (before, len(s), len(s) - before))
