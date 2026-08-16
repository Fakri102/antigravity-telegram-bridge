#!/bin/bash
# ==============================================================================
# Antigravity Telegram Bridge - Systemd Service Installer (Linux VPS 24/7)
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVICE_NAME="antigravity-telegram"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
CURRENT_USER=$(whoami)

echo "🔧 Mengonfigurasi Systemd Service untuk $SERVICE_NAME..."

# Cek .env
if [ ! -f "$DIR/.env" ]; then
    echo "❌ ERROR: File $DIR/.env tidak ditemukan!"
    exit 1
fi

TOKEN=$(grep "TELEGRAM_BOT_TOKEN=" "$DIR/.env" | cut -d '=' -f2 | tr -d ' "')
if [ -z "$TOKEN" ]; then
    echo "❌ ERROR: TELEGRAM_BOT_TOKEN masih kosong di $DIR/.env"
    exit 1
fi

# Tulis unit file systemd
echo "📝 Menulis unit file ke $SERVICE_FILE..."
sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=Antigravity Telegram Bridge Daemon
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python $DIR/bot.py
Restart=always
RestartSec=5s
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF"

echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "🚀 Mengaktifkan & Menjalankan service $SERVICE_NAME..."
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "=========================================================="
echo "✅ Antigravity Telegram Bridge Berhasil Terpasang di Systemd!"
echo "=========================================================="
echo "Status Service: sudo systemctl status $SERVICE_NAME"
echo "Live Logs:      sudo journalctl -u $SERVICE_NAME -f"
echo "Restart:        sudo systemctl restart $SERVICE_NAME"
echo "Stop:           sudo systemctl stop $SERVICE_NAME"
echo "=========================================================="
