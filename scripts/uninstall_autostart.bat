@echo off
REM uninstall_autostart.bat - undo install_autostart.bat. Removes exactly the two task names it created and nothing else.
REM Does not stop a running screen - close that window yourself if you want it down.
setlocal
echo [agrodss] removing scheduled tasks
schtasks /Delete /TN "agrodss-screen-logon" /F
schtasks /Delete /TN "agrodss-screen-watch" /F
echo.
echo [agrodss] done. Windows no longer restarts the screen by itself.
pause
exit /b 0
