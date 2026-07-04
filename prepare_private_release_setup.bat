@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set npm_config_update_notifier=false

echo Preparing private release setup files...
echo This creates or fills local private files that must not be committed.
echo Korean details will be printed by the Python and npm scripts.
echo.

set SETUP_EXIT=0
set BACKEND_REPORT_EXIT=0
set FRONTEND_REPORT_EXIT=0
set ALIGNMENT_REPORT_EXIT=0

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment was not found: %cd%\.venv\Scripts\python.exe
  goto :failed
)

echo [1/4] Create private release env files from templates
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
echo [2/4] Fill empty backend private token values
".venv\Scripts\python.exe" scripts\generate_release_secrets.py --fill-empty
if errorlevel 1 (
  set SETUP_EXIT=%ERRORLEVEL%
  goto :failed
)

echo.
echo [3/4] Prepare Android upload signing key
".venv\Scripts\python.exe" scripts\generate_android_upload_key.py --create-key
if errorlevel 1 (
  set SETUP_EXIT=%ERRORLEVEL%
  goto :failed
)

echo.
echo [4/4] Show release readiness reports
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\owner_release_report.py
if errorlevel 1 set BACKEND_REPORT_EXIT=1

echo.
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
echo Server/app release setting alignment
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\validate_release_alignment.py
if errorlevel 1 set ALIGNMENT_REPORT_EXIT=1

echo.
if "%BACKEND_REPORT_EXIT%%FRONTEND_REPORT_EXIT%%ALIGNMENT_REPORT_EXIT%"=="000" (
  echo Private release setup is complete.
) else (
  echo Private release setup finished, but some external values still need setup.
)
echo.
pause
exit /b 0

:failed
if "%SETUP_EXIT%"=="0" set SETUP_EXIT=1
echo.
echo Private release setup failed. Error code: %SETUP_EXIT%
echo Check the messages above, fix the issue, then run this file again.
echo.
pause
exit /b %SETUP_EXIT%
