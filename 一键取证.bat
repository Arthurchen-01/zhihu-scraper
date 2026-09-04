@echo off
chcp 65001 >nul
title 知乎负面证据全量取证与人员穿透系统

echo ========================================================
echo   知乎负面证据全量取证与可疑人员穿透系统 (本地一键运行)
echo ========================================================
echo.

cd /d "%~dp0"

REM 检查是否有 uv 或 python
where uv >nul 2>nul
if %ERRORLEVEL% equ 0 (
    uv run python run_evidence_pipeline.py
) else (
    python run_evidence_pipeline.py
)

echo.
echo ========================================================
echo   排查完成！证据文件已保存在 outputs 目录下。
echo ========================================================
pause
