@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup-save.ps1" -SaveDirectory "%APPDATA%\HelloGames\NMS"
if errorlevel 1 goto :failed
echo.
echo Backup completed and verified.
pause
exit /b 0

:failed
echo.
echo Backup failed. Read the error above.
pause
exit /b 1
