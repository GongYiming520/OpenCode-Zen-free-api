@echo off
chcp 65001 >nul 2>nul
cd /d "%~dp0"
echo Starting OpenCode Zen bridge...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-zen.ps1" %*
echo.
pause
