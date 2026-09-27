@echo off
REM run_frontend.bat - start the internal screen (localhost only, opens a new browser window).
REM Finds a usable Python by itself (VELA venv first - CLAUDE.md venv rule), skips pip when markdown is present,
REM and keeps this window open at the end so any error stays visible (2026-09-19: blank console = Store alias stub).
REM [R-7 2026-09-27] cmd reads a batch by BYTE OFFSET while it runs, and this file runs for DAYS (it waits on the server
REM below, then restarts it on new code). A git pull that changes this file makes cmd resume inside the NEW file at the
REM OLD offset - exactly what update.bat did on 2026-09-27 ("'/f' is not recognized"). So a TEMP copy runs instead; the
REM repo folder comes in as an argument because %~dp0 inside the copy is TEMP. The hand-off is WITHOUT "call" so cmd
REM never comes back to this file.
REM The copy's name is different on every run - a fixed name would let a second start overwrite a copy that is still
REM running (the same trap, just moved). A few KB per start stay in TEMP.
if /i "%~1"=="--from-temp" goto :run
set "TMPBAT=%TEMP%\agrodss_run_frontend_%RANDOM%%RANDOM%.bat"
copy /y "%~f0" "%TMPBAT%" >nul
if errorlevel 1 goto :run
"%TMPBAT%" --from-temp "%~dp0"

:run
setlocal
set "HERE=%~2"
if "%HERE%"=="" set "HERE=%~dp0"
cd /d "%HERE%"
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
set "H0="
for /f "delims=" %%h in ('git rev-parse --short HEAD 2^>nul') do set "H0=%%h"
%PY% frontend\serve.py %BROWSER%
set "RC=%errorlevel%"
set "H1="
for /f "delims=" %%h in ('git rev-parse --short HEAD 2^>nul') do set "H1=%%h"
REM [publisher 2026-09-19 21:40 "changes must show up right away"] the server saw git HEAD change - git pull landed - and
REM shut itself down with code 3. Restart on the new code without opening another browser window; the page just reloads.
if "%RC%"=="3" goto restart
REM [R-6 2026-09-21] a race made the server exit 0 on a code change, so this loop never fired and the screen stayed dead
REM with no error at all. The race is fixed, but the build that is RUNNING when the fix arrives is the old one - it cannot
REM save its own restart. So judge by the SHAPE of the death: the code changed while it ran, yet it did not ask to restart.
REM That is the silent exit. Ctrl+C also exits 0, but then HEAD did not change, so this stays quiet.
if not "%H0%"=="%H1%" goto restart
goto stopped
:restart
echo [agrodss] code changed - restarting on new HEAD ...
set "BROWSER=--no-browser"
goto again
:stopped
echo.
echo [agrodss] server stopped - exit code %RC% (code was %H0%)
echo [agrodss] if the screen died with no error, just run this file again.
pause
