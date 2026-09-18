@echo off
REM run_frontend.bat - start the internal screen (localhost only, opens a new browser window)
setlocal
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed - see above.
  pause
  exit /b 1
)
python frontend\serve.py
