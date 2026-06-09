@echo off
cd /d "%~dp0"

netstat -ano | findstr /R /C:":8002 .*LISTENING" >nul
if %errorlevel%==0 (
  echo Backend is already running at http://127.0.0.1:8002
) else (
  start "StockAnalyze Backend" cmd /k "%~dp0run_backend.bat"
  timeout /t 5 /nobreak >nul
)

netstat -ano | findstr /R /C:":5174 .*LISTENING" >nul
if %errorlevel%==0 (
  echo Frontend is already running at http://127.0.0.1:5174
) else (
  start "StockAnalyze Frontend" cmd /k "%~dp0run_frontend.bat"
  timeout /t 3 /nobreak >nul
)

start http://127.0.0.1:5174
