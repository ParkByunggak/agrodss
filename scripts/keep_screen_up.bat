@echo off
REM keep_screen_up.bat - if the internal screen is not listening, start it. Otherwise do nothing and exit.
REM
REM [publisher 2026-09-21 "can code run run_frontend.bat itself?"] No - the session runs on a remote Linux container and
REM the screen runs on this PC, so nothing the session does can start a process here. What CAN be done is make this PC
REM keep it up: this file is the check, install_autostart.bat registers it with the Windows scheduler.
REM
REM ASCII ONLY (cmd reads a batch in the console code page - cp949 on Korean Windows). No parentheses inside redirected
REM blocks (live_check.bat learned that the hard way: a ")" closes the block early and nothing runs).
REM
REM This file is IDEMPOTENT and quiet: if the port answers it exits 0 without printing, so running it every few minutes
REM costs nothing. It never kills anything - it only starts what is not there.
setlocal
cd /d "%~dp0\.."
set "PORT=8765"
if not "%AGRODSS_FRONTEND_PORT%"=="" set "PORT=%AGRODSS_FRONTEND_PORT%"

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 goto alive

echo [agrodss] screen is not listening on %PORT% - starting run_frontend.bat
start "agrodss" /min cmd /c "run_frontend.bat"
exit /b 0

:alive
exit /b 0
