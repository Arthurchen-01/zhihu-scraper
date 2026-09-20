# -*- coding: utf-8 -*-
"""把「第十二轮（v11 + v12）」卡片插进验收报告，并更新页头时间。"""
import io
import os
import sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "验收报告.html")
s = io.open(P, encoding="utf-8").read()

# ---------- 1) 页头时间 ----------
old_sub = "生成时间：2026-09-20（v10 更新）"
new_sub = "生成时间：2026-09-20（v12 更新）"
if s.count(old_sub) != 1:
    print("页头没找到唯一匹配:", s.count(old_sub))
    sys.exit(1)
s = s.replace(old_sub, new_sub, 1)

# ---------- 2) 新卡片 ----------
CARD = """
<!-- ================= 0 · v12 更新 ================= -->
<div class="card" style="border:2px solid #fcd34d;background:linear-gradient(180deg,#fffbeb 0%,#fff 100%)">
  <h2><span class="n">◆</span> 第十二轮 · 正文「加几处」你来定（1~5）+ AI 帮你挑位置；顺带补上「总控文件」</h2>
  <div class="meta">
    你提的原话：「<b>云端 github 写好了东西是不？云端是否有总控文件写好我的需求？不然我上下文一没，
    直接要重开了。就比如我要的不仅是标题，还有文章内容也要添加，可以选择往里加几个，也可以 ai 推荐。</b>」<br>
    这一句话里其实是<b>三件事</b>，下面逐个交代。前两件是查证结论，第三件是这一轮真正改的东西。
  </div>

  <h3>A. 先说总控文件 —— 你担心得对，之前<b>确实没有</b></h3>
  <table>
    <tr><th style="width:200px">查了什么</th><th>结果</th></tr>
    <tr>
      <td>仓库根目录有哪些 <code>*.md</code></td>
      <td><code>AGENTS.md</code> / <code>README.md</code> / <code>README_EN.md</code> /
          <code>SYSTEM_DESIGN.md</code> / <code>API_AND_MCP_GUIDE.md</code>，以及一份
          <code>清一武道馆_全网舆情监控与存证系统_总需求与技术架构规范.md</code></td>
    </tr>
    <tr>
      <td>那份「总需求」是不是本工作台的？</td>
      <td><span class="pill warn">不是</span> 它是<b>上一个项目</b>（舆情监控与存证系统）的。
          清一新教育文章修改工作台<b>此前没有任何总控文件</b> ——
          需求只散落在聊天记录里，你换个会话就真得从头讲。</td>
    </tr>
  </table>

  <div class="note">
    <b>现在有了。</b>新增
    <code>清一新教育文章修改工作台_总控与需求交接.md</code>
    （<b>394 行 / 20,674 字节</b>），已提交并推送到
    <code>github.com/Arthurchen-01/zhihu-scraper</code> 的 <code>main</code> 分支。
    新会话只要读这一份，就知道要做什么、做到哪、为什么这么设计、坑在哪、下一步干什么，
    <b>不需要翻聊天记录，也不需要再问你一遍</b>。
  </div>

  <p>这份文件里有 14 节，重点几节是：</p>
  <table>
    <tr><th style="width:270px">章节</th><th>作用</th></tr>
    <tr><td><b>§2 用户的判定标准</b></td>
        <td>把你亲口说过的话（不许解压/敲命令、要原子闸门+参与感、指引必须常驻可见、
            扩展由我们写好……）逐条摘录，<b>验收时照着打勾</b>，不是「尽量」</td></tr>
    <tr><td><b>§3 需求全集（v2~v12）</b></td>
        <td>每轮需求 + 状态 + 单点需求清单（含「正文可加几处」「AI 推荐」）</td></tr>
    <tr><td><b>§4 架构不变量</b></td>
        <td>①云端永不写知乎 ②本地不做内容判断 ③本地自报不算数，必须云端回读复核 ——
            <b>改代码前先看这三条</b></td></tr>
    <tr><td><b>§7 云端接口清单</b></td>
        <td>前缀是 <code>/api/qy</code>（不是 <code>/qy</code>）、列表会剥 <code>items</code>
            等坑，一次说清</td></tr>
    <tr><td><b>§12 已知的坑</b></td>
        <td>环境类 / 代码类 / 语义类，都是<b>真踩过的</b>，附现象和正确做法</td></tr>
    <tr><td><b>§14 给新会话的第一件事</b></td>
        <td>接手者（人或 AI）的第一份清单</td></tr>
  </table>
  <p>同时在 <code>AGENTS.md</code>（必读清单 + 文档职责）和 <code>README.md</code>
     （清一新教育章节）挂上了入口，以后不会有人「找不到需求文档」。</p>

  <h3>B. 「文章内容也要添加」 —— 这个其实早就能加，但「加几处」是<b>坏的</b></h3>
  <p>查下来，正文植入<b>一直有</b>（署名式句末括注 <code>（清一新教育）</code>），
     但<b>「加几处」这个参数从来没生效过</b> —— 三处叠加，一起把它夹死成 1 处：</p>
  <table>
    <tr><th style="width:300px">位置</th><th>原来写的是</th><th style="width:170px">后果</th></tr>
    <tr><td><code>zhihu_scraper/qy_content.py</code></td>
        <td><code>_MAX_BODY_HITS = 1</code></td>
        <td rowspan="3">不管你在页面上选几处，
            最终都只加 <b>1 处</b>；
            AI 审核也只会推荐 1 个位置</td></tr>
    <tr><td><code>zhihu_scraper/app/qingyi_page.py</code></td>
        <td>前端建任务时写死 <code>body_hits: 1</code></td></tr>
    <tr><td><code>zhihu_scraper/app/qingyi_api.py</code></td>
        <td><code>/scan-scenes</code> <b>无视</b>传入的 <code>hits</code>，固定预览 1 处</td></tr>
  </table>

  <h3>C. 现在：处数你自己选，1~5 处</h3>
  <p>页面「高级：修改内容设置 / 先预览正文植入位置」里多了一个下拉框，
     <b>只读预演、建任务、AI 审核三处用的是同一个值</b>，不会再打架。</p>

  <div class="shot">
    <img src="shots/16_v12_bodyhits.png" alt="正文植入处数选择器">
    <div class="cap"><b>页面实拍（第十二轮）</b>：「修改内容」区新增
      <b>「正文植入处数」</b> 下拉（图中选的是 3 处），右侧紧跟一句提醒
      「处数越多，被判定「关键词堆砌」的风险越高」；下面是
      「开启智能审核 · 逐篇判断加在哪里；不可用时自动回退内置规则」和
      「只读预演：看正文会加在哪」。<br>
      <span style="color:#92400e">说明：这个面板位于「检索结果卡片」内部，
      需先检索出文章列表才会出现；截图时列表为空，故临时把该卡片展开以呈现控件本身。
      控件、选项、文案均与线上一致，未做任何修饰。</span></div>
  </div>

  <p>下拉框里就是这些选项：</p>
  <pre>1 处（默认 · 最稳） / 2 处 / 3 处 / 4 处 / 5 处（最多）</pre>
  <div class="note">
    <b>为什么默认还是 1 处？</b> —— 同一篇里重复堆同一个词，正是平台判定
    「内容注水 / 关键词堆砌」的典型特征。所以 5 是<b>上限</b>，不是推荐值。
    扫描器还带「两个植入点之间至少隔 2 个段落」的约束，短文章实际只能挑出 2~4 处，宁缺毋滥。
  </div>

  <h3>D. 「也可以 AI 推荐」 —— 也打通了</h3>
  <p>AI 审核接口新增 <code>want_hits</code> 参数：候选池按你选的上限去取，
     提示词明确要求「按上限挑、<b>宁少勿多</b>」，返回结果再按上限截断。
     AI 不可用（没配 Key / 超时 / 返回不合法）时，<b>自动回退内置规则</b>挑前 N 个位置，
     不会因为 AI 挂了就一篇都改不了。</p>

  <h3>E. 引擎实测：同一篇文章，选几处就加几处</h3>
  <p>直接用线上真实引擎（<code>qy_content.scan_scenes</code>）跑同一篇正文，
     只改上限，看实际落点：</p>
  <pre>_MAX_BODY_HITS = 5

  limit=1 -> 实际 1 处, block_no=[0]
  limit=2 -> 实际 2 处, block_no=[0, 7]
  limit=3 -> 实际 3 处, block_no=[0, 2, 7]
  limit=5 -> 实际 4 处, block_no=[0, 2, 4, 7]     ← 这篇只挑得出 4 处，宁缺毋滥
  limit=9 -> 实际 4 处, block_no=[0, 2, 4, 7]     ← 上限再大也不会超

  1 处后品牌词出现次数 = 1
  3 处后品牌词出现次数 = 3      ← 加了 3 处，正文里正好 3 个品牌词
  3 处结果可还原     = True      ← 一键还原回原文，逐字一致
  幂等（已含品牌词再扫）= []      ← 已改过的文章不会被重复植入</pre>

  <p>接口层的声明也跟着改了（<code>GET /api/qy/meta</code>）：</p>
  <pre>max_body_hits   = 5
scope_statement = 标题最前面加入品牌词【清一新教育】1 处（固定）；
                  正文以署名式括注「（清一新教育）」加入品牌词，
                  处数可在 1~5 之间自选（默认 1 处），也可交由 AI 逐篇推荐加在哪。…</pre>

  <h3>F. 顺带修的一处：第 3 步状态条原来「只有刚建完任务才显示」</h3>
  <p>你说「我要怎么更新到自己的知乎，我没看到任何指引」那次（第九轮）补了一张常驻卡，
     但那张卡的状态文案<b>只在刚创建完任务、页面内存里还挂着任务对象时</b>才有内容。
     你刷新一下页面，它就又变回「还没创建任务」了 —— 这是新的坑。</p>
  <p>改法：<code>renderHowto()</code> 现在会先去
     <code>GET /api/qy/jobs?limit=1</code> 取<b>云端最新任务</b>，再按真实状态渲染。
     实测刷新后显示的是：</p>
  <pre>② 任务 qy20260919-009-d16d 已就绪（待执行 1 篇）</pre>
  <p>也就是说，<b>状态来自云端，不来自你这次是否刚点过按钮</b>。</p>

  <h3>G. 提交记录</h3>
  <table>
    <tr><th style="width:120px">提交</th><th>内容</th></tr>
    <tr><td><code>01877af</code></td>
        <td>docs(qingyi): 新增「总控与需求交接」—— 上下文丢了也能一把接回来
            （+ AGENTS.md / README.md 挂入口）</td></tr>
    <tr><td><code>dda2bec</code></td>
        <td>feat(qingyi): 正文植入处数可选 1~5 + AI 按需推荐</td></tr>
    <tr><td><code>20fe77e</code></td>
        <td>feat(qingyi): 第 3 步状态条改成「读云端最新任务」+ 客户端入口源码入库</td></tr>
  </table>
  <p>已确认 <code>HEAD == origin/main == 01877af</code>，工作区干净。</p>
</div>

"""

anchor = '<!-- ================= 0 · v10 更新 ================= -->'
if s.count(anchor) != 1:
    print("锚点没找到唯一匹配:", s.count(anchor))
    sys.exit(1)
s = s.replace(anchor, CARD.strip() + "\n\n" + anchor, 1)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("OK 报告已更新:", len(s), "字符")
