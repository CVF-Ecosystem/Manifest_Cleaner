@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto setup
".venv\Scripts\python.exe" scripts\check_release.py --runtime-only >nul 2>&1
if not errorlevel 1 goto run
:setup
call "%~dp0SETUP.cmd"
if errorlevel 1 goto failed
:run
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Ứng dụng chưa chạy được. Xem thông báo phía trên hoặc mở START_HERE.html.
pause
exit /b 1
