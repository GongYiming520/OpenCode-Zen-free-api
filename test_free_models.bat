@echo off
chcp 65001 >nul 2>nul
cd /d "%~dp0"
python test_free_models.py %*
echo.
pause
