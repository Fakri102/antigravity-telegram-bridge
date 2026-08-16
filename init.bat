@echo off
setlocal
cd /d "%~dp0"

:: Cek Python di venv atau sistem
if exist venv\Scripts\python.exe (
    set "PYTHON_EXEC=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXEC=python"
)

:: Jalankan wizard inisiasi
%PYTHON_EXEC% init_config.py --setup %*
if errorlevel 1 (
    echo.
    echo Inisiasi dibatalkan atau terjadi kesalahan.
)
pause
