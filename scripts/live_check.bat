@echo off
REM live_check.bat - one click: (1) copy API keys from D:\vela\.env by name, (2) collect soil exam + fertilizer prescription
REM for parcel p001, (3) run the live 3/3 reproduction. Writes a log WITHOUT values (statuses only) and opens it in Notepad.
REM Values (PNU, soil, prescription) stay in data\soil\ (git-ignored). Paste the Notepad text into the session.
setlocal
cd /d "%~dp0\.."
set "PY="
if exist "D:\vela\backend_new\venv\Scripts\python.exe" set "PY=D:\vela\backend_new\venv\Scripts\python.exe"
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
set "LOG=%TEMP%\agrodss_live.txt"
(
  echo === agrodss live check %date% %time% ===
  git log --oneline -1
  echo.
  echo === 1. keys from D:\vela\.env (names only) ===
  %PY% scripts\env_from_vela.py
  echo.
  echo === 2. soil exam + prescription for p001 (statuses only) ===
  %PY% -m ingest.fertilizer "충청북도 괴산군 연풍면 갈금리 50" --parcel=p001 --crop=쪽파 --summary
  echo.
  echo === 3. live 3/3 reproduction ===
  %PY% scripts\live_reproduce.py
  echo exit code %errorlevel%
) > "%LOG%" 2>&1
start notepad "%LOG%"
