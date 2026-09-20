# -*- coding: utf-8 -*-
"""提交 v11（状态条读真实任务）+ 把 exe 的入口源码纳入仓库。"""
import subprocess
import sys

MSG = """feat(qingyi): 第 3 步状态条改成「读云端最新任务」+ 客户端入口源码入库

一、状态条（qingyi_page.py）
  旧的 renderHowto 只在页面自己挂载过任务（全局 JOB 非空）时才显示状态。
  但刷新页面不会自动挂载历史任务，所以打开页面时永远落到
  「① 还没建任务的话……」这句兜底文案 —— 即使用户其实早就建好了任务。
  现在：JOB 为空时自己去 GET /api/qy/jobs?limit=1 拉「最新任务」，
  按真实状态说话（就绪 / 执行中 / 已跑完 / 已取消 / 无待执行篇）。
  刷新后一眼就能看到自己处在哪一步，不用猜、不用慌。
  实测线上：任务 qy20260919-009-d16d 已就绪（待执行 1 篇），无控制台报错。

二、客户端入口源码入库（clients/qingyi_deploy.py）
  这是 Windows 单文件「一键修改.exe」的入口（PyInstaller spec 指向它）。
  之前只存在于本地构建目录，仓库里没有 —— 别人拿到仓库无法复现这个 exe。
  现在纳入仓库，和 qingyi_worker.py 一起构成「云端 + 客户端」完整链路。

  它的行为（本轮重点）：六道闸门 + 一次回车确认，任何一道不过就干净退出、
  绝不动用户的知乎；六道全绿才把「要改哪几篇、标题从什么改成什么」摆出来，
  等用户按回车才开始。默认只跑一轮，跑完退出，不留空转窗口。
"""


def sh(cmd, timeout=300):
    r = subprocess.run(['ssh', 'server3', cmd], capture_output=True,
                       timeout=timeout, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or ''), (r.stderr or '')


def main():
    # 1) 建目录并上传 exe 入口源码
    sh('mkdir -p /opt/zhihu-scraper/clients')
    up = subprocess.run(
        ['ssh', 'server3', 'cat > /opt/zhihu-scraper/clients/qingyi_deploy.py'],
        stdin=open('exe_build/qingyi_deploy.py', 'rb'),
        capture_output=True, timeout=120)
    print('上传入口源码 rc =', up.returncode)

    rc, out, err = sh('cd /opt/zhihu-scraper && '
                      'wc -l clients/qingyi_deploy.py && git status --porcelain')
    print(out)

    # 2) 写提交信息
    w = subprocess.run(['ssh', 'server3', 'cat > /tmp/qymsg_v11.txt'],
                       input=MSG.encode('utf-8'), capture_output=True, timeout=60)
    print('写入提交信息 rc =', w.returncode)

    # 3) 提交并推送
    cmd = ('cd /opt/zhihu-scraper && '
           'git add -A && '
           'git commit -F /tmp/qymsg_v11.txt && '
           'GIT_ASKPASS=/root/.git-askpass git push origin main && '
           'echo "=== PUSHED ===" && '
           'git log --oneline -3 && '
           'git rev-parse HEAD origin/main')
    rc, out, err = sh(cmd, timeout=300)
    print('--- commit/push rc =', rc, '---')
    print(out)
    if err.strip():
        print('STDERR:', err.strip()[-500:])
    return 0 if rc == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
