# -*- coding: utf-8 -*-
"""服务端补丁 v7：
  1) /credential-latest 加密钥校验（不再让任何人凭 URL 拿到真实知乎登录态）
  2) /download/extension 分发自写的浏览器扩展包
"""
from pathlib import Path

API = Path("/opt/zhihu-scraper/zhihu_scraper/app/qingyi_api.py")
src = API.read_text(encoding="utf-8")
orig = src
report = []


def sub(old, new, tag):
    global src
    if old not in src:
        report.append("SKIP  %s（未找到，可能已打过）" % tag)
        return
    if src.count(old) != 1:
        report.append("FAIL  %s（出现 %d 次，不唯一）" % (tag, src.count(old)))
        return
    src = src.replace(old, new, 1)
    report.append("OK    %s" % tag)


# ---- 1. 导入 Request ----
sub(
    "from fastapi import APIRouter, HTTPException",
    "from fastapi import APIRouter, HTTPException, Request",
    "导入 Request",
)

# ---- 2. credential-latest 加密钥校验 ----
sub(
    '''@router.get("/credential-latest")
def qy_cred_latest():
    """网页端一键载入最近自动获取的凭证（6 小时内有效）。"""
    now = time.time()''',
    '''@router.get("/credential-latest")
def qy_cred_latest(request: Request, key: str = ""):
    """网页端 / 浏览器扩展 / 一键程序取回最近同步的凭证（6 小时内有效）。

    这里装的是**一份真实的知乎登录态**，不能让任何人凭猜到的 URL 就拿到，
    所以加了站点密钥校验。key 走 X-API-Key 头或 ?key= 查询参数都可以
    （查询参数是给手工 curl 排障留的口子）。
    """
    if (request.headers.get("X-API-Key") or key or "") != SITE_KEY:
        raise HTTPException(status_code=403, detail="站点密钥不正确")
    now = time.time()''',
    "credential-latest 加密钥校验",
)

# ---- 3. 下载端点支持扩展 ----
sub(
    '''_EXE_NAME = "清一新教育一键修改.exe"
_EXE_DIR = Path("data/qy_download")


@router.get("/download/{plat}")
def qy_download(plat: str):
    """分发一键程序：用户下载后双击即用 —— 不用解压、不用终端、不用装 Python。"""
    p = (plat or "").strip().lower()
    if p not in ("windows", "win", "exe"):''',
    '''_EXE_NAME = "清一新教育一键修改.exe"
_EXT_NAME = "清一新教育-修改助手-扩展.zip"
_EXE_DIR = Path("data/qy_download")


@router.get("/download/{plat}")
def qy_download(plat: str):
    """分发客户端：一键程序（双击即用）+ 浏览器扩展（装上就不用关浏览器）。

    注意：扩展分支必须写在 /download/{plat} 这同一个函数里 ——
    如果另开一条 /download/extension 路由，会被 {plat} 先吃掉（
    FastAPI 按声明顺序匹配），这是踩过的坑。
    """
    p = (plat or "").strip().lower()
    if p in ("extension", "ext", "chrome", "edge", "browser"):
        for cand in (_EXE_DIR / _EXT_NAME, _EXE_DIR / "qingyi-extension.zip"):
            if cand.exists():
                return FileResponse(str(cand), media_type="application/zip",
                                    filename=_EXT_NAME)
        raise HTTPException(
            status_code=404,
            detail="浏览器扩展包还没上传到服务器，请先联系管理员。")
    if p not in ("windows", "win", "exe"):''',
    "download 支持扩展",
)

# ---- 4. meta 里补一条扩展说明 ----
sub(
    '''        "sponsor": SPONSOR,''',
    '''        "sponsor": SPONSOR,
        "client_tools": {
            "windows": "/api/qy/download/windows",
            "extension": "/api/qy/download/extension",
            "extension_note": (
                "浏览器扩展「清一新教育 · 修改助手」：把本浏览器已登录的知乎凭证"
                "自动同步到云端凭证柜。装上之后本地一键程序直接从云端取凭证，"
                "不再需要关闭浏览器（浏览器会独占锁定 Cookie 数据库，"
                "外部程序读不到，这是系统层面的锁）。"),
        },''',
    "meta 补扩展说明",
)

if src != orig:
    bak = API.with_suffix(".py.bak-v7")
    if not bak.exists():
        bak.write_text(orig, encoding="utf-8")
    API.write_text(src, encoding="utf-8")

print("\n".join(report))
print("\n编译校验:", end=" ")
import py_compile
try:
    py_compile.compile(str(API), doraise=True)
    print("通过")
except py_compile.PyCompileError as e:
    print("失败\n", e)
    raise
