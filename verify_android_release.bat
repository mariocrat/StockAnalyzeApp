@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\verify_android_release.ps1"
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Android release build verification failed. Error code: %EXIT_CODE%
  if "%ALPHAMATE_NO_PAUSE%"=="1" exit /b %EXIT_CODE%
  pause
  exit /b %EXIT_CODE%
)
echo.
echo Android release build verification passed.
if not "%ALPHAMATE_NO_PAUSE%"=="1" pause
exit /b 0
