@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto setup
".venv\Scripts\python.exe" scripts\check_release.py --runtime-only >nul 2>&1
if not errorlevel 1 goto test
:setup
call "%~dp0SETUP.cmd"
if errorlevel 1 goto failed
:test
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
echo.
echo Các kiểm thử đã hoàn thành.
pause
exit /b 0
:failed
pause
exit /b 1
