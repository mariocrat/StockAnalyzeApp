@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python venv was not found at %cd%\.venv\Scripts\python.exe
  pause
  exit /b 1
)
".venv\Scripts\python.exe" backend\scripts\owner_release_report.py
set REPORT_EXIT=%ERRORLEVEL%
echo.
pause
exit /b %REPORT_EXIT%
