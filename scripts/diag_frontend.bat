@echo off
REM diag_frontend.bat - collect why the internal screen does not start; writes a log and opens it in Notepad.
REM Read-only: touches nothing in the repository. Paste the Notepad content into the chat.
setlocal
cd /d "%~dp0\.."
set "LOG=%TEMP%\agrodss_diag.txt"
set "VENV=D:\vela\backend_new\venv\Scripts\python.exe"
(
  echo === agrodss diag %date% %time% ===
  echo cwd=%cd%
  echo.
  echo === git ===
  git log --oneline -1
  git status --short
  echo.
  echo === python candidates ===
  where python
  where py
  echo.
  echo === VELA venv ===
  if exist "%VENV%" (echo venv exe: exists) else (echo venv exe: MISSING)
  type "D:\vela\backend_new\venv\pyvenv.cfg"
  "%VENV%" --version
  "%VENV%" -c "import sys; print('venv runs', sys.version)"
  echo.
  echo === py -3 ===
  py -3 --version
  py -3 -c "import sys; print('py runs', sys.version)"
  echo.
  echo === python ===
  python --version
  python -c "import sys; print('python runs', sys.version)"
  echo.
  echo === import check with venv ===
  "%VENV%" -c "import sys; sys.path.insert(0, '.'); import markdown; import frontend.serve; print('import ok')"
  echo.
  echo === import check with py -3 ===
  py -3 -c "import sys; sys.path.insert(0, '.'); import markdown; import frontend.serve; print('import ok')"
  echo.
  echo === bind check with venv - .env BIND / token / port ===
  "%VENV%" -c "import sys; sys.path.insert(0, '.'); from frontend import serve, config; print('BIND', config.BIND, 'PORT', config.PORT, 'token set', bool(config.LAN_TOKEN)); s = serve.make_server(); print('bind ok', s.server_address); s.server_close()"
  echo.
  echo === git ===
  git log --oneline -1
  git status --short
  echo.
  echo === port 8765 ===
  netstat -ano | findstr :8765
  echo.
  echo === VELA 8000 ===
  netstat -ano | findstr :8000
) > "%LOG%" 2>&1
start notepad "%LOG%"
