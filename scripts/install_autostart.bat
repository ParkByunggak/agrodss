@echo off
REM install_autostart.bat - one double-click: let Windows keep the internal screen up.
REM
REM Registers two scheduled tasks for the CURRENT USER (no admin rights needed, nothing system-wide):
REM   agrodss-screen-logon    runs keep_screen_up.bat when you log on
REM   agrodss-screen-watch    runs keep_screen_up.bat every 5 minutes
REM keep_screen_up.bat starts run_frontend.bat ONLY when the port is not listening, so this never doubles the server.
REM
REM Undo with uninstall_autostart.bat - it removes exactly these two task names and nothing else.
REM
REM [not verified on Windows by the session] The session runs on Linux and cannot test schtasks here. What was checked:
REM ASCII only, no parentheses inside blocks, task names match the uninstaller, and the port check comes before the start.
REM If schtasks reports an error, paste it into the session and it gets fixed - do not work around it by hand.
setlocal
cd /d "%~dp0"
set "TASKDIR=%~dp0"
set "WATCH=%TASKDIR%keep_screen_up.bat"

if not exist "%WATCH%" goto missing

echo [agrodss] registering: run at logon
schtasks /Create /TN "agrodss-screen-logon" /TR "\"%WATCH%\"" /SC ONLOGON /F
if errorlevel 1 goto failed

echo [agrodss] registering: check every 5 minutes
schtasks /Create /TN "agrodss-screen-watch" /TR "\"%WATCH%\"" /SC MINUTE /MO 5 /F
if errorlevel 1 goto failed

echo.
echo [agrodss] done. The screen now comes back by itself - at logon and within 5 minutes of any stop.
echo [agrodss] starting it once now so you do not have to wait.
call "%WATCH%"
echo.
pause
exit /b 0

:missing
echo [ERROR] keep_screen_up.bat not found next to this file.
pause
exit /b 1

:failed
echo.
echo [ERROR] schtasks failed - see the message above. Paste it into the session.
pause
exit /b 1
