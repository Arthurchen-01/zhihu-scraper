# -*- coding: utf-8 -*-
"""提交并推送 v13 界面升级。"""
import subprocess
import sys

ROOT = "/opt/zhihu-scraper"

MSG = """feat(qingyi): 工作台页面换设计系统 —— 从「一堆白盒子」改成有层次、有反馈的界面

用户反馈：「这个各种渲染看起来极其低级啊，就是完全没有任何交互的感觉」

原页面 97 个选择器基本靠 1px 边框 + 纯色块拼出来：卡片之间没有层次、
按钮没有按下反馈、折叠块没有动效、滚动没有任何反馈，通篇是白盒子平铺。

本次**只加不改**：原有 <style> 原样保留做兜底，后面追加两层样式 + 一段脚本：

- v13 覆盖层 —— 统一色板 / 圆角 / 三层阴影 / 渐变主色 / 状态胶囊 /
  进度条微光 / 标签页 / 表单焦点环 / 细滚动条 / prefers-reduced-motion
- v13.1 修正层 —— 上一版把几处「语义不同」的类盖错了，按原意改回并升级质感：
  .step 是序号圆点（不是区块）/ .notice 是琥珀警示（不是蓝）/
  .logs·.diff 是深色终端块（不是白）/ .zero 是绿色成功块 /
  .jsbox 是浅色代码框 / .scanbox 要能滚（别 overflow:hidden）
- 交互增强脚本 —— 顶部滚动进度条、卡片进场轻上浮（跳过 .dim/.hide，
  并带 2.5s 安全网避免长页留白）、锚点平滑滚动、details 展开动效与箭头

未改动任何 id / onclick / 业务逻辑；btnCreate·doCreate·doInspect·fBodyHits
等关键符号计数核对一致，页面 200，浏览器控制台零报错。
"""


def sh(cmd, timeout=240):
    r = subprocess.run(["ssh", "server3", cmd], capture_output=True,
                       timeout=timeout, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def main():
    subprocess.run(["ssh", "server3", "cat > /tmp/qymsg_v13.txt"],
                   input=MSG.encode("utf-8"), capture_output=True, timeout=60)
    cmd = ("cd %s && git add zhihu_scraper/app/qingyi_page.py && "
           "git commit -F /tmp/qymsg_v13.txt && "
           "GIT_ASKPASS=/root/.git-askpass git push origin main && "
           "echo '=== PUSHED ===' && git log --oneline -3 && "
           "git rev-parse HEAD origin/main && git status --porcelain" % ROOT)
    rc, out, err = sh(cmd)
    print("rc =", rc)
    print(out)
    if err.strip():
        print("STDERR:", err.strip()[-400:])
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
