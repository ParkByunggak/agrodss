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
REM [2026-09-21] tell serve.py a wrapper loop exists, so it exits with code 3 instead of re-execing itself.
REM Without this flag (e.g. PowerShell running serve.py directly) the server restarts itself on new code.
set "AGRODSS_WRAPPED=1"
set "BROWSER="
:again
%PY% frontend\serve.py %BROWSER%
set "RC=%errorlevel%"
if "%RC%"=="3" (
  REM [publisher 2026-09-19 21:40 "changes must show up right away"] the server saw git HEAD change - git pull landed - and
  REM shut itself down with code 3. Restart on the new code without opening another browser window; the page just reloads.
  echo [agrodss] code changed - restarting on new HEAD ...
  set "BROWSER=--no-browser"
  goto again
)
echo.
echo [agrodss] server stopped - exit code %RC%
pause
