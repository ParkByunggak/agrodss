@echo off
REM run_frontend.bat - start the internal screen (localhost only, opens a new browser window).
REM Finds a usable Python by itself (VELA venv first - CLAUDE.md venv rule), skips pip when markdown is present,
REM and keeps this window open at the end so any error stays visible (2026-09-19: blank console = Store alias stub).
setlocal
cd /d "%~dp0"
set "PY="
if exist "D:\vela\backend_new\venv\Scripts\python.exe" set "PY=D:\vela\backend_new\venv\Scripts\python.exe"
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo [ERROR] no usable Python found. Install Python 3.9+ or edit PY= in this file.
  pause
  exit /b 1
)
echo [agrodss] python = %PY%
%PY% --version
%PY% -c "import markdown" >nul 2>&1
if errorlevel 1 (
  echo [agrodss] installing requirements ...
  %PY% -m pip install -q -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] pip install failed - see above. Try: %PY% -m pip install markdown
    pause
    exit /b 1
  )
)
%PY% frontend\serve.py
echo.
echo [agrodss] server stopped (exit code %errorlevel%)
pause
