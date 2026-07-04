@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\verify_project.ps1"
if %errorlevel% neq 0 (
  echo.
  echo 프로젝트 전체 검증에 실패했습니다.
  pause
  exit /b %errorlevel%
)
echo.
echo 프로젝트 전체 검증을 통과했습니다.
pause
