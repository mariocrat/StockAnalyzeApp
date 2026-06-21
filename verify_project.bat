@echo off
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\verify_project.ps1"
if %errorlevel% neq 0 (
  echo.
  echo Project verification failed.
  pause
  exit /b %errorlevel%
)
echo.
echo Project verification passed.
pause
