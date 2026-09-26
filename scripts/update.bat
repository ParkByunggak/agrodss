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
REM nothing. Nothing else is DISCARDED - this file never throws your work away.
REM
REM [swept 2026-09-21] parcels.json was not the only file of that shape. Tracked files under data\ that are still
REM written while the app runs: crop_names.csv (approving a name) and organic\organic_materials_public.json (refreshing
REM the materials canon). [U-24 2026-09-26] subjects.json left this list - runtime writes now go to
REM data\subjects_local.json (git-ignored), the seed file is only changed by commits. If one of those is edited here AND the
REM pull carries a change to the same file, git stops with "commit or stash" and you are stuck on old code again -
REM which is exactly the days-long stall this script exists to end. So before pulling, any locally edited tracked file
REM under data\ is COPIED to data\_local_backup\ (git-ignored) and then restored, and this window says which ones.
REM Copied, not discarded: nothing you typed is lost, and the session can merge it back.
REM
REM ASCII ONLY (cmd reads a batch in the console code page - cp949 on Korean Windows).
REM No parentheses inside blocks - live_check.bat died that way once: a ")" closes the block early.
setlocal
cd /d "%~dp0.."
set "PORT=8765"
if not "%AGRODSS_FRONTEND_PORT%"=="" set "PORT=%AGRODSS_FRONTEND_PORT%"
set "HOSTPORT=127.0.0.1:%PORT%"

set "OLD="
for /f "delims=" %%h in ('git rev-parse --short HEAD 2^>nul') do set "OLD=%%h"
echo [agrodss] code here now: %OLD%

git diff --quiet -- data/parcels.json
if errorlevel 1 git checkout -- data/parcels.json

for /f "tokens=*" %%f in ('git diff --name-only -- data/ 2^>nul') do call :preserve "%%f"

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

REM [publisher 2026-09-23] This used to print "the screen SHOULD now be running <new>" and stop. That is a CLAIM,
REM not a measurement - and a claim is exactly what cost this project days: a pull lands, the already-running
REM process keeps serving the OLD build, and nothing says so. Ask the screen what it is running and compare.
call :measure
if "%RUNNING%"=="%NEW%" goto isnew
if "%RUNNING%"=="" goto cannotask

echo [agrodss] the screen is still running %RUNNING% - it cannot swap itself onto the fix (R-6). Restarting it.
call :restart
call :measure
if "%RUNNING%"=="%NEW%" goto isnew

echo.
echo [ERROR] the screen is running %RUNNING% but the code here is %NEW%.
echo [ERROR] close the black "agrodss" window by hand and double-click run_frontend.bat, then paste this window.
echo.
pause
exit /b 1

:isnew
echo.
echo [agrodss] measured: the screen is running %NEW%. This is the newest code.
echo [agrodss] the footer should show the AI notice, centred, with the address ONCE.
echo.
pause
exit /b 0

:cannotask
echo.
echo [agrodss] could not ask the screen what it is running (no curl, or it is not up yet).
echo [agrodss] open http://%HOSTPORT%/changes - it says "reflected" or "behind" at the top.
echo.
pause
exit /b 0

REM Ask the screen itself. Writes RUNNING = the commit the PROCESS started on (empty if it cannot be asked).
:measure
set "RUNNING="
del "%TEMP%\agrodss_running.txt" >nul 2>&1
curl -s -m 5 "http://%HOSTPORT%/running" > "%TEMP%\agrodss_running.txt" 2>nul
for /f "tokens=2 delims==" %%h in ('findstr /B /C:"head=" "%TEMP%\agrodss_running.txt" 2^>nul') do set "RUNNING=%%h"
del "%TEMP%\agrodss_running.txt" >nul 2>&1
goto :eof

REM Stop ONLY the process listening on our port, then let keep_screen_up start it again.
REM Never a blanket taskkill - the port pins exactly one process and nothing else is touched.
:restart
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do call :killpid %%p
timeout /t 3 /nobreak >nul
call "%~dp0keep_screen_up.bat"
timeout /t 5 /nobreak >nul
goto :eof

:killpid
echo [agrodss] stopping the old screen - PID %1 on port %PORT%
taskkill /PID %1 /F >nul 2>&1
goto :eof

:pullfailed
echo.
echo [ERROR] git pull failed - see the message above. NOTHING was changed or discarded.
echo [ERROR] paste that message into the session instead of working around it by hand.
echo.
pause
exit /b 1

REM Keep a copy of a locally edited tracked data file, then restore it so the pull can pass.
REM The copy comes FIRST - if it fails, the restore does not happen and we stop rather than lose the file.
:preserve
set "P=%~1"
set "P=%P:/=\%"
if /i "%P%"=="data\parcels.json" goto :eof
if not exist "data\_local_backup" mkdir "data\_local_backup"
copy /y "%P%" "data\_local_backup\" >nul
if errorlevel 1 goto preservefailed
echo [agrodss] kept your local %P% in data\_local_backup\ - restoring it so the update can land
git checkout -- "%P%"
goto :eof

:preservefailed
echo.
echo [ERROR] could not copy %P% aside, so nothing was touched. Paste this window into the session.
pause
exit /b 1
