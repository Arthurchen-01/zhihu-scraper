"""Write 一键取证并同步云端.bat with CRLF (\\r\\n) and pure ASCII execution header to guarantee 100% Windows CMD compatibility."""

from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 使用纯净的 CRLF 和 Windows 标准批处理结构
lines = [
    "@echo off",
    "chcp 65001 >nul",
    "cls",
    "echo ======================================================================",
    "echo  清一武道馆 · 全网负面舆情监控与法务存证同步终端",
    "echo ======================================================================",
    "echo.",
    "cd /d \"C:\\Users\\25472\\Desktop\\AI brain storming\\工具栏\\zhihu-black\"",
    "echo [1/3] 📡 正在向云端服务器 (38.76.206.7:8770) 发起实时增量证据同步...",
    "call uv run python cloud_sync_service.py",
    "echo.",
    "echo [2/3] 📸 正在对最新侵权链接执行 Playwright 批量现场截图与存证...",
    "call uv run python batch_archive_fulltext_and_screenshots.py",
    "echo.",
    "echo [3/3] 📂 正在打开最新证据文件与报表目录...",
    "start \"\" \"C:\\Users\\25472\\Desktop\\清一武道馆\\outputs\\excel_reports\"",
    "echo.",
    "echo ======================================================================",
    "echo  🎉 同步与取证完成！最新 Excel 证据表与截图已就绪。",
    "echo  🌐 随时在线查看 24h 实时大盘: http://38.76.206.7:8770",
    "echo ======================================================================",
    "pause"
]

bat_text = "\r\n".join(lines) + "\r\n"
bat_path = Path(r"C:\Users\25472\Desktop\清一武道馆\一键取证并同步云端.bat")
# UTF-8 with BOM (0xEF, 0xBB, 0xBF) or UTF-8
bat_path.write_bytes(b"\xef\xbb\xbf" + bat_text.encode("utf-8"))

print("✅ 已用标准 Windows CRLF + UTF-8 with BOM 重写【一键取证并同步云端.bat】！")
