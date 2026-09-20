# -*- coding: utf-8 -*-
"""v7 文案补丁：把「浏览器扩展能免掉关浏览器」写进给 AI 助手的说明与各处提示。"""
from pathlib import Path
import py_compile

API = Path("/opt/zhihu-scraper/zhihu_scraper/app/qingyi_api.py")
PAGE = Path("/opt/zhihu-scraper/zhihu_scraper/app/qingyi_page.py")
rep = []


def patch(path, pairs):
    src = path.read_text(encoding="utf-8")
    orig = src
    for old, new, tag in pairs:
        if old not in src:
            rep.append("SKIP  %s :: %s" % (path.name, tag))
            continue
        if src.count(old) != 1:
            rep.append("FAIL  %s :: %s（出现 %d 次）"
                       % (path.name, tag, src.count(old)))
            continue
        src = src.replace(old, new, 1)
        rep.append("OK    %s :: %s" % (path.name, tag))
    if src != orig:
        bak = path.with_suffix(path.suffix + ".bak-v7b")
        if not bak.exists():
            bak.write_text(orig, encoding="utf-8")
        path.write_text(src, encoding="utf-8")


# ---------------- qingyi_api.py ----------------
patch(API, [
    # 1) AGENTS_MD：关浏览器那段 → 讲清「扩展可免掉」
    ('''唯一要提醒用户的一件事：如果 Edge / Chrome 开着，程序会提示关掉浏览器 ——
**它会自动等你，关掉后自己继续，不用按任何键**（浏览器会独占锁住登录数据，
这是 Windows 的系统级行为，任何工具都绕不过去）。''',
     '''关于「要不要关浏览器」：一键程序会**优先**去云端凭证柜取登录态。
如果用户装了我们提供的浏览器扩展「清一新教育 · 修改助手」，
扩展已经把登录同步进云端了 → **浏览器可以一直开着，什么都不用做**。

没装扩展时，如果 Edge / Chrome 开着，程序会提示关掉浏览器 ——
**它会自动等你，关掉后自己继续，不用按任何键**（浏览器会独占锁住登录数据，
这是 Windows 的系统级行为，任何工具都绕不过去）。

> 强烈建议顺手把扩展装上（见下一节），用户从此就不需要关浏览器了。''',
     "AGENTS_MD 关浏览器段"),

    # 2) AGENTS_MD：插入扩展专章
    ('''## 请按顺序执行''',
     '''## 浏览器扩展（强烈建议，一次性）

扩展**我们已经写好**，你不需要写任何代码。它只做一件事：
把本浏览器的知乎登录同步到云端凭证柜，从而让「关浏览器」这一步彻底消失。

- 下载：`{{SERVER}}/api/qy/download/extension`
  （zip，请求需带请求头 `X-API-Key: {{KEY}}`）
- 解压到固定位置：`%LOCALAPPDATA%\\\\QingyiEdu\\\\extension`
- 打开 `edge://extensions`（Chrome 用 `chrome://extensions`）
  → 打开右上角「开发者模式」→「加载已解压的扩展程序」→ 选那个文件夹
- 点扩展图标 →「立即同步到云端」，看到「本浏览器知乎登录：已登录」即成功

⚠️ **浏览器禁止任何脚本注入 `chrome://` / `edge://` 页面**，
所以最后点选文件夹那一两下必须由人完成，不要试图用脚本自动化，必然失败。
压缩包里的 `AGENTS.md` 有完整步骤，同目录的 `install-extension.ps1`
可以代劳「放文件 / 开页面 / 路径进剪贴板」。

装好后，用户只需要做一件事：**双击一键程序**。

## 请按顺序执行''',
     "AGENTS_MD 插入扩展章"),

    # 3) 凭证柜为空时的提示（现在首选是扩展，不再是部署包）
    ('''                "note": ("凭证柜还是空的（凭证保留 6 小时）。"
                         "请先在第 1 步下载部署包、在你的电脑上双击「一键部署」，"
                         "再回来点「载入凭证」。")}''',
     '''                "note": ("凭证柜还是空的（凭证保留 6 小时）。"
                         "最省事：装上「清一新教育 · 修改助手」扩展，"
                         "点一下它的图标即可完成同步；"
                         "或者在第 1 步下载一键程序并双击一次，"
                         "再回来点「载入凭证」。")}''',
     "凭证柜为空提示"),
])

# ---------------- qingyi_page.py ----------------
patch(PAGE, [
    ('''        : ("取凭证据失败：" + m + "。请先在第 1 步下载部署包、在你的电脑上双击「一键部署」，再回来点本按钮。"),''',
     '''        : ("取凭证据失败：" + m + "。最省事是装第 1 步的浏览器扩展并点一下同步；"
           + "或者下载一键程序双击一次，再回来点本按钮。"),''',
     "载入凭证失败提示"),
])

print("\n".join(rep))
print("\n编译校验:", end=" ")
for p in (API, PAGE):
    try:
        py_compile.compile(str(p), doraise=True)
        print(" %s 通过" % p.name, end="")
    except py_compile.PyCompileError as e:
        print("\n%s 失败:\n%s" % (p.name, e))
        raise
print()
