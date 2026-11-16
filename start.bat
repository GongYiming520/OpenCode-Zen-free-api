@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>nul
cd /d "%~dp0"
title OpenCode Zen Bridge

rem ============================================================
rem  start.bat - one-click launcher for Windows
rem
rem    Double-click it, or run:
rem      start.bat
rem      start.bat --port 9000 --mode stateful
rem
rem  It checks Python, finds or installs opencode, creates an
rem  isolated data directory, then starts oc_bridge.py.
rem  Keep this window open while using the bridge; press Ctrl+C
rem  to stop it.
rem ============================================================

rem ---------- 1. Python ----------
set "PY="
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [start] Python 3 was not found.
  echo [start] Install it from https://www.python.org/downloads/
  echo [start] During installation, tick "Add Python to PATH".
  echo.
  pause
  exit /b 1
)
%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if errorlevel 1 (
  echo [start] Python 3.8 or newer is required.
  echo [start] Current version:
  %PY% --version
  echo.
  pause
  exit /b 1
)

rem ---------- 2. opencode ----------
rem Prefer .exe > .cmd > extensionless. The extensionless npm shim is a
rem shell script and cannot be launched directly by CreateProcess on Windows.
set "OCBIN="
if defined OPENCODE_BIN if exist "%OPENCODE_BIN%" set "OCBIN=%OPENCODE_BIN%"
if not defined OCBIN call :findoc

if not defined OCBIN (
  echo [start] opencode was not found. Installing it with npm ...
  where npm >nul 2>nul
  if errorlevel 1 (
    echo [start] Node.js / npm was not found.
    echo [start] Install Node.js 18+ from https://nodejs.org/ and run this file again.
    echo.
    pause
    exit /b 1
  )
  call npm i -g opencode-ai
  if errorlevel 1 (
    echo [start] "npm i -g opencode-ai" failed.
    echo [start] Try running it manually in an elevated terminal, or install opencode
    echo [start] from https://opencode.ai and pass --opencode-bin PATH.
    echo.
    pause
    exit /b 1
  )
  set "OCBIN="
  call :findoc
)

if not defined OCBIN (
  echo [start] Still could not locate the opencode binary.
  echo [start] Run "opencode --version" once, or pass --opencode-bin PATH.
  echo.
  pause
  exit /b 1
)

rem ---------- 3. isolated data directory ----------
set "BRIDGE_HOME=%CD%\.opencode-home"
if not exist "%BRIDGE_HOME%" mkdir "%BRIDGE_HOME%" >nul 2>nul
set "PYTHONUTF8=1"

echo.
echo ============================================================
echo  OpenCode Zen Bridge
echo  opencode : %OCBIN%
echo  data dir : %BRIDGE_HOME%
echo  Keep this window open. Press Ctrl+C to stop the bridge.
echo ============================================================
echo.

rem ---------- 4. start ----------
%PY% -u "%CD%\oc_bridge.py" --opencode-bin "%OCBIN%" --home "%BRIDGE_HOME%" %*
if errorlevel 1 (
  echo.
  echo [start] The bridge exited with an error. See the message above.
  pause
)
endlocal
exit /b 0

rem ------------------------------------------------------------
:findoc
if defined OCBIN exit /b 0
for /f "delims=" %%P in ('where opencode.exe 2^>nul') do if not defined OCBIN set "OCBIN=%%P"
if defined OCBIN exit /b 0
for /f "delims=" %%P in ('where opencode.cmd 2^>nul') do if not defined OCBIN set "OCBIN=%%P"
if defined OCBIN exit /b 0

set "NP="
for /f "delims=" %%P in ('npm prefix -g 2^>nul') do set "NP=%%P"
if defined NP (
  for %%F in (
    "%NP%\opencode.exe"
    "%NP%\opencode.cmd"
    "%NP%\opencode"
    "%NP%\node_modules\opencode-ai\bin\opencode.exe"
    "%NP%\node_modules\opencode-ai\bin\opencode"
  ) do (
    if not defined OCBIN if exist "%%~fF" set "OCBIN=%%~fF"
  )
)
if defined OCBIN exit /b 0

for %%F in (
  "%LOCALAPPDATA%\opencode\bin\opencode.exe"
  "%USERPROFILE%\.opencode\bin\opencode.exe"
  "%APPDATA%\npm\opencode.cmd"
) do (
  if not defined OCBIN if exist "%%~fF" set "OCBIN=%%~fF"
)
exit /b 0
