@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set npm_config_update_notifier=false

echo 출시 준비용 개인 설정 파일을 준비합니다...
echo.
echo 이 작업은 GitHub에 올라가지 않는 내 PC의 개인 설정 파일만 만들거나 채웁니다.
echo API Key, 비밀번호, 서명 키 파일은 GitHub에 올리지 않습니다.
echo.

set SETUP_EXIT=0
set BACKEND_REPORT_EXIT=0
set FRONTEND_REPORT_EXIT=0
set ALIGNMENT_REPORT_EXIT=0

if not exist ".venv\Scripts\python.exe" (
  echo Python venv를 찾을 수 없습니다: %cd%\.venv\Scripts\python.exe
  goto :failed
)

echo [1/4] 출시 설정 파일을 템플릿에서 만듭니다
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
echo [2/4] 서버용 개인 토큰 빈칸을 채웁니다
".venv\Scripts\python.exe" scripts\generate_release_secrets.py --fill-empty
if errorlevel 1 (
  set SETUP_EXIT=%ERRORLEVEL%
  goto :failed
)

echo.
echo [3/4] Android 업로드 서명 키를 준비합니다
".venv\Scripts\python.exe" scripts\generate_android_upload_key.py --create-key
if errorlevel 1 (
  set SETUP_EXIT=%ERRORLEVEL%
  goto :failed
)

echo.
echo [4/4] 출시 준비 보고서를 보여줍니다
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\owner_release_report.py
if errorlevel 1 set BACKEND_REPORT_EXIT=1

echo.
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
echo 서버/앱 출시 설정 일치 검사
echo ----------------------------------------
".venv\Scripts\python.exe" backend\scripts\validate_release_alignment.py
if errorlevel 1 set ALIGNMENT_REPORT_EXIT=1

echo.
if "%BACKEND_REPORT_EXIT%%FRONTEND_REPORT_EXIT%%ALIGNMENT_REPORT_EXIT%"=="000" (
  echo 개인 출시 설정 준비가 완료됐습니다.
) else (
  echo 개인 출시 설정 준비 작업은 끝났습니다.
  echo 아직 외부에서 받아야 하는 값이나 직접 채워야 하는 항목이 남아 있습니다.
)
echo.
pause
exit /b 0

:failed
if "%SETUP_EXIT%"=="0" set SETUP_EXIT=1
echo.
echo 개인 출시 설정 준비가 실패했습니다. 오류 코드: %SETUP_EXIT%
echo 위 메시지를 확인해 고친 뒤 이 파일을 다시 실행하세요.
echo.
pause
exit /b %SETUP_EXIT%
