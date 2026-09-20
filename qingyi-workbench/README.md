# 清一新教育文章修改工作台 · 交付物

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

1. **工作台页 `zhihu_scraper/app/qingyi_page.py` 里有 4 个 `<style>` 块，顺序即优先级：**
   `原始块（兜底）` → `v13 覆盖层` → `v13.1 覆盖层修正` → `v13.2 引导与提示`。
   改动只往后追加，**不要替换原始块**。
2. **批量覆盖样式前，必须先把每个类的原始规则读出来。**
   教训：曾按类名批量覆盖，盖错 7 处语义完全不同的类 ——
   `.step` 是 23px 序号圆点（不是区块）、`.notice` 是琥珀警示条（不是蓝）、
   `.logs`/`.diff` 是深色终端块（不是白）、`.zero` 是绿色成功块、
   `.jsbox` 是浅色代码框、`.scanbox` 需要能滚。

3. **同一个类被多层覆盖过时，先数清楚有几层碰它。**
   教训：`toast` 被 v13 改成浅色玻璃、又被 v13.1 按回深色，前一层等于白做；
   表面症状是「明明改了却不生效」。动视觉层前先 `grep` 一遍这个类出现过几次。

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
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8775/api/qy/console
curl -s -H 'X-API-Key: <站点密钥>' http://127.0.0.1:8775/api/qy/meta | head -c 300
```

**进不来的东西（别指望在仓库里找到）**：真实知乎 Cookie、DeepSeek Key、
`data/qy_jobs.json`、`data/qyedu_backup/`、exe 产物 —— 都在服务器上或本机，
按 `.gitignore` 排除。

## 7. 怎么把改动推到 GitHub（2026-09-20 实测可行）

服务器上**没有存任何 GitHub 凭证**（无 credential helper / .netrc / gh），
`git push` 直连会卡在要用户名。两条死路别再试：

- **本机 git over ssh 拉服务器仓库** —— 沙箱里 git 的 ssh 子进程会挂死管道，
  超时都杀不干净；
- **整仓 bundle 下载**（约 57MB）—— 传输通道会被掐。

实测可行的路（脚本 `patches/_push_from_server.py` 一键做完）：

1. 本机从 Windows 凭据管理器读 PAT（脚本 `qy_gettok.py` → `qy_local/_tok.tmp`）；
2. token 传到服务器 `/tmp/qy_tok`（umask 077，权限 600）；
3. 服务器写一次性 askpass 脚本，
   `GIT_ASKPASS=… git -c credential.helper= push origin HEAD:main`；
4. 推完**立刻删掉**服务器上的 askpass 脚本与 token 文件（脚本里已做）。

若必须走 bundle（比如要整仓搬家），只打**增量**：
`git bundle create x.bundle <GitHub已有HEAD>..main`，本机克隆 GitHub 仓库后
`git fetch x.bundle main:server-main` 再推。

