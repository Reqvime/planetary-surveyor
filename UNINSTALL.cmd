@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\uninstall.ps1"
if errorlevel 1 goto :failed
echo.
echo Runtime mod files removed. This project folder can now be deleted manually.
pause
exit /b 0

:failed
echo.
echo Uninstall failed. Read the error above; unknown files were left untouched.
pause
exit /b 1
