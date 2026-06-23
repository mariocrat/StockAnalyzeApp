@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set npm_config_update_notifier=false
set REPORT_EXIT=0
set BACKEND_REPORT_EXIT=0
set FRONTEND_REPORT_EXIT=0

if exist ".env.release" (
  set ALPHAMATE_ENV_FILE=%cd%\.env.release
  echo Using backend release env file: %cd%\.env.release
)

if exist "frontend\.env.release" (
  set ALPHAMATE_FRONTEND_ENV_FILE=%cd%\frontend\.env.release
  echo Using frontend release env file: %cd%\frontend\.env.release
)

if not exist ".venv\Scripts\python.exe" (
  echo Python venv was not found at %cd%\.venv\Scripts\python.exe
  pause
  exit /b 1
)

echo [1/2] Server release readiness
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\owner_release_report.py
if errorlevel 1 set BACKEND_REPORT_EXIT=1

echo.
echo [2/2] Frontend and Android release readiness
echo ----------------------------------------
if not exist "frontend\package.json" (
  echo Frontend project was not found at %cd%\frontend
  set FRONTEND_REPORT_EXIT=1
) else (
  pushd frontend
  call npm.cmd run --silent release:report
  if errorlevel 1 set FRONTEND_REPORT_EXIT=1
  popd
)

if "%BACKEND_REPORT_EXIT%"=="1" set REPORT_EXIT=1
if "%FRONTEND_REPORT_EXIT%"=="1" set REPORT_EXIT=1

echo.
if "%REPORT_EXIT%"=="0" (
  echo All release readiness checks passed.
) else (
  echo Some release readiness items still need setup.
)
echo.
pause
exit /b %REPORT_EXIT%
