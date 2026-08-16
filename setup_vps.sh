#!/bin/bash
# ==============================================================================
# Antigravity Telegram Bridge - 1-Click VPS Setup Script (Ubuntu / Debian)
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 Memulai Setup Antigravity Telegram Bridge di Linux VPS"
echo "=========================================================="

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 1. Update paket OS dan instal dependencies sistem
echo "📦 [1/5] Memeriksa & Menginstal dependensi sistem (Python, FFmpeg, Git, Curl)..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-venv python3-pip ffmpeg git curl
elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y python3 python3-pip ffmpeg git curl
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm python python-pip ffmpeg git curl
else
    echo "⚠️ Package manager tidak dikenali. Pastikan python3, pip, ffmpeg terinstal."
fi

# 2. Periksa Antigravity CLI (agy)
echo "🔍 [2/5] Memeriksa Antigravity CLI (agy)..."
if ! command -v agy >/dev/null 2>&1 && [ ! -f "$HOME/.local/bin/agy" ]; then
    echo "⬇️ Mengunduh dan menginstal Antigravity CLI..."
    curl -fsSL https://antigravity.google/install.sh | bash || {
        echo "⚠️ Silakan pastikan Antigravity CLI terinstal di server ini."
    }
fi

# 3. Setup Python Virtual Environment
echo "🐍 [3/5] Menyiapkan Python Virtual Environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

"$DIR/venv/bin/pip" install --upgrade pip
"$DIR/venv/bin/pip" install -r requirements.txt

# 4. Siapkan File Konfigurasi .env
echo "⚙️ [4/5] Menyiapkan file konfigurasi..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️ File .env baru dibuat. Silakan edit file .env dan isi TELEGRAM_BOT_TOKEN serta ALLOWED_TELEGRAM_USER_ID."
fi

# Berikan izin eksekusi untuk semua script
chmod +x start.sh service.sh bot.py setup_vps.sh install_systemd.sh 2>/dev/null || true

echo "=========================================================="
echo "✅ Setup Dasar Selesai!"
echo "=========================================================="
echo ""
echo "Langkah selanjutnya:"
echo "1. Pastikan Anda sudah mengedit file .env (nano .env)"
echo "2. Jalankan bot 24/7 sebagai Systemd Service dengan:"
echo "   sudo ./install_systemd.sh"
echo ""
