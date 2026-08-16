#!/bin/bash
# Manager Service Background untuk Antigravity Telegram Bridge

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

PID_FILE="$DIR/bot.pid"
LOG_FILE="$DIR/bot.log"

case "$1" in
    start)
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "⚠️ Bot sudah berjalan dengan PID $(cat "$PID_FILE")"
            exit 1
        fi

        TOKEN=$(grep "TELEGRAM_BOT_TOKEN=" .env | cut -d '=' -f2 | tr -d ' "')
        if [ -z "$TOKEN" ]; then
            echo "❌ ERROR: TELEGRAM_BOT_TOKEN belum diisi di $DIR/.env"
            exit 1
        fi

        echo "🚀 Memulai Antigravity Telegram Bridge di background..."
        nohup "$DIR/venv/bin/python" "$DIR/bot.py" > "$LOG_FILE" 2>&1 &
        echo $! > "$PID_FILE"
        echo "✅ Bot berjalan di background (PID: $(cat "$PID_FILE"))"
        echo "📄 Log output: $LOG_FILE"
        ;;

    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "🛑 Menghentikan bot (PID: $PID)..."
                kill "$PID"
                rm -f "$PID_FILE"
                echo "✅ Bot berhasil dihentikan."
            else
                echo "⚠️ Proses bot tidak ditemukan. Membersihkan PID file."
                rm -f "$PID_FILE"
            fi
        else
            echo "ℹ️ Bot tidak sedang berjalan."
        fi
        ;;

    restart)
        $0 stop
        sleep 2
        $0 start
        ;;

    status)
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "🟢 Bot AKTIF (PID: $(cat "$PID_FILE"))"
        else
            echo "🔴 Bot MATI / TIDAK AKTIF"
        fi
        ;;

    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -n 50 -f "$LOG_FILE"
        else
            echo "Log file belum ada."
        fi
        ;;

    *)
        echo "Penggunaan: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
