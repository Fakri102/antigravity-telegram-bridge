#!/bin/bash
# ==============================================================================
# Script untuk menjalankan Antigravity Telegram Bridge
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Tentukan binary Python
if [ -d "$DIR/venv" ] && [ -f "$DIR/venv/bin/python" ]; then
    PYTHON_EXEC="$DIR/venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

# Cek token di .env atau jalankan interactive setup wizard jika belum disetel
TOKEN=""
if [ -f .env ]; then
    TOKEN=$(grep -E "^TELEGRAM_BOT_TOKEN=" .env | cut -d '=' -f2 | tr -d ' "')
fi

if [ -z "$TOKEN" ]; then
    echo "⚠️ TELEGRAM_BOT_TOKEN belum disetel."
    echo "Memulai inisiasi konfigurasi..."
    "$PYTHON_EXEC" "$DIR/init_config.py" --setup
    if [ $? -ne 0 ]; then
        echo "❌ Inisiasi dibatalkan atau gagal. Keluar."
        exit 1
    fi
fi

echo "🚀 Menjalankan Antigravity Telegram Bridge..."
"$PYTHON_EXEC" "$DIR/bot.py"
