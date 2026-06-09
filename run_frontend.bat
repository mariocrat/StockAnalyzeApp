@echo off
netstat -ano | findstr /R /C:":5174 .*LISTENING" >nul
if %errorlevel%==0 (
  echo Frontend is already running at http://127.0.0.1:5174
  exit /b 0
)
cd /d "%~dp0frontend"
set VITE_API_BASE=http://127.0.0.1:8002
cmd /c npm run dev -- --host 127.0.0.1 --port 5174
