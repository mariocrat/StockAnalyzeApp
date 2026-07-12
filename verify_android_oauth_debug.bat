@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\verify_android_oauth_debug.ps1"
if errorlevel 1 (
  echo.
  echo Android OAuth test APK build failed.
  if "%ALPHAMATE_NO_PAUSE%"=="1" exit /b 1
  pause
  exit /b 1
)
echo.
echo Android OAuth test APK build passed.
if not "%ALPHAMATE_NO_PAUSE%"=="1" pause
exit /b 0
