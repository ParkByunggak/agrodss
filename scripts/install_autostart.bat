@echo off
REM install_autostart.bat - one double-click: let Windows keep the internal screen up.
REM
REM TWO WAYS, tried in order. The first that works wins, and this script says which one it was.
REM
REM   way 1  the Windows scheduler   agrodss-screen-logon (at logon) + agrodss-screen-watch (every 5 minutes)
REM                                  for THE CURRENT USER ONLY and interactive: /RU "%USERNAME%" /IT
REM                                  /IT is the point. Without it schtasks asks Windows for "run whether the
REM                                  user is logged on or not", which needs the "log on as a batch job" right -
REM                                  a standard account does not have it and is told "Access is denied".
REM                                  That is what happened on the publisher's PC (2026-09-21).
REM   way 2  the Startup folder      one .cmd in %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup that
REM                                  starts watch_screen.bat minimized. Writing a file inside your own profile
REM                                  is not a privilege, so this way cannot be refused for lack of rights.
REM                                  It watches while you are logged on - which is when the screen matters.
REM
REM This script never deletes anything. Undo with uninstall_autostart.bat: it removes exactly those two task
REM names and that one file, and nothing else.
REM
REM [not verified on Windows by the session] The session runs on a remote Linux container and cannot test
REM schtasks here (R-5: advice gets walked or measured first - and where it cannot be, that is said out loud).
REM What the gate does check: ASCII only, no multi-line blocks, task and file names match the uninstaller, the
REM port check comes before the start, and the refusal path leads somewhere instead of stopping.
REM If anything below still fails, paste this whole window into the session - do not work around it by hand.
setlocal
cd /d "%~dp0"
set "TASKDIR=%~dp0"
set "WATCH=%TASKDIR%keep_screen_up.bat"
set "LOOP=%TASKDIR%watch_screen.bat"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "ENTRY=%STARTUP%\agrodss-screen.cmd"

if not exist "%WATCH%" goto missing
if not exist "%LOOP%" goto missing

echo [agrodss] way 1 of 2: the Windows scheduler, for this account only
schtasks /Create /TN "agrodss-screen-logon" /TR "\"%WATCH%\"" /SC ONLOGON /RU "%USERNAME%" /IT /F
if errorlevel 1 goto fallback

schtasks /Create /TN "agrodss-screen-watch" /TR "\"%WATCH%\"" /SC MINUTE /MO 5 /RU "%USERNAME%" /IT /F
if errorlevel 1 goto fallback

echo [agrodss] the scheduler took it - at logon, and every 5 minutes.
goto started

:fallback
echo.
echo [agrodss] the scheduler refused. That is a permission on this PC, not a fault in the screen.
echo [agrodss] way 2 of 2: a Startup entry, which needs no permission at all
if not exist "%STARTUP%" goto nostartup
> "%ENTRY%" echo @echo off
>> "%ENTRY%" echo start "agrodss-watch" /min "%LOOP%"
if not exist "%ENTRY%" goto nostartup
echo [agrodss] wrote the Startup entry: %ENTRY%
echo [agrodss] it starts the 5-minute watcher, minimized, at every logon. Starting it now too.
start "agrodss-watch" /min "%LOOP%"

:started
echo.
echo [agrodss] done. Starting the screen once now so you do not have to wait.
call "%WATCH%"
echo.
echo [agrodss] check the bottom-right corner of the screen: the AI notice, and the address ONCE.
pause
exit /b 0

:missing
echo [ERROR] keep_screen_up.bat or watch_screen.bat is not next to this file.
echo Run scripts\update.bat first - these arrive together with it.
pause
exit /b 1

:nostartup
echo.
echo [ERROR] neither way worked: the scheduler refused, and this folder is not writable:
echo   %STARTUP%
echo.
echo This does NOT stop the screen. scripts\update.bat starts it directly, and so does
echo scripts\keep_screen_up.bat - the only thing missing is the automatic restart after a reboot.
echo.
echo By hand: press Win+R, type  shell:startup  and press Enter, then drop a shortcut to
echo   %LOOP%
echo into the folder that opens. Paste this whole window into the session and it gets fixed.
pause
exit /b 1
