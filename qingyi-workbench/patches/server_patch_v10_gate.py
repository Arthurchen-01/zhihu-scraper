# -*- coding: utf-8 -*-
"""v10 补丁：第 3 步卡片 ② 的说明改成「六道体检 + 按回车确认」。

用户反馈：「本地这个只要双击了就直接开始启动了，但是 bug 很多啊，
比如云端还没搞定就下载双击了……没有一个原子式的，这样用户慌啊，
你得让他有参与感，同时还很简单。」

→ exe 已改为六道闸门 + 一次回车确认；这里把页面文案同步过来。
"""
import io
import re
import sys

PAGE = "/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py"

OLD = """      <div class="ttl">② 双击 <code>清一新教育一键修改.exe</code></div>
      <div class="tiptext">
        会弹出一个黑窗口，它自动完成：取云端凭证 → 领任务 →
        逐篇把改好的稿子提交到你的知乎 → 跑完自动停。
        <b>跑完之前别关那个窗口</b>；到每日上限会自己停下，剩下的第二天接着跑。
        窗口里会一行行打印进度，不用按任何键。
      </div>
"""

NEW = """      <div class="ttl">② 双击 <code>清一新教育一键修改.exe</code> —— 先体检，再问你一声</div>
      <div class="tiptext">
        弹出一个黑窗口，它先做<b>六道体检</b>：有没有任务 / 登录有效没 /
        云端稿子备好没。<b>任何一道不过，它当场停下并告诉你差什么、该点哪里</b> ——
        不闷头跑，也不会开着窗口空转（<b>这时不会动你的知乎</b>）。<br>
        六道全绿之后，它把<b>「要改哪几篇、标题从什么改成什么」摆给你看</b>，
        你<b>按一次回车它才开始动手</b>；按 q 就什么都不改、直接退出。<br>
        跑的过程中一行行打印进度；到每日上限会自己停下（剩下的第二天接着跑），
        跑完它会提示你「按回车关闭窗口」。
      </div>
"""


def main() -> int:
    with io.open(PAGE, encoding="utf-8") as f:
        src = f.read()

    n = src.count(OLD)
    if n != 1:
        print("[X] 待替换片段出现 %d 次（应为 1 次），中止，未改动文件。" % n)
        return 1

    out = src.replace(OLD, NEW)
    if NEW.strip() not in out:
        print("[X] 替换后校验失败，中止。")
        return 1

    with io.open(PAGE, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)

    print("[OK] 已替换 1 处。文件 %d -> %d 字节" % (len(src), len(out)))
    # 回读确认
    back = io.open(PAGE, encoding="utf-8").read()
    for k in ("六道体检", "按一次回车它才开始动手", "不会动你的知乎"):
        print("   回读 %-18s : %s" % (k, k in back))
    print("   旧文案是否已消失 :", "它自动完成：取云端凭证" not in back)
    return 0


if __name__ == "__main__":
    sys.exit(main())
