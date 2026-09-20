# -*- coding: utf-8 -*-
"""把交付物（验收报告 + 截图 + 补丁脚本）+ 接手入口一起推上 GitHub，实现跨设备同步。"""
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

BASE = r"C:\Users\s990uma\WorkBuddy\2026-09-19-18-08-35\qy_local"
ROOT = "/opt/zhihu-scraper"
DOC = "清一新教育文章修改工作台_总控与需求交接.md"

# ---------- 绝不上传的文件（含真实凭证） ----------
BLOCK_FILES = {"cookie.txt", "_inspect_js.txt", "console.html", "_lastjob.txt"}
BLOCK_DIRS = {"exe_build", "zh-editor", "zh-editor-test", "data", "dist_upload",
              "pkg_v5", "brand", "qingyi_extension", "__pycache__"}

START_HERE = """# 先读这一页 · START HERE

> 这份仓库是「**清一新教育文章修改工作台**」的全部家当。
> 不管你换了电脑、换了对话窗口、还是换了助手 —— **把下面那段话粘进去，就能一把接回来。**

---

## 一、把这段话粘给任何新助手（换设备 / 换对话窗口都行）

```text
请接手「清一新教育文章修改工作台」这个项目。

1) 把仓库拿到本地（私有仓库，用 GitHub 账号 Arthurchen-01 登录即可）：
   git clone https://github.com/Arthurchen-01/zhihu-scraper.git
2) 完整读一遍仓库根目录的：
   清一新教育文章修改工作台_总控与需求交接.md
3) 再读 qingyi-workbench/README.md，
   并打开 qingyi-workbench/验收报告.html 看交付现状（每轮一张卡，截图+文本证据）
4) 然后 ssh server3（103.52.152.37），cd /opt/zhihu-scraper，
   看 git log --oneline -8 与 git status
5) 最后汇报：现在做到哪一步、线上什么状态、下一步该干什么。

动手改任何东西之前，先看总控文件的 §2（用户的判定标准）、
§4（三条架构不变量）、§12（已知的坑）—— 这三节是雷区地图。
```

**如果你已经在这台电脑上、只是换了个对话窗口**：第 1 步不用 clone，
把工作目录指向 `C:\\Users\\s990uma\\WorkBuddy\\2026-09-19-18-08-35\\qy_local\\` 即可。

---

## 二、读哪几份就够接活

| 文件 | 一句话 |
| --- | --- |
| `清一新教育文章修改工作台_总控与需求交接.md` | **唯一需求总控** —— 要做什么、做到哪、为什么这么设计、坑在哪 |
| `qingyi-workbench/README.md` | 交付物索引 + 界面设计系统 + 怎么重建 |
| `qingyi-workbench/验收报告.html` | 可视化验收报告（用浏览器直接打开） |
| `AGENTS.md` | 仓库的代理执行规则 |
| `README.md` | 对外功能与安装入口 |

**只读第一行那一份，就够接活了。** 其余是取证用的。

---

## 三、关键事实速查

| 项目 | 值 |
| --- | --- |
| 品牌词 | 标题前置 `【清一新教育】`（固定 1 处）；正文括注 `（清一新教育）`（1~5 处可选，默认 1） |
| 线上工作台 | <https://zh.samuraiguan.cloud/api/qy/console> |
| 部署机 | `server3` = `103.52.152.37`，目录 `/opt/zhihu-scraper` |
| 服务 | `zhihu-scraper.service`（systemd），端口 **8775** |
| **改完 `qingyi_*.py` 必须** | `systemctl restart zhihu-scraper`（页面是模块级常量，不重启不生效） |
| 客户端入口源码 | `clients/qingyi_deploy.py`（六道闸门 + 一次回车确认） |

---

## 四、⚠️ 这个仓库是私有的，原因写在这

仓库里含**站点访问密钥**、**服务器 IP**、品牌与对接人信息。
所以 **不要把它改成公开仓库**，除非先把这些信息清出去。

- 换新设备：用 `Arthurchen-01` 账号登录 GitHub，即可 `git clone`；
  或者生成一个**只读** Personal Access Token 交给助手。
- 仓库根的文档与代码可以随便传；**真实凭证（知乎 Cookie 等）一律不进仓库**，
  这条规矩必须继续守（见 `.gitignore` 与总控文件 §9）。
"""

WB_README = """# 清一新教育文章修改工作台 · 交付物

这个目录放**本项目的所有可见交付物与构建脚本**，目的是让「换电脑 / 换助手」时
一 clone 就能拿到全部现场证据，而不是只有代码。

---

## 1. 这里面有什么

| 路径 | 说明 |
| --- | --- |
| `验收报告.html` | **可视化验收报告**。自包含单文件，浏览器直接打开。每轮一张卡，用页面截图 + 文本快照交叉印证 |
| `shots/` | 报告引用的页面截图（1280px 宽真机截图） |
| `patches/` | 每一轮改动的**补丁脚本**与提交/验证脚本（见下） |

> 需求侧的总控在仓库根：`清一新教育文章修改工作台_总控与需求交接.md`。
> 那一份是**唯一入口**，本目录只是它的证据库。

---

## 2. 验收报告怎么用

直接双击 `验收报告.html`，或用浏览器打开。不用装任何东西。

交互（都是页内能力，不需要联网）：

- **顶部工具栏** —— 搜索框（快捷键 `/`）、全部折叠/展开、目录按钮、阅读进度条
- **左侧目录** —— 宽屏（≥1440px）常驻并按滚动高亮；窄屏点「目录」拉出抽屉，`Esc` 关
- **卡片** —— 点标题整行即可折叠；历史轮次默认折起，各留一行摘要
- **截图** —— 点任意一张放大（灯箱），`Esc` 或点任意处关闭
- **代码块** —— 鼠标悬停出现「复制」
- **打印** —— 自动展开全部卡片并隐藏工具栏

---

## 3. 界面设计系统（动样式之前必读）

工作台页与验收报告现在是**同一套设计语言**。完整说明在总控文件 **§15**；
这里只放最容易踩的两条：

1. **工作台页 `zhihu_scraper/app/qingyi_page.py` 里有 3 个 `<style>` 块，顺序即优先级：**
   `原始块（兜底）` → `v13 覆盖层` → `v13.1 覆盖层修正`。
   改动只往后追加，**不要替换原始块**。
2. **批量覆盖样式前，必须先把每个类的原始规则读出来。**
   教训：曾按类名批量覆盖，盖错 7 处语义完全不同的类 ——
   `.step` 是 23px 序号圆点（不是区块）、`.notice` 是琥珀警示条（不是蓝）、
   `.logs`/`.diff` 是深色终端块（不是白）、`.zero` 是绿色成功块、
   `.jsbox` 是浅色代码框、`.scanbox` 需要能滚。

设计令牌（两边共用）：

```text
色板    bg #f4f6fb / panel #fff / line #e7ebf3 / text #0b1220 / text-2 #4b5768
主色    brand #2563eb → cyan #06b6d4，统一走 --grad: linear-gradient(135deg,…)
语义    ok #059669 / warn #d97706 / err #dc2626
圆角    10 / 14 / 18
阴影    三层：--sh-1 贴近 · --sh-2 常态 · --sh-3 悬停
缓动    --ease: cubic-bezier(.22,.61,.36,1)
```

---

## 4. patches/ 里的脚本怎么用

所有样式/结构改动都是**通过 Python 补丁脚本打到服务器上**的，不是手改 HTML。
这些脚本都带**幂等标记**（grep 到标记就跳过），可以放心重跑。

| 脚本 | 作用 |
| --- | --- |
| `server_patch_v8_upload.py` | 页面加「手动上传凭证到云端」入口 |
| `server_patch_v9_howto.py` | 补上「怎么把改动推到自己的知乎」常驻指引卡 |
| `server_patch_v10_gate.py` | 第 3 步文案改成「先体检、再问你一声」 |
| `server_patch_v11_status.py` | 状态条改为读云端最新任务（真实状态） |
| `server_patch_v12_bodyhits.py` | 正文植入处数可选 1~5 + AI 按需推荐 |
| `_upgrade_page_ui.py` / `_fix_page_ui.py` | 工作台页：打 v13 设计系统覆盖层 + 修正层 + 交互脚本 |
| `_upgrade_report_ui.py` / `_fix_report_ui.py` / `_fix_report_toc.py` | 验收报告：换样式 + 注入交互层 + 目录抽屉 |
| `_add_v13_card.py` | 往报告里插一版新卡片（**加卡片零成本，脚本会自动挂上全部交互**） |
| `_publish_master_doc.py` / `_publish_doc_v13.py` | 总控文件上传 / 更新 + 推送 |
| `_verify_v10.py` / `_verify_v12.py` / `_verify_v13.py` | 线上验证脚本 |
| `_commit_v10.py` / `_commit_v11.py` / `_commit_v13.py` | 提交推送脚本 |

跑法（在能 ssh 到 server3 的机器上）：

```bash
python _verify_v13.py          # 例：验证 v13 是否在线生效
python _upgrade_page_ui.py     # 例：重打工作台页覆盖层（幂等，重复跑会跳过）
```

---

## 5. 往报告里加一轮新卡片（零成本）

报告页的交互层是**页面加载时用 JS 重建 DOM** 的，所以新增章节不用手写任何控件：

```html
<div class="card">
  <h2><span class="n">◆</span> 第十四轮 · 标题写在这</h2>
  <div class="meta">你提的原话 / 这轮干了什么</div>
  <h3>A. 小节标题</h3>
  <table>…</table>
  <div class="shot"><img src="shots/21_xxx.png"><div class="cap">说明</div></div>
</div>
```

丢进去即可 —— 折叠壳、目录条目、进场动画、表格圆角、代码复制按钮**全自动挂上**。
注意两条：

- **别在卡片上写 inline 样式**（会盖掉设计系统）。需要强调最新一轮，
  把它放在**第一张**即可，脚本会自动加渐变环。
- 截图按 `shots/NN_描述.png` 命名，放 `shots/` 下。

---

## 6. 重建 / 排障速查

```bash
# 服务
systemctl status zhihu-scraper
systemctl restart zhihu-scraper     # 改完 qingyi_*.py 必做

# 自检
curl -s -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:8775/api/qy/console
curl -s -H 'X-API-Key: <站点密钥>' http://127.0.0.1:8775/api/qy/meta | head -c 300
```

**进不来的东西（别指望在仓库里找到）**：真实知乎 Cookie、DeepSeek Key、
`data/qy_jobs.json`、`data/qyedu_backup/`、exe 产物 —— 都在服务器上或本机，
按 `.gitignore` 排除。
"""


def read(p):
    return io.open(p, encoding="utf-8").read()


def main():
    stage = os.path.join(tempfile.gettempdir(), "qy_sync_stage")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(os.path.join(stage, "qingyi-workbench", "shots"))
    os.makedirs(os.path.join(stage, "qingyi-workbench", "patches"))

    # --- 1) 入口文档 ---
    io.open(os.path.join(stage, "START_HERE.md"), "w",
            encoding="utf-8", newline="\n").write(START_HERE)
    io.open(os.path.join(stage, "qingyi-workbench", "README.md"), "w",
            encoding="utf-8", newline="\n").write(WB_README)

    # --- 2) 验收报告 + 它真正引用的截图 ---
    rep_src = os.path.join(BASE, "验收报告.html")
    html = read(rep_src)
    used = sorted(set(re.findall(r'src="(shots/[^"]+)"', html)))
    shutil.copyfile(rep_src, os.path.join(stage, "qingyi-workbench", "验收报告.html"))
    miss = []
    n_shot = 0
    for u in used:
        src = os.path.join(BASE, u.replace("/", os.sep))
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(stage, "qingyi-workbench", "shots",
                                              os.path.basename(u)))
            n_shot += 1
        else:
            miss.append(u)
    print("报告 + %d 张截图" % n_shot + ("；缺失: %s" % miss if miss else ""))

    # --- 3) 补丁脚本 ---
    n_py = 0
    for fn in sorted(os.listdir(BASE)):
        p = os.path.join(BASE, fn)
        if not os.path.isfile(p):
            continue
        if fn in BLOCK_FILES or not fn.endswith(".py"):
            continue
        shutil.copyfile(p, os.path.join(stage, "qingyi-workbench", "patches", fn))
        n_py += 1
    print("补丁/验证脚本 %d 个" % n_py)

    # --- 4) 打包 ---
    tgz = os.path.join(tempfile.gettempdir(), "qy_sync.tgz")
    with tarfile.open(tgz, "w:gz") as tf:
        tf.add(stage, arcname="qy-sync")
    print("打包 %.2f MB" % (os.path.getsize(tgz) / 1048576.0))

    # --- 5) 上传并解包 ---
    with open(tgz, "rb") as f:
        r = subprocess.run(["ssh", "server3", "cat > /tmp/qy_sync.tgz"],
                           stdin=f, capture_output=True, timeout=600)
    print("上传 rc =", r.returncode)

    unpack = (
        "set -e\n"
        "cd /tmp && rm -rf qy-sync 2>/dev/null || true\n"
        "mkdir -p /tmp/qy-sync\n"
        "tar xzf /tmp/qy_sync.tgz -C /tmp/qy-sync\n"
        "cp -f /tmp/qy-sync/qy-sync/START_HERE.md /opt/zhihu-scraper/START_HERE.md\n"
        "rm -rf /opt/zhihu-scraper/qingyi-workbench\n"
        "cp -a /tmp/qy-sync/qy-sync/qingyi-workbench /opt/zhihu-scraper/qingyi-workbench\n"
        "echo UNPACK_OK\n"
    )
    r = subprocess.run(["ssh", "server3", "bash -s"], input=unpack,
                       capture_output=True, timeout=300, encoding="utf-8",
                       errors="replace")
    print(r.stdout)
    if r.returncode != 0:
        print("ERR:", (r.stderr or "")[-600:])
        return 1

    # --- 6) 总控文件 §14 补一句指向 START_HERE.md ---
    doc_local = os.path.join(BASE, DOC)
    t = read(doc_local)
    old = "1. 读本文件（你正在读）。"
    new = ("0. **先读仓库根的 `START_HERE.md`** —— 那里面有一段可以直接粘给新助手的接手语。\n"
           "1. 读本文件（你正在读）。")
    if t.count(old) == 1:
        t = t.replace(old, new, 1)
        io.open(doc_local, "w", encoding="utf-8", newline="\n").write(t)
        with open(doc_local, "rb") as f:
            subprocess.run(["ssh", "server3", "cat > /tmp/qy_master_doc.md"],
                           stdin=f, capture_output=True, timeout=120)
        r2 = subprocess.run(
            ["ssh", "server3",
             "python3 -c \"import io,os,shutil;"
             "shutil.copyfile('/tmp/qy_master_doc.md','/opt/zhihu-scraper/" + DOC + "');"
             "print('doc updated')\""],
            capture_output=True, timeout=120, encoding="utf-8", errors="replace")
        print(r2.stdout.strip())
    else:
        print("§14 锚点异常，跳过（%d）" % t.count(old))

    return 0


if __name__ == "__main__":
    sys.exit(main())
