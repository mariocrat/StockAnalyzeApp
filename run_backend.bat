@echo off
netstat -ano | findstr /R /C:":8002 .*LISTENING" >nul
if %errorlevel%==0 (
  echo Backend is already running at http://127.0.0.1:8002
  exit /b 0
)
cd /d "%~dp0backend"
"%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8002
