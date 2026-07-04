@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo Preparing private Android upload signing key...
echo Korean details will be printed by the Python script.
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment was not found: %cd%\.venv\Scripts\python.exe
  echo Run setup first, then try again.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" scripts\generate_android_upload_key.py --create-key
set SETUP_EXIT=%ERRORLEVEL%
echo.
pause
exit /b %SETUP_EXIT%
