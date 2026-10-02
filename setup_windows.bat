@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.12 or newer from python.org, then run this file again.
  pause
  exit /b 1
)
py -3 -c "import sys; sys.exit(sys.version_info < (3, 12))"
if errorlevel 1 (
  echo Python 3.12 or newer is required.
  pause
  exit /b 1
)
py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe download_model.py
if errorlevel 1 goto failed
.venv\Scripts\python.exe main.py --check
if errorlevel 1 (
  echo Install llama.cpp using: winget install llama.cpp
  echo Then run this file again.
  pause
  exit /b 1
)
echo Setup complete. Double-click launch_windows.bat to start CodeKey.
pause
exit /b 0
:failed
echo Setup failed. Check the error above and run this file again.
pause
exit /b 1
