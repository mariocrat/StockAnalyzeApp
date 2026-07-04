@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set npm_config_update_notifier=false
set REPORT_EXIT=0
set BACKEND_REPORT_EXIT=0
set FRONTEND_REPORT_EXIT=0
set ALIGNMENT_REPORT_EXIT=0

if exist ".env.release" (
  set ALPHAMATE_ENV_FILE=%cd%\.env.release
  echo Using backend release env: %cd%\.env.release
)

if exist "frontend\.env.release" (
  set ALPHAMATE_FRONTEND_ENV_FILE=%cd%\frontend\.env.release
  echo Using frontend/Android release env: %cd%\frontend\.env.release
)

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment was not found: %cd%\.venv\Scripts\python.exe
  pause
  exit /b 1
)

echo [1/3] Backend release readiness
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\owner_release_report.py
if errorlevel 1 set BACKEND_REPORT_EXIT=1

echo.
echo [2/3] Frontend/Android release readiness
echo ----------------------------------------
if not exist "frontend\package.json" (
  echo Frontend project was not found: %cd%\frontend
  set FRONTEND_REPORT_EXIT=1
) else (
  pushd frontend
  call npm.cmd run --silent release:report
  if errorlevel 1 set FRONTEND_REPORT_EXIT=1
  popd
)

echo.
echo [3/3] Server/app release setting alignment
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\validate_release_alignment.py
if errorlevel 1 set ALIGNMENT_REPORT_EXIT=1

if "%BACKEND_REPORT_EXIT%"=="1" set REPORT_EXIT=1
if "%FRONTEND_REPORT_EXIT%"=="1" set REPORT_EXIT=1
if "%ALIGNMENT_REPORT_EXIT%"=="1" set REPORT_EXIT=1

echo.
if "%REPORT_EXIT%"=="0" (
  echo Every release readiness check passed.
) else (
  echo Some release readiness items still need setup.
)
echo.
pause
exit /b %REPORT_EXIT%
