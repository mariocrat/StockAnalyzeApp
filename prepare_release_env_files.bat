@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
  echo Python venv was not found at %cd%\.venv\Scripts\python.exe
  pause
  exit /b 1
)

".venv\Scripts\python.exe" scripts\create_release_env_files.py
set SETUP_EXIT=%ERRORLEVEL%
echo.
pause
exit /b %SETUP_EXIT%
