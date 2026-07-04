@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\verify_android_debug.ps1"
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Android 디버그 빌드 검증에 실패했습니다. 오류 코드: %EXIT_CODE%
  pause
  exit /b %EXIT_CODE%
)
echo.
echo Android 디버그 빌드 검증을 통과했습니다.
pause
