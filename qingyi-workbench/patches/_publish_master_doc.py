# -*- coding: utf-8 -*-
"""把总控文件放进仓库，并在 AGENTS.md / README.md 里挂上入口。"""
import io
import subprocess
import sys

DOC = "清一新教育文章修改工作台_总控与需求交接.md"
LOCAL = "清一新教育文章修改工作台_总控与需求交接.md"
ROOT = "/opt/zhihu-scraper"
AGENTS = ROOT + "/AGENTS.md"
README = ROOT + "/README.md"

MSG = """docs(qingyi): 新增「总控与需求交接」—— 上下文丢了也能一把接回来

用户诉求：「云端是否有总控文件写好我的需求？不然我上下文一没，直接要重开了。」

仓库里此前只有旧「舆情监控」项目的总需求，**清一新教育文章修改工作台没有总控**。
新增 `清一新教育文章修改工作台_总控与需求交接.md`，一处说清：

- 一分钟定位 + 相关人与账号（品牌词 / 站点密钥 / 部署机 / 服务）
- **用户的判定标准**（原话摘录，验收逐条对照）
- 需求全集：按 v2~v12 逐轮列状态 + 单点需求清单
- 架构不变量三条（云端永不写知乎 / 本地不做内容判断 / 本地自报不算数）
- 改动范围（标题固定 1 处；正文 1~5 处可选，默认 1）
- exe 六道闸门 + 一次回车确认 + 各命令行开关
- 云端接口清单（含 payload 结构、`/api/qy` 前缀、列表剥 items 等坑）
- 防风控节奏表 + 写入链路
- 部署与运维、exe 构建命令与发布三步
- 验收方式（要出哪些证据）
- 当前状态与待办
- 已知的坑（环境类 / 代码类 / 语义类）
- 术语表 + 给新会话的第一件事

同时在 `AGENTS.md` 的必读清单与文档职责里挂上入口，
`README.md` 的清一新教育章节补上指向该文档的链接，并修正
「每篇固定 2 处」的旧表述（正文处数现已可选 1~5）。
"""


def sh(cmd, timeout=300):
    r = subprocess.run(['ssh', 'server3', cmd], capture_output=True,
                       timeout=timeout, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or ''), (r.stderr or '')


def main():
    # 1) 先按纯 ASCII 名上传，再由服务端脚本改成中文名
    #    （避免中文路径穿过 ssh 命令行时的编码问题）
    up = subprocess.run(['ssh', 'server3', 'cat > /tmp/qy_master_doc.md'],
                        stdin=open(LOCAL, 'rb'), capture_output=True, timeout=120)
    print('上传到 /tmp rc =', up.returncode)

    # 2) 改名 + 挂入口（脚本走 stdin，中文没问题）
    patch = r'''
import io, shutil, sys, os

ROOT = "/opt/zhihu-scraper"
DOC = "清一新教育文章修改工作台_总控与需求交接.md"
AG  = ROOT + "/AGENTS.md"
RD  = ROOT + "/README.md"

shutil.move("/tmp/qy_master_doc.md", os.path.join(ROOT, DOC))
p = os.path.join(ROOT, DOC)
print("总控文件:", p, os.path.getsize(p), "字节,", sum(1 for _ in io.open(p, encoding="utf-8")), "行")

fails = []

def rep(path, old, new, label):
    s = io.open(path, encoding="utf-8").read()
    if s.count(old) != 1:
        fails.append((label, s.count(old)))
        return
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        s.replace(old, new, 1))
    print("[OK]", label)

rep(AG, """3. 按任务读取：
   - `README.md` 与 `README_EN.md`：对外功能和安装入口""",
    """3. 按任务读取：
   - `清一新教育文章修改工作台_总控与需求交接.md`：**清一新教育文章修改工作台的需求总控与交接**
     （做这个子系统之前必须先读这一份）
   - `README.md` 与 `README_EN.md`：对外功能和安装入口""",
    "AGENTS 必读清单")

rep(AG, """- `AGENTS.md`：代理执行规则""",
    """- `AGENTS.md`：代理执行规则
- `清一新教育文章修改工作台_总控与需求交接.md`：清一新教育文章修改工作台的
  需求总控、判定标准、架构不变量、接口清单、运维与踩坑记录（该子系统的唯一入口文档）""",
    "AGENTS 文档职责")

rep(RD, """**改动范围（硬约束）**：每篇文章固定改动 **2 处** ——
① 标题最前面加入品牌词 `【清一新教育】` 1 处；
② 正文以署名式括注 `（清一新教育）` 加入品牌词 1 处。""",
    """**改动范围**：标题最前面加入品牌词 `【清一新教育】` **1 处（固定）**；
正文以署名式括注 `（清一新教育）` 加入品牌词，**处数可在 1~5 之间自选（默认 1 处）**，
也可交由 AI 逐篇推荐加在哪。同一篇里重复堆同一个词越容易触发平台
「关键词堆砌」判定，所以处数是上限而非推荐值，默认保持 1 处。""",
    "README 改动范围")

rep(RD, """**使用**：访问工作台页面 `🏷️ 文章修改工作台` → 粘贴凭证 → 只读检索 →""",
    """> 📌 该子系统的**需求总控、判定标准、接口清单、运维与踩坑记录**见
> [`清一新教育文章修改工作台_总控与需求交接.md`](./清一新教育文章修改工作台_总控与需求交接.md)。

**使用**：访问工作台页面 `🏷️ 文章修改工作台` → 粘贴凭证 → 只读检索 →""",
    "README 入口链接")

if fails:
    print("未应用：", fails)
    sys.exit(1)
print("全部应用成功")
'''
    r = subprocess.run(['ssh', 'server3', 'python3 -'], input=patch,
                       capture_output=True, timeout=120, encoding='utf-8',
                       errors='replace')
    print(r.stdout)
    if r.returncode != 0:
        print('patch ERR:', r.stderr[-500:])
        return 1

    # 3a) 先把工作区里 v12 的代码改动单独提交掉（别和文档混在一个 commit）
    V12MSG = """feat(qingyi): 正文植入处数可选 1~5 + AI 按需推荐

用户诉求：「我要的不仅是标题，还有文章内容也要添加，可以选择往里加几个，
也可以 ai 推荐。」

排查发现「正文加几处」此前**从未生效**，三处叠加夹死：
- qy_content.py        _MAX_BODY_HITS = 1
- app/qingyi_page.py   前端写死 body_hits: 1
- app/qingyi_api.py    /scan-scenes 无视传入的 hits

修复：
- _MAX_BODY_HITS 提到 5（默认仍是 1，处数是上限不是推荐值）
- 页面「高级」区加「正文植入处数」下拉（1~5），bodyHitsWant() 统一取值，
  建任务 / 只读预演 / AI 审核三处都带上
- AI 审核新增 want_hits 参数：候选池按上限取，提示词「按上限挑、宁少勿多」，
  结果按 want_hits 截断；AI 不可用时回退内置规则挑前 want_hits 处
- /meta 增 max_body_hits=5，scope_statement 同步为「1~5 处自选，默认 1」
"""
    subprocess.run(['ssh', 'server3', 'cat > /tmp/qymsg_v12.txt'],
                   input=V12MSG.encode('utf-8'), capture_output=True, timeout=60)
    cmd1 = ('cd %s && git add zhihu_scraper/app/qingyi_api.py '
            'zhihu_scraper/app/qingyi_page.py zhihu_scraper/qy_content.py && '
            'git commit -F /tmp/qymsg_v12.txt && echo "=== V12 COMMITTED ===" && '
            'git log --oneline -1' % ROOT)
    rc, out, err = sh(cmd1)
    print('v12 commit rc =', rc)
    print(out)
    if err.strip():
        print('STDERR:', err.strip()[-400:])
    if rc != 0:
        print('v12 提交失败，停在这里。')
        return 1

    # 3b) 提交推送总控文件 + AGENTS/README 入口
    subprocess.run(['ssh', 'server3', 'cat > /tmp/qymsg_doc.txt'],
                   input=MSG.encode('utf-8'), capture_output=True, timeout=60)
    cmd = ('cd %s && git add -A && git commit -F /tmp/qymsg_doc.txt && '
           'GIT_ASKPASS=/root/.git-askpass git push origin main && '
           'echo "=== PUSHED ===" && git log --oneline -4 && '
           'git rev-parse HEAD origin/main && git status --porcelain' % ROOT)
    rc, out, err = sh(cmd)
    print('commit/push rc =', rc)
    print(out)
    if err.strip():
        print('STDERR:', err.strip()[-400:])
    return 0 if rc == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
