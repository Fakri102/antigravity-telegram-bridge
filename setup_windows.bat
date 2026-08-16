@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   🚀 Antigravity Telegram Bridge - Setup untuk Windows
echo ==========================================================
echo.

:: 1. Periksa Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ [ERROR] Python tidak ditemukan di sistem Anda!
    echo Silakan unduh dan instal Python dari: https://www.python.org/downloads/
    echo PENTING: Centang kotak "Add Python to PATH" saat instalasi.
    echo.
    pause
    exit /b 1
)

:: 2. Buat Virtual Environment jika belum ada
if not exist venv (
    echo 🐍 [1/3] Membuat Python Virtual Environment (venv)...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Gagal membuat venv.
        pause
        exit /b 1
    )
)

:: 3. Instal Dependencies
echo 📦 [2/3] Menginstal dependensi dari requirements.txt...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Gagal menginstal dependensi.
    pause
    exit /b 1
)

:: 4. Inisiasi Kredensial .env
echo.
echo ⚙️ [3/3] Menyiapkan kredensial bot Telegram...
venv\Scripts\python.exe init_config.py --setup

echo.
echo ==========================================================
echo ✅ Setup Selesai!
echo ==========================================================
echo Anda dapat menyalakan bot kapan saja dengan menjalankan:
echo   start.bat
echo ==========================================================
pause
