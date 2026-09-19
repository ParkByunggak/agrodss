@echo off
REM live_check.bat - one click: (1) copy API keys from D:\vela\.env by name, (2) collect soil exam + fertilizer prescription
REM for the first cultivation unit, (3) run the live 3/3 reproduction. Writes a log WITHOUT values (statuses only) and opens
REM it in Notepad. Values (PNU, soil, prescription) stay in data\soil\ (git-ignored). Paste the Notepad text into the session.
REM
REM [code review D1/D11 2026-09-19] ASCII ONLY in this file: cmd reads a batch in the console code page (cp949 on Korean
REM Windows), so UTF-8 Korean literals arrive as broken bytes. Crop and address are resolved from the registries by the
REM cultivation-unit id (--subject), never written here (the address is PII). Delayed expansion so that the exit code
REM inside the ( ... ) block is the real one (plain %errorlevel% is expanded when the block is parsed).
setlocal enabledelayedexpansion
cd /d "%~dp0\.."
set "PY="
if exist "D:\vela\backend_new\venv\Scripts\python.exe" set "PY=D:\vela\backend_new\venv\Scripts\python.exe"
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
set "SUBJECT=p001-jjokpa-2026f"
set "LOG=%TEMP%\agrodss_live.txt"
(
  echo === agrodss live check %date% %time% ===
  git log --oneline -1
  echo.
  echo === 1. keys from D:\vela\.env (names only) ===
  %PY% scripts\env_from_vela.py
  echo exit code !errorlevel!
  echo.
  echo === 2. soil exam + prescription for %SUBJECT% (statuses only) ===
  %PY% -X utf8 -m ingest.fertilizer --subject=%SUBJECT% --summary
  echo exit code !errorlevel!
  echo.
  echo === 3. live 3/3 reproduction ===
  %PY% -X utf8 scripts\live_reproduce.py
  echo exit code !errorlevel!
) > "%LOG%" 2>&1
start notepad "%LOG%"
