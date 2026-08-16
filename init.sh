#!/bin/bash
# ==============================================================================
# Antigravity Telegram Bridge - Initializer & Credential Setup Wizard
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Pastikan Python tersedia
if [ -d "$DIR/venv" ] && [ -f "$DIR/venv/bin/python" ]; then
    PYTHON_CMD="$DIR/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python 3 tidak ditemukan. Silakan instal Python 3 terlebih dahulu."
    exit 1
fi

# Jalankan wizard inisiasi kredensial
"$PYTHON_CMD" "$DIR/init_config.py" --setup "$@"
