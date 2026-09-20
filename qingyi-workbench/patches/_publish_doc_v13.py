# -*- coding: utf-8 -*-
"""总控文件补 v13：需求表加一行 + 新增 §15 界面设计系统（改样式前必读）。"""
import io
import os
import subprocess
import sys

ROOT = "/opt/zhihu-scraper"
DOC = "清一新教育文章修改工作台_总控与需求交接.md"
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), DOC)

s = io.open(LOCAL, encoding="utf-8").read()
n0 = len(s)

# ---------- 1) §3 需求表加 v13 ----------
old_row = "| v12 | **正文植入处数可选（1~5）+ AI 按需推荐** | ✅ |"
new_row = ("| v12 | **正文植入处数可选（1~5）+ AI 按需推荐** | ✅ |\n"
           "| v13 | **界面重做**：报告页 + 工作台页统一设计系统（层次 / 折叠 / 动效 / 反馈） | ✅ |")
if s.count(old_row) != 1:
    print("需求表锚点异常:", s.count(old_row)); sys.exit(1)
s = s.replace(old_row, new_row, 1)

# ---------- 2) 新增 §15，插在 §14 之前 ----------
SEC15 = """## 15. 界面设计系统（改样式前必读）

两个界面的视觉现在是**同一套语言**。动样式之前先读这一节，能省掉一整轮返工。

### 15.1 设计令牌（两边共用）

```text
色板    bg #f4f6fb / panel #fff / line #e7ebf3 / text #0b1220 / text-2 #4b5768
主色    brand #2563eb → cyan #06b6d4，统一走 --grad: linear-gradient(135deg,…)
语义    ok #059669 / warn #d97706 / err #dc2626
圆角    10 / 14 / 18
阴影    三层：--sh-1 贴近 · --sh-2 常态 · --sh-3 悬停
缓动    --ease: cubic-bezier(.22,.61,.36,1)
```

### 15.2 工作台页面（`zhihu_scraper/app/qingyi_page.py`）

页面里现在有 **3 个 `<style>` 块**，顺序就是优先级：

| 序号 | 内容 | 位置 |
| --- | --- | --- |
| 1 | **原始块** —— 页面最初的全部样式 | 保留不动，做兜底 |
| 2 | **v13 覆盖层** —— 统一视觉 | 标记 `v13 · 设计系统覆盖层` |
| 3 | **v13.1 修正层** —— 修正第 2 块盖错的类 | 标记 `v13.1 · 覆盖层修正` |

> ⚠️ **改样式之前，必须先把每个类的原始规则拉出来读一遍。**
> 教训：第 2 块是「按类名批量覆盖」，结果盖错了 7 处**语义完全不同**的类 ——
> `.step` 是 23px 的**序号圆点**（不是区块）、`.notice` 是**琥珀警示条**（不是蓝）、
> `.logs` / `.diff` 是**深色终端块**（不是白）、`.zero` 是**绿色成功块**、
> `.jsbox` 是**浅色**代码框、`.scanbox` 需要能滚（被加了 `overflow:hidden`）。
> 光看类名猜语义（`.step` 像区块、`.zero` 像空状态）一定会出事。

页面末尾还有一个 `<script>`（标记 `v13 交互增强`）：

- 顶部滚动进度条 —— 写 CSS 变量 `--qy-p`，由 `body::before` 消费；
- 卡片进场轻上浮 —— **必须跳过 `.dim` / `.hide`**。这两个类靠透明度表达语义
  （`.dim` = 已禁用、`.hide` = 未解锁），被 inline `opacity` 覆盖会直接改错语义。
  另外带 2.5s 安全网，避免长页 / 整页截图时留白；
- 锚点平滑滚动。

### 15.3 验收报告（本地 `qy_local/验收报告.html`）

自包含单文件：**正文结构 + 一层样式 + 一段交互脚本**。脚本在页面加载时用 JS
重建 DOM（顶栏 / 目录 / 灯箱 / 复制按钮 / 折叠壳），所以：

- **新增卡片不用手写任何控件。** 丢一个 `<div class="card">` 进去，
  折叠、目录条目、进场动画、表格圆角、代码块复制按钮**全自动挂上**。
- 卡片上**不要再写 inline 样式**。历史上各轮留下的杂色 inline 边框
  （`style="border:2px solid #fcd34d;…"`）已被脚本统一清掉，最新一轮自动获得
  渐变色环（`.qy-latest`，由脚本给第一张卡加上）。
- 要调外观只改 `<style>` 和那段脚本；正文卡片随便加。

### 15.4 补丁脚本（都在 `qy_local/`）

样式和交互是**通过 Python 补丁脚本打到服务器上**的，不是手改：

| 脚本 | 作用 |
| --- | --- |
| `_upgrade_page_ui.py` | 工作台页：打覆盖层 + 交互增强脚本 |
| `_fix_page_ui.py` | 工作台页：打修正层 |
| `_upgrade_report_ui.py` | 报告：换样式 + 注入交互层 + 换 Hero |
| `_fix_report_ui.py` | 报告：清 inline 杂色边框 + 修折叠漏边 |
| `_fix_report_toc.py` | 报告：目录抽屉 + Hero 装饰柔化 |

**每个脚本都带幂等标记**，重复跑会自己跳过。改完页面必须
`systemctl restart zhihu-scraper`（页面是模块级常量）。

---

"""
anchor = "## 14. 给新会话的第一件事"
if s.count(anchor) != 1:
    print("§14 锚点异常:", s.count(anchor)); sys.exit(1)
s = s.replace(anchor, SEC15 + anchor, 1)

# ---------- 3) §11 当前状态补一句 ----------
old_st = "- 线上：服务 active、页面 200、两个下载端点 200"
new_st = ("- 线上：服务 active、页面 200、两个下载端点 200\n"
          "- 界面：工作台页 / 验收报告均已换 v13 设计系统（见 §15）\n"
          "- 最新提交：`1f9fb92`（v13 界面升级）")
if s.count(old_st) != 1:
    print("状态锚点异常:", s.count(old_st)); sys.exit(1)
s = s.replace(old_st, new_st, 1)

s = s.replace("> 最后更新：2026-09-20（v12）", "> 最后更新：2026-09-20（v13）", 1)

io.open(LOCAL, "w", encoding="utf-8", newline="\n").write(s)
print("本地文档 %d -> %d (+%d)" % (n0, len(s), len(s) - n0))

# ---------- 4) 上传 + 提交推送 ----------
MSG = """docs(qingyi): 总控文件补 v13 —— 需求表加一行 + 新增「界面设计系统」章节

用户反馈「界面看起来极其低级、没有任何交互」，本轮把工作台页与验收报告
统一到一套设计语言。把这件事写进总控，避免下次又被改坏：

- §3 需求全集补上 v13（界面重做）
- 新增 §15「界面设计系统（改样式前必读）」：
  - 共用设计令牌（色板 / 主色渐变 / 语义色 / 圆角 / 三层阴影 / 缓动）
  - 工作台页现在是 3 个 <style> 块的优先级顺序，以及「按类名批量覆盖」
    盖错 7 处语义不同类的教训（.step / .notice / .logs / .diff / .zero /
    .jsbox / .scanbox）
  - 交互增强脚本的注意事项（进场上浮必须跳过 .dim / .hide）
  - 验收报告是「加卡片即自动挂上交互」的自包含单文件，别再写 inline 样式
  - 5 个补丁脚本清单与幂等说明
- §11 当前状态补上界面与最新提交
"""

r = subprocess.run(["ssh", "server3", "cat > /tmp/qy_master_doc.md"],
                   stdin=open(LOCAL, "rb"), capture_output=True, timeout=120)
print("上传 rc =", r.returncode)

patch = r'''
import io, os, sys
ROOT = "/opt/zhihu-scraper"
DOC = "清一新教育文章修改工作台_总控与需求交接.md"
p = os.path.join(ROOT, DOC)
tmps = p + ".tmp"
io.open(tmps, "w", encoding="utf-8", newline="\n").write(
    io.open("/tmp/qy_master_doc.md", encoding="utf-8").read())
os.replace(tmps, p)
t = io.open(p, encoding="utf-8").read()
print("总控文件", os.path.getsize(p), "字节,", t.count(chr(10)) + 1, "行")
print("含 v13 章节:", "## 15. 界面设计系统" in t)
'''
r = subprocess.run(["ssh", "server3", "python3 -"], input=patch,
                   capture_output=True, timeout=180, encoding="utf-8",
                   errors="replace")
print(r.stdout)
if r.returncode != 0:
    print("ERR:", r.stderr[-500:]); sys.exit(1)

subprocess.run(["ssh", "server3", "cat > /tmp/qymsg_doc13.txt"],
               input=MSG.encode("utf-8"), capture_output=True, timeout=60)
cmd = ("cd %s && git add -A && git commit -F /tmp/qymsg_doc13.txt && "
       "GIT_ASKPASS=/root/.git-askpass git push origin main && "
       "echo '=== PUSHED ===' && git log --oneline -3 && "
       "git rev-parse HEAD origin/main && git status --porcelain" % ROOT)
r = subprocess.run(["ssh", "server3", cmd], capture_output=True, timeout=240,
                   encoding="utf-8", errors="replace")
print(r.stdout)
if (r.stderr or "").strip():
    print("STDERR:", r.stderr.strip()[-300:])
