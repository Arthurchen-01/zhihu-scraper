# -*- coding: utf-8 -*-
"""在服务器上提交并推送 v10（六道闸门 + 一次确认）的页面改动。"""
import subprocess
import sys

MSG = """feat(qingyi): 一键程序改成「六道闸门 + 一次确认」—— 不再闷头开跑

用户反馈：「双击了就直接开始启动了，bug 很多啊，比如云端还没搞定就下载双击了……
没有一个原子式的，这样用户慌啊，你得让他有参与感，同时还很简单。」

旧行为的问题：
  1) 云端还没建任务时，它照样进到第 4 步「开始修改」，然后开着一个窗口
     无限轮询等任务 —— 用户以为在跑，其实什么都没发生。
  2) 云端备稿失败时，只打印一行提示，仍然继续往下执行。
  3) 从「凭证就绪」到「写你的知乎」之间没有任何停顿，用户没有中止的机会。
  4) 默认不带 --once，跑完不退出，窗口一直挂着。

新行为（qingyi_deploy.py，exe 的入口）：
  · 六道闸门依次判断，任何一道不过 → 打印「差什么 / 你该做什么」→ 干净退出，
    并明确写出「这轮对你的知乎没有任何改动」：
      1/6 设备识别
      2/6 云端有没有待执行的任务
          （无任务 / 已完成 / 已取消 / 正在被别人跑 / 没有待执行的篇，各自不同措辞）
      3/6 每日上限
      4/6 登录态（云端凭证优先，回退读浏览器）
      5/6 云端备稿（/api/qy/prepare 必须 ok）
      6/6 动手前逐篇校验 payload 真的取得到（不只抽查第一篇，
          缺任何一篇就整体不动，避免只改一半留下半成品）
  · 六道全绿后打印「即将执行」清单：任务号 / 账号 / 篇数 / 每日上限 / 前后标题对照，
    然后等用户按一次回车才开始；按 q 退出，什么都不改。
    —— 参与感在这里，可中止也在这里。
  · 默认只跑一轮（不再隐式常驻）：跑完当前这单就收工退出，
    绝不留一个空转的窗口。想要值守用新增的 --watch。
  · 新增 --yes（跳过确认，无人值守）；--prep-only（只体检、不写入）保留。

页面（qingyi_page.py）第 3 步卡片 ② 的文案同步改成「先体检、再问你一声」，
写清「任何一道不过会当场停下、这时不会动你的知乎」。

实测：
  · 六道闸门逐条单测（连不上 / 无任务 / 已完成 / 已取消 / 正在跑 / 无待执行篇）
    全部命中正确的「停」分支。
  · 脚本版 --prep-only 对真实任务 qy20260919-009-d16d 全链路通过（只读，未写入）。
  · 新 exe 实跑：在闸门 4 因 Edge 锁定而正确停住，给出「关掉浏览器」指引
    并自动倒计时等待，未往下执行。
  · exe --selftest 通过；md5 08590b2b763361f4c47c1d07eb1f717a（13,683,635 字节）。
"""


def sh(cmd, timeout=180):
    r = subprocess.run(['ssh', 'server3', cmd], capture_output=True,
                       timeout=timeout, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or ''), (r.stderr or '')


def main():
    rc, out, err = sh('cd /opt/zhihu-scraper && git config user.name; '
                      'git config user.email; git log -1 --format=%an|%ae')
    print('--- 现有作者配置 ---')
    print(out.strip())

    # 写提交信息
    w = subprocess.run(['ssh', 'server3', 'cat > /tmp/qymsg_v10.txt'],
                       input=MSG.encode('utf-8'), capture_output=True,
                       timeout=60)
    print('写入提交信息 rc =', w.returncode)

    cmd = ('cd /opt/zhihu-scraper && '
           'git add -A && '
           'git commit -F /tmp/qymsg_v10.txt && '
           'GIT_ASKPASS=/root/.git-askpass git push origin main && '
           'echo "=== PUSHED ===" && '
           'git log --oneline -3 && '
           'git rev-parse HEAD origin/main')
    rc, out, err = sh(cmd, timeout=300)
    print('--- commit/push rc =', rc, '---')
    print(out)
    if err.strip():
        print('STDERR:', err.strip()[-600:])
    return 0 if rc == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
