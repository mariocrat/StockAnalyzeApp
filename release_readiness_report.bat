@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set npm_config_update_notifier=false
set REPORT_EXIT=0
set BACKEND_REPORT_EXIT=0
set FRONTEND_REPORT_EXIT=0
set ALIGNMENT_REPORT_EXIT=0

if exist ".env.release" (
  set ALPHAMATE_ENV_FILE=%cd%\.env.release
  echo 서버 출시 설정 파일을 사용합니다: %cd%\.env.release
)

if exist "frontend\.env.release" (
  set ALPHAMATE_FRONTEND_ENV_FILE=%cd%\frontend\.env.release
  echo 프론트/Android 출시 설정 파일을 사용합니다: %cd%\frontend\.env.release
)

if not exist ".venv\Scripts\python.exe" (
  echo Python venv를 찾을 수 없습니다: %cd%\.venv\Scripts\python.exe
  pause
  exit /b 1
)

echo [1/3] 서버 출시 준비 상태
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\owner_release_report.py
if errorlevel 1 set BACKEND_REPORT_EXIT=1

echo.
echo [2/3] 프론트/Android 출시 준비 상태
echo ----------------------------------------
if not exist "frontend\package.json" (
  echo frontend 프로젝트를 찾을 수 없습니다: %cd%\frontend
  set FRONTEND_REPORT_EXIT=1
) else (
  pushd frontend
  call npm.cmd run --silent release:report
  if errorlevel 1 set FRONTEND_REPORT_EXIT=1
  popd
)

echo.
echo [3/3] 서버/앱 출시 설정 일치 검사
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\validate_release_alignment.py
if errorlevel 1 set ALIGNMENT_REPORT_EXIT=1

if "%BACKEND_REPORT_EXIT%"=="1" set REPORT_EXIT=1
if "%FRONTEND_REPORT_EXIT%"=="1" set REPORT_EXIT=1
if "%ALIGNMENT_REPORT_EXIT%"=="1" set REPORT_EXIT=1

echo.
if "%REPORT_EXIT%"=="0" (
  echo 모든 출시 준비 검사를 통과했습니다.
) else (
  echo 아직 설정이 필요한 출시 준비 항목이 남아 있습니다.
)
echo.
pause
exit /b %REPORT_EXIT%
