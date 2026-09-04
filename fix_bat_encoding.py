"""Save 一键取证并同步云端.bat with native GBK (CP936) encoding for 100% Windows CMD compatibility."""

from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

bat_content = """@echo off
title 清一武道馆 - 全网负面舆情监控与法务存证同步终端

echo ======================================================================
echo  清一武道馆 · 全网负面舆情监控、现场截图与律师版证据同步终端
echo ======================================================================
echo.

set "PROJECT_DIR=C:\\Users\\25472\\Desktop\\AI brain storming\\工具栏\\zhihu-black"
cd /d "%PROJECT_DIR%"

echo [1/3] 正在向云端服务器 (38.76.206.7:8770) 发起实时增量证据同步...
uv run python cloud_sync_service.py

echo.
echo [2/3] 正在对最新侵权链接执行 Playwright 高保真现场截图与全文存证...
uv run python batch_archive_fulltext_and_screenshots.py

echo.
echo [3/3] 正在打开最新证据文件与报表目录...
start explorer "C:\\Users\\25472\\Desktop\\清一武道馆\\outputs\\excel_reports"

echo.
echo ======================================================================
echo  同步与取证完成！最新 Excel 证据表与截图已就绪。
echo  随时在线查看 24h 实时大盘: http://38.76.206.7:8770
echo ======================================================================
pause
"""

bat_path = Path(r"C:\Users\25472\Desktop\清一武道馆\一键取证并同步云端.bat")
bat_path.write_bytes(bat_content.encode("gbk", errors="replace"))

print("已成功将【一键取证并同步云端.bat】以 GBK (ANSI) 格式原生重写并保存！")
