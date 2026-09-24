@echo off
setlocal
"%SystemRoot%\System32\chcp.com" 65001 >nul
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0scripts\verify_project.ps1" %*
set "verify_exit=%errorlevel%"
if not "%verify_exit%"=="0" echo Project verification failed.
if "%verify_exit%"=="0" echo Project verification passed.
exit /b %verify_exit%
