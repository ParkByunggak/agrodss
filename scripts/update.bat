@echo off
REM update.bat - one double-click: get the newest code and bring the screen back ON it.
REM
REM [publisher 2026-09-21] The footer read "running 225cf9f" twice in a row - the pull had not landed. Typing git in the
REM right folder is friction, and that friction is why the screen ran days-old code. This file removes the typing:
REM double-click, read the last line, done. It also KEEPS THE WINDOW OPEN - the old version had no pause, so a
REM double-click flashed and vanished with the output unread.
REM
REM [R-6] The old last line here said "the screen server restarts itself when HEAD changed". That is NOT true, and it is
REM exactly what went wrong: a race made the server exit 0 instead of asking for a restart. Even after that fix, the
REM build that is RUNNING when the fix arrives is the old one - it cannot restart itself onto its own repair. So this
REM file brings the screen back itself, through keep_screen_up.bat (which starts it only when the port is dead).
REM
REM U-18: the old registry file data\parcels.json was tracked and runtime writes modified it, so pull stopped with
REM "commit or stash". Its values live in data\parcels_local.json (git-ignored) now, so discarding that one edit loses
REM nothing. Nothing else is touched - this file never discards your work.
REM
REM ASCII ONLY (cmd reads a batch in the console code page - cp949 on Korean Windows).
REM No parentheses inside blocks - live_check.bat died that way once: a ")" closes the block early.
setlocal
cd /d "%~dp0.."

set "OLD="
for /f "delims=" %%h in ('git rev-parse --short HEAD 2^>nul') do set "OLD=%%h"
echo [agrodss] code here now: %OLD%

git diff --quiet -- data/parcels.json
if errorlevel 1 git checkout -- data/parcels.json

echo [agrodss] pulling ...
git pull origin main
if errorlevel 1 goto pullfailed

set "NEW="
for /f "delims=" %%h in ('git rev-parse --short HEAD 2^>nul') do set "NEW=%%h"
if "%OLD%"=="%NEW%" goto same

echo [agrodss] %OLD% -^> %NEW%
echo [agrodss] waiting for the old screen to stop - it cannot restart itself onto the fix
timeout /t 8 /nobreak >nul
goto start

:same
echo [agrodss] already newest - nothing to pull.

:start
call "%~dp0keep_screen_up.bat"
echo.
echo [agrodss] done. The screen should now be running %NEW%
echo [agrodss] check the footer: the AI notice, and the address ONCE.
echo.
pause
exit /b 0

:pullfailed
echo.
echo [ERROR] git pull failed - see the message above. NOTHING was changed or discarded.
echo [ERROR] paste that message into the session instead of working around it by hand.
echo.
pause
exit /b 1
