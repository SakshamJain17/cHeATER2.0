@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo CodeKey setup is missing. Run setup_windows.bat first.>>codekey.log
  exit /b 1
)
start "" /b ".venv\Scripts\pythonw.exe" "launch.pyw"
exit /b 0
