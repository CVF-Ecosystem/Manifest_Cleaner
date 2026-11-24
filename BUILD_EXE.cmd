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
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean ManifestCleaner.spec
if errorlevel 1 goto failed
if not exist "dist\ManifestCleaner\ManifestCleaner.exe" goto failed
copy /y START_HERE.html "dist\ManifestCleaner\START_HERE.html" >nul
if errorlevel 1 goto failed
copy /y README.md "dist\ManifestCleaner\README.md" >nul
if errorlevel 1 goto failed
xcopy "docs\*" "dist\ManifestCleaner\docs" /E /I /Y /Q >nul
if errorlevel 1 goto failed
xcopy "samples\*" "dist\ManifestCleaner\samples" /E /I /Y /Q >nul
if errorlevel 1 goto failed
copy /y settings.example.json "dist\ManifestCleaner\settings.example.json" >nul
if errorlevel 1 goto failed
copy /y docs\WINDOWS_RELEASE_CHECKLIST.md "dist\ManifestCleaner\WINDOWS_RELEASE_CHECKLIST.md" >nul
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import sys, platform, importlib.metadata as m; from manifest_cleaner import __version__; print('Manifest Cleaner Windows local build'); print('App: '+__version__); print('Python: '+sys.version); print('Platform: '+platform.platform()); print('\n'.join(name+'=='+m.version(name) for name in ('pyinstaller','pandas','openpyxl','XlsxWriter','xlrd')))" > "dist\ManifestCleaner\BUILD_INFO.txt"
if errorlevel 1 goto failed
echo.
echo Kết quả: dist\ManifestCleaner\ManifestCleaner.exe
echo Khi chuyển máy khác, chuyển cả thư mục dist\ManifestCleaner, không chỉ file exe.
echo Bản build chưa thay thế kiểm tra thủ công trên Windows. Đọc WINDOWS_RELEASE_CHECKLIST.md trong thư mục kết quả.
pause
exit /b 0
:failed
echo Đóng gói chưa hoàn thành. Xem lỗi phía trên.
pause
exit /b 1
