@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run.ps1" -BackupConfirmed -PreflightOnly
if errorlevel 1 goto :failed
echo.
echo Installation and game signatures are valid.
pause
exit /b 0

:failed
echo.
echo Verification failed. Read the error above.
pause
exit /b 1
