#!/bin/bash
# Script untuk menjalankan Antigravity Telegram Bridge

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Cek file .env
if [ ! -f .env ]; then
    echo "⚠️ File .env belum ditemukan. Menyalin dari .env.example..."
    cp .env.example .env
fi

# Cek token di .env
TOKEN=$(grep "TELEGRAM_BOT_TOKEN=" .env | cut -d '=' -f2 | tr -d ' "')
if [ -z "$TOKEN" ]; then
    echo "❌ ERROR: TELEGRAM_BOT_TOKEN masih kosong di file .env!"
    echo "Silakan buka file $DIR/.env dan masukkan bot token Anda dari @BotFather."
    exit 1
fi

echo "🚀 Menjalankan Antigravity Telegram Bridge..."
"$DIR/venv/bin/python" "$DIR/bot.py"
