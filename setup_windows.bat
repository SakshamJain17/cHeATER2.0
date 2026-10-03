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
set "HAS_WINGET=1"
where winget >nul 2>nul
if errorlevel 1 (
  set "HAS_WINGET=0"
  echo Windows Package Manager not found; checking for a manually configured llama.cpp runner.
) else (
  winget list --id ggml.llamacpp -e --accept-source-agreements 2>nul | findstr /i "ggml.llamacpp" >nul
  if errorlevel 1 (
    winget install --id ggml.llamacpp -e --accept-source-agreements --accept-package-agreements
    if errorlevel 1 goto failed
  )
)
py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe download_model.py
if errorlevel 1 goto failed
.venv\Scripts\python.exe main.py --check
if errorlevel 1 (
  if "%HAS_WINGET%"=="1" (
    echo Install llama.cpp using: winget install --id ggml.llamacpp -e
  ) else (
    echo Download llama.cpp for Windows from https://github.com/ggml-org/llama.cpp/releases
    echo Then set model.binary in config.yaml to the path of llama-cli.exe.
  )
  echo Then run this file again.
  pause
  exit /b 1
)
echo Setup complete. Double-click launch_windows.vbs to start CodeKey without a console window.
pause
exit /b 0
:failed
echo Setup failed. Check the error above and run this file again.
pause
exit /b 1
