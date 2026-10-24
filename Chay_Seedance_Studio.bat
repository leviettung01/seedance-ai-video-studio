@echo off
chcp 65001 >nul
title Seedance AI Video Studio PRO v5.0 (PyQt6)

echo ====================================================
echo   Seedance AI Video Studio PRO v5.0 - PyQt6 GUI
echo   Professional Desktop Application
echo   Auto Login VIA FB, Cookie Persistence, Job Tracker
echo ====================================================
echo.

REM 1. Giai phong cong 8899 neu dang bi chiem dung
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8899" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

REM 2. Chuyen den thu muc ma nguon dua theo duong dan file .bat (khong hardcode o dia F:\)
cd /d "%~dp0seedance_ai_video_studio_src"

if not exist "main_gui_pyqt.py" (
    echo [LOI] Khong tim thay tap tin main_gui_pyqt.py!
    echo Vui long dam bao thu muc "seedance_ai_video_studio_src" nam cung thu muc voi file .bat nay.
    pause
    exit /b 1
)

REM 3. Tu dong tim kiem moi truong Python tuong thich (co ho tro PyQt6)
set "PYTHON_EXE="

REM Uu tien Python 3.10 he thong (da cai day du PyQt6)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" -c "import PyQt6.QtWidgets" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    )
)

REM Kiem tra venv cuc bo neu co
if not defined PYTHON_EXE if exist "%~dp0seedance_ai_video_studio_src\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0seedance_ai_video_studio_src\venv\Scripts\python.exe"
)
if not defined PYTHON_EXE if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
)

REM Kiem tra python mac dinh trong PATH
if not defined PYTHON_EXE (
    python -c "import PyQt6.QtWidgets" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    )
)

REM Neu van chua tim thay Python co PyQt6, fallback ve Python 3.10 hoac python PATH
if not defined PYTHON_EXE (
    if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
        set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    ) else (
        set "PYTHON_EXE=python"
    )
)

echo [INFO] Thu muc lam viec : %cd%
echo [INFO] Python su dung   : %PYTHON_EXE%
echo Dang khoi chay Seedance Studio PRO v5.0 (PyQt6)...
echo.

"%PYTHON_EXE%" main_gui_pyqt.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ====================================================
    echo [THONG BAO] Ung dung da dung lai hoac gap loi!
    echo Ma loi (Exit code): %ERRORLEVEL%
    echo ====================================================
    pause
)

