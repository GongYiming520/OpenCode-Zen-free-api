@echo off
chcp 65001 >nul 2>nul
cd /d "%~dp0"
python test_api.py %*
echo.
pause
