@echo off
chcp 65001 >nul
cls
echo ======================================================================
echo  知乎定向排查与批量存证 Web 交互系统 (本地端口 8775)
echo ======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."

echo 正在启动 Web 服务...
start "" http://127.0.0.1:8775
python -m zhihu_scraper.app.web
pause
