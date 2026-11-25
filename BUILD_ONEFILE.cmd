@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0SETUP.cmd"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check "pyinstaller>=6,<7"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m unittest discover -s tests -q
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath "dist\onefile" --workpath "build\onefile" ManifestCleaner-onefile.spec
if errorlevel 1 goto failed
if not exist "dist\onefile\ManifestCleaner.exe" goto failed
".venv\Scripts\python.exe" -c "import sys, platform, importlib.metadata as m; from manifest_cleaner import __version__; print('Manifest Cleaner Windows one-file build'); print('App: '+__version__); print('Python: '+sys.version); print('Platform: '+platform.platform()); print('\n'.join(name+'=='+m.version(name) for name in ('pyinstaller','pandas','openpyxl','XlsxWriter','xlrd')))" > "dist\onefile\BUILD_INFO.txt"
if errorlevel 1 goto failed
echo.
echo Kết quả: dist\onefile\ManifestCleaner.exe
echo Gửi người dùng cuối đúng một file ManifestCleaner.exe. BUILD_INFO.txt chỉ để người build lưu lại.
echo File tự giải nén nên mỗi lần mở mất vài giây. settings.json và recent_files.json được tạo cạnh file exe.
echo Bản build chưa thay thế kiểm tra thủ công trên Windows. Đọc mục F của docs\WINDOWS_RELEASE_CHECKLIST.md.
pause
exit /b 0
:failed
echo Đóng gói chưa hoàn thành. Xem lỗi phía trên.
pause
exit /b 1
