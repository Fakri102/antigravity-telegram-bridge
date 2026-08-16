@echo off
setlocal
cd /d "%~dp0"

:: Tentukan Python binary
if exist venv\Scripts\python.exe (
    set "PYTHON_EXEC=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXEC=python"
)

:: Periksa file .env
if not exist .env (
    echo [INFO] File .env belum ditemukan.
    echo Memulai wizard inisiasi kredensial...
    %PYTHON_EXEC% init_config.py --setup
    if errorlevel 1 exit /b 1
)

:: Jalankan Bot
echo ==========================================================
echo   Menjalankan Antigravity Telegram Bridge (Windows)
echo ==========================================================
%PYTHON_EXEC% bot.py

if errorlevel 1 (
    echo.
    echo Bot terhenti karena kesalahan.
    pause
)
