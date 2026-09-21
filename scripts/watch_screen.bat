@echo off
REM watch_screen.bat - the fallback watcher: call keep_screen_up.bat every 5 minutes, forever.
REM
REM [publisher 2026-09-21] install_autostart.bat asked the Windows scheduler and got "Access is denied".
REM The scheduler is a PRIVILEGE. A loop is not. This file needs nothing but the right to run a batch in
REM your own session, so it cannot be refused for lack of rights.
REM
REM install_autostart.bat starts this (minimized) and writes a one-line Startup entry that starts it again at
REM every logon. Close the window and the watching stops - the screen itself keeps running, and the next logon
REM brings the watcher back. Nothing here kills anything: keep_screen_up.bat only starts what is not there.
REM
REM ASCII ONLY - cmd reads a batch in the console code page (cp949 on Korean Windows).
REM No multi-line blocks - a ")" inside one closes it early (live_check.bat died of exactly that).
setlocal
cd /d "%~dp0"
set "EVERY=300"
if not "%AGRODSS_WATCH_SECONDS%"=="" set "EVERY=%AGRODSS_WATCH_SECONDS%"

echo [agrodss] watching the screen - a check every %EVERY% seconds. Closing this window stops the watching.

:loop
call "%~dp0keep_screen_up.bat"
timeout /t %EVERY% /nobreak >nul
goto loop
