@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set npm_config_update_notifier=false

echo Preparing private release setup files...
echo.
echo This will create or update local ignored files only.
echo It will not add API keys or upload private files to GitHub.
echo.

set SETUP_EXIT=0
set BACKEND_REPORT_EXIT=0
set FRONTEND_REPORT_EXIT=0

if not exist ".venv\Scripts\python.exe" (
  echo Python venv was not found at %cd%\.venv\Scripts\python.exe
  goto :failed
)

echo [1/4] Creating release env files from templates
".venv\Scripts\python.exe" scripts\create_release_env_files.py
if errorlevel 1 (
  set SETUP_EXIT=%ERRORLEVEL%
  goto :failed
)

if exist ".env.release" (
  set ALPHAMATE_ENV_FILE=%cd%\.env.release
)

if exist "frontend\.env.release" (
  set ALPHAMATE_FRONTEND_ENV_FILE=%cd%\frontend\.env.release
)

echo.
echo [2/4] Filling private backend release token placeholders
".venv\Scripts\python.exe" scripts\generate_release_secrets.py --fill-empty
if errorlevel 1 (
  set SETUP_EXIT=%ERRORLEVEL%
  goto :failed
)

echo.
echo [3/4] Preparing private Android upload signing key
".venv\Scripts\python.exe" scripts\generate_android_upload_key.py --create-key
if errorlevel 1 (
  set SETUP_EXIT=%ERRORLEVEL%
  goto :failed
)

echo.
echo [4/4] Showing release readiness report
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\owner_release_report.py
if errorlevel 1 set BACKEND_REPORT_EXIT=1

echo.
if not exist "frontend\package.json" (
  echo Frontend project was not found at %cd%\frontend
  set FRONTEND_REPORT_EXIT=1
) else (
  pushd frontend
  call npm.cmd run --silent release:report
  if errorlevel 1 set FRONTEND_REPORT_EXIT=1
  popd
)

if "%BACKEND_REPORT_EXIT%"=="1" set SETUP_EXIT=1
if "%FRONTEND_REPORT_EXIT%"=="1" set SETUP_EXIT=1

echo.
if "%SETUP_EXIT%"=="0" (
  echo Private release setup is ready.
) else (
  echo Private release setup finished, but some release readiness items still need external values.
)
echo.
pause
exit /b %SETUP_EXIT%

:failed
if "%SETUP_EXIT%"=="0" set SETUP_EXIT=1
echo.
echo Private release setup failed with exit code %SETUP_EXIT%.
echo Fix the message above, then run this file again.
echo.
pause
exit /b %SETUP_EXIT%
