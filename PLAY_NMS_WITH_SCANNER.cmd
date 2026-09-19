@echo off
setlocal
cd /d "%~dp0"
echo Planetary Discovery Scanner v1.0.0
echo The mod changes discovery state in your active save.
choice /C YN /N /M "Do you have a separate save backup? [Y/N] "
if errorlevel 2 exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run.ps1" -BackupConfirmed
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo Launch failed. Read the error above.
pause
exit /b 1
