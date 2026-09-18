@echo off
REM setup_agrodss.bat - populate D:\agrodss from GitHub (idempotent)
REM Usage: double-click, or run from any cmd/PowerShell window.
REM Messages are ASCII only so cp949 consoles show them intact.

setlocal
set "TARGET=D:\agrodss"
set "REMOTE=https://github.com/ParkByunggak/agrodss.git"

where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] git not found in PATH. Install Git for Windows first.
  goto :fail
)

if not exist "%TARGET%" (
  echo [1/3] %TARGET% does not exist - cloning...
  git clone "%REMOTE%" "%TARGET%"
  if errorlevel 1 goto :fail
  goto :verify
)

if exist "%TARGET%\.git" (
  echo [1/3] %TARGET% is already a git repo - syncing to origin/main...
  cd /d "%TARGET%"
  git remote get-url origin >nul 2>&1
  if errorlevel 1 git remote add origin "%REMOTE%"
  git fetch origin
  if errorlevel 1 goto :fail
  git checkout -B main origin/main
  if errorlevel 1 goto :fail
  goto :verify
)

REM Directory exists but is not a git repo (empty or not) - init in place.
REM Existing items (e.g. .claude, desktop.ini) are kept; checkout only fails
REM if a name collides with a tracked file (CLAUDE.md, docs\, scripts\, .gitignore).
echo [1/3] %TARGET% exists but is not a git repo. Current contents:
dir /a "%TARGET%"
echo       Initializing git in place and pulling origin/main...
cd /d "%TARGET%"
git init
if errorlevel 1 goto :fail
git remote add origin "%REMOTE%"
git fetch origin
if errorlevel 1 goto :fail
git checkout -B main origin/main
if errorlevel 1 (
  echo [ERROR] checkout failed - a local file collides with a tracked one.
  echo         Rename the colliding file shown above and run again.
  goto :fail
)
goto :verify

:verify
cd /d "%TARGET%"
echo [2/3] HEAD:
git log --oneline -1
echo [3/3] Files:
git ls-files
if not exist "%TARGET%\CLAUDE.md" (
  echo [ERROR] CLAUDE.md missing after sync - paste the output above.
  goto :fail
)
echo.
echo [OK] %TARGET% is ready. Open Claude Code here and paste section 3 of
echo      docs\agrodss_bootstrap_20260918.md as the first instruction.
pause
exit /b 0

:fail
echo.
echo [FAILED] See messages above. Paste them back to the session.
pause
exit /b 1
