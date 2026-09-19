@echo off
setlocal
cd /d "%~dp0"
"%~dp0runtime\python.exe" "%~dp0app\scanner.py" backup
echo.
pause
