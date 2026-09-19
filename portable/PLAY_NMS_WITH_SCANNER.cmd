@echo off
setlocal
cd /d "%~dp0"
"%~dp0runtime\python.exe" "%~dp0app\scanner.py" play
if errorlevel 1 (
    echo.
    echo The game was not started. Read the message above.
    pause
    exit /b 1
)
exit /b 0
