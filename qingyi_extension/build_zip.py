#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 qingyi_extension/ 打包成 data/qy_download/qingyi-extension.zip。

控制台第 1 步的「🧩 浏览器扩展」按钮就是从后者的
GET /api/qy/download/extension 分发的。

用法（在仓库根目录执行）：
    python3 qingyi_extension/build_zip.py
"""
import hashlib
import os
import sys
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent
OUT = ROOT / "data" / "qy_download" / "qingyi-extension.zip"

# 解压后先出现的文件放前面，方便用户一眼看到 AGENTS.md
ORDER = [
    "AGENTS.md", "README.md", "install-extension.ps1",
    "manifest.json", "config.js", "background.js",
    "popup.html", "popup.js", "options.html", "options.js", "help.html",
    "icons/icon-16.png", "icons/icon-32.png",
    "icons/icon-48.png", "icons/icon-128.png",
]

# 时间戳固定，保证同样的源码 -> 同样的 zip（可复现）
STAMP = (2026, 9, 20, 11, 0, 0)


def main() -> int:
    missing = [f for f in ORDER if not (SRC / f).exists()]
    if missing:
        print("[X] 缺少文件：", ", ".join(missing))
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in ORDER:
            zi = zipfile.ZipInfo(name, date_time=STAMP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, (SRC / name).read_bytes())

    b = OUT.read_bytes()
    print("已生成 %s" % OUT)
    print("  条目 %d 个 / %d 字节" % (len(ORDER), len(b)))
    print("  md5  %s" % hashlib.md5(b).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
