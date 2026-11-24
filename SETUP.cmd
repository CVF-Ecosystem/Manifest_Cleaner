@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Manifest Cleaner - chuẩn bị môi trường local
if exist ".venv\Scripts\python.exe" goto install
call :try_python py -3.12
if not errorlevel 1 goto create
call :try_python py -3.11
if not errorlevel 1 goto create
call :try_python py -3.13
if not errorlevel 1 goto create
call :try_python py -3.10
if not errorlevel 1 goto create
call :try_python py -3
if not errorlevel 1 goto create
call :try_python python
if not errorlevel 1 goto create
echo Chưa tìm thấy Python 3.10-3.13 bản 64-bit có Tcl/Tk.
echo Cài hoặc sửa Python 3.12 64-bit cho tài khoản hiện tại, chọn thành phần Tcl/Tk, rồi chạy lại START.cmd.
exit /b 1
:create
%MC_PYTHON% -m venv .venv
if errorlevel 1 exit /b 1
:install
".venv\Scripts\python.exe" -c "import sys, struct, tkinter; assert (3,10) <= sys.version_info[:2] < (3,14) and struct.calcsize('P') == 8, 'Can Python 3.10-3.13 64-bit va Tcl/Tk.'"
if errorlevel 1 (
  echo Moi truong .venv khong dung Python/Tcl-Tk duoc ho tro.
  echo Doi ten thu muc .venv de giu ban cu, sua/cai Python 3.12 64-bit co Tcl/Tk, roi chay lai SETUP.cmd.
  exit /b 1
)
echo Cài thư viện vào thư mục .venv của ứng dụng. Lần chuẩn bị này cần kết nối để tải thư viện.
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Không tải đủ thư viện. Kiểm tra kết nối hoặc nhờ agent local cài từ kho thư viện offline.
  exit /b 1
)
".venv\Scripts\python.exe" scripts\check_release.py --runtime-only
if errorlevel 1 exit /b 1
echo Đã chuẩn bị xong. Các lần sử dụng manifest diễn ra local.
exit /b 0

:try_python
set "MC_PYTHON=%*"
%MC_PYTHON% -c "import sys, struct, tkinter; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
exit /b %errorlevel%
