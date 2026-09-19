@echo off
setlocal
cd /d "%~dp0"
echo Planetary Discovery Scanner v1.0.0 installer
echo This requires Python 3.13 x64 and an internet connection on first install.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
if errorlevel 1 goto :failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\deploy.ps1"
if errorlevel 1 goto :failed
echo.
echo Installation complete. Start the game with PLAY_NMS_WITH_SCANNER.cmd.
pause
exit /b 0

:failed
echo.
echo Installation failed. Read the error above; no unsupported game build was modified.
pause
exit /b 1
