@echo off
REM uninstall_autostart.bat - undo install_autostart.bat. Removes exactly what it can create and nothing else:
REM   the two task names          agrodss-screen-logon  agrodss-screen-watch
REM   the one Startup entry       %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\agrodss-screen.cmd
REM The installer has two ways and only one of them usually took, so a "task not found" line here is normal.
REM Does not stop a running screen or a running watcher - close those windows yourself if you want them down.
setlocal
set "ENTRY=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\agrodss-screen.cmd"

echo [agrodss] removing scheduled tasks
schtasks /Delete /TN "agrodss-screen-logon" /F
schtasks /Delete /TN "agrodss-screen-watch" /F

echo [agrodss] removing the Startup entry
if exist "%ENTRY%" del "%ENTRY%"

echo.
echo [agrodss] done. Windows no longer restarts the screen by itself.
pause
exit /b 0
