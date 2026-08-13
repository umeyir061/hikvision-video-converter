@echo off
setlocal
chcp 65001 >nul
set "APP_DIR=%~dp0"

where pythonw.exe >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw.exe "%APP_DIR%hikvision_video_duzeltici.py" %*
    exit /b 0
)

where python.exe >nul 2>&1
if %errorlevel% equ 0 (
    python.exe "%APP_DIR%hikvision_video_duzeltici.py" %*
    exit /b %errorlevel%
)

echo Python was not found. Python 3 is required.
pause
exit /b 1
