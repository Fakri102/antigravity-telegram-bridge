#!/usr/bin/env python3
"""
Antigravity Telegram Bridge - Interactive Setup & Configuration Wizard
Membantu inisiasi dan konfigurasi kredensial bot secara interaktif dan aman.
"""

import os
import sys
import re
import stat
from typing import Dict, Optional

ENV_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
ENV_EXAMPLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.example")

def read_existing_env() -> Dict[str, str]:
    """Membaca konfigurasi .env yang sudah ada jika tersedia."""
    config = {}
    target_path = ENV_FILE_PATH if os.path.exists(ENV_FILE_PATH) else ENV_EXAMPLE_PATH
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        config[k.strip()] = v.strip()
        except Exception:
            pass
    return config

def print_banner():
    print("\n" + "=" * 62)
    print("🤖  ANTIGRAVITY TELEGRAM BRIDGE - SETUP WIZARD")
    print("=" * 62)
    print("Panduan inisiasi kredensial & konfigurasi awal bot.")
    print("=" * 62 + "\n")

def is_valid_bot_token(token: str) -> bool:
    """Validasi format dasar token bot Telegram (angka:alphanumeric)."""
    return bool(re.match(r"^\d{8,12}:[A-Za-z0-9_-]{30,45}$", token.strip()))

def run_interactive_setup(force: bool = False) -> bool:
    """
    Menjalankan wizard konfigurasi interaktif di terminal.
    Jika force=False dan .env sudah valid, setup dilewati.
    """
    existing = read_existing_env()
    current_token = existing.get("TELEGRAM_BOT_TOKEN", "").strip()

    # Jika tidak force dan sudah ada token, tanyakan konfirmasi
    if not force and current_token and os.path.exists(ENV_FILE_PATH):
        return True

    print_banner()

    # 1. TELEGRAM BOT TOKEN
    print("📌 [Langkah 1/4] Telegram Bot Token (Wajib)")
    print("   Dapatkan token dari @BotFather di Telegram (https://t.me/BotFather):")
    print("   1. Buka @BotFather -> Ketik /newbot")
    print("   2. Tentukan nama & username bot Anda")
    print("   3. Salin API Token yang diberikan\n")

    token = ""
    while not token:
        default_prompt = f" [{current_token}]" if current_token else ""
        prompt_str = f"👉 Masukkan Telegram Bot Token{default_prompt}: "
        user_input = input(prompt_str).strip()

        if not user_input and current_token:
            token = current_token
            break
        elif user_input:
            if not is_valid_bot_token(user_input):
                print("   ⚠️ Peringatan: Format token tampak tidak lazim (biasanya: 123456789:ABCdef...).")
                confirm = input("   Tetap gunakan token ini? (y/N): ").strip().lower()
                if confirm == "y":
                    token = user_input
                    break
            else:
                token = user_input
                break
        else:
            print("   ❌ Error: Telegram Bot Token wajib diisi!\n")

    # 2. ALLOWED TELEGRAM USER ID
    current_user_id = existing.get("ALLOWED_TELEGRAM_USER_ID", "").strip()
    print("\n" + "-" * 62)
    print("🔒 [Langkah 2/4] Allowed Telegram User ID (Keamanan Whitelist)")
    print("   Hanya akun Telegram dengan ID ini yang dapat mengakses server Anda.")
    print("   Cara mendapatkan ID:")
    print("   - Buka Telegram -> Cari @userinfobot (https://t.me/userinfobot)")
    print("   - Kirim pesan apa saja, bot akan membalas dengan nomor 'Id' Anda")
    print("   - Bisa lebih dari 1 ID dipisah koma (contoh: 123456789, 987654321)")
    print("   - Atau kosongkan jika ingin cek ID Anda nanti via /start di bot\n")

    default_user_prompt = f" [{current_user_id}]" if current_user_id else " [Kosongkan jika belum tahu]"
    user_id_input = input(f"👉 Masukkan User ID Telegram{default_user_prompt}: ").strip()
    if not user_id_input and current_user_id:
        user_id_val = current_user_id
    else:
        user_id_val = user_id_input

    # 3. WORKSPACE DIRECTORY
    default_ws = existing.get("ANTIGRAVITY_WORKSPACE", "").strip() or os.path.expanduser("~")
    print("\n" + "-" * 62)
    print("📂 [Langkah 3/4] Default Workspace Directory")
    print(f"   Direktori kerja default untuk mengeksekusi perintah Antigravity.")
    print(f"   Default: {default_ws}\n")

    ws_input = input(f"👉 Masukkan path workspace [{default_ws}]: ").strip()
    workspace_val = ws_input if ws_input else default_ws
    workspace_val = os.path.expanduser(workspace_val)

    # 4. GEMINI API KEY (OPSIONAL)
    current_gemini = existing.get("GEMINI_API_KEY", "").strip()
    print("\n" + "-" * 62)
    print("🎙️ [Langkah 4/4] Gemini API Key (Opsional - untuk Voice Transcription)")
    print("   Digunakan untuk transkripsi voice note bahasa Indonesia tingkat lanjut.")
    print("   Dapatkan gratis di: https://aistudio.google.com/app/apikey (kosongkan jika tidak butuh)\n")

    default_gemini_prompt = f" [{current_gemini[:6]}...]" if current_gemini else " [Opsional / Kosong]"
    gemini_input = input(f"👉 Masukkan Gemini API Key{default_gemini_prompt}: ").strip()
    if not gemini_input and current_gemini:
        gemini_val = current_gemini
    else:
        gemini_val = gemini_input

    # Simpan ke .env
    env_content = f"""# ==========================================
# ANTIGRAVITY TELEGRAM BRIDGE CONFIGURATION
# Dibuat otomatis oleh Setup Wizard
# ==========================================

# Token Bot Telegram dari @BotFather
TELEGRAM_BOT_TOKEN={token}

# Whitelist Telegram User ID (hanya ID ini yang bisa akses server)
ALLOWED_TELEGRAM_USER_ID={user_id_val}

# Direktori default saat bot dijalankan
ANTIGRAVITY_WORKSPACE={workspace_val}

# Path ke binary agy CLI (kosongkan untuk deteksi otomatis)
AGY_BINARY_PATH={existing.get('AGY_BINARY_PATH', '')}

# Opsional: Gemini API Key untuk transkripsi audio
GEMINI_API_KEY={gemini_val}

# Timeout eksekusi dalam detik (default: 300)
ANTIGRAVITY_TIMEOUT={existing.get('ANTIGRAVITY_TIMEOUT', '300')}

# Level Log: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL={existing.get('LOG_LEVEL', 'INFO')}
"""

    try:
        with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(env_content)

        # Set permission chmod 600 (Hanya user ini yang bisa baca/tulis)
        try:
            os.chmod(ENV_FILE_PATH, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

        print("\n" + "=" * 62)
        print("✅ KONFIGURASI BERHASIL DISIMPAN!")
        print("=" * 62)
        print(f"📄 File konfigurasi: {ENV_FILE_PATH}")
        print("🔒 Hak akses file telah dikunci (chmod 600 - Owner read/write only)")
        if not user_id_val:
            print("\n💡 Tips: Anda belum memasukkan ALLOWED_TELEGRAM_USER_ID.")
            print("   Jalankan bot, lalu kirim perintah /start di Telegram untuk melihat User ID Anda.")
            print("   Setelah itu jalankan `./init.sh` lagi untuk menyimpannya.")
        print("=" * 62 + "\n")
        return True

    except Exception as e:
        print(f"\n❌ Gagal menyimpan konfigurasi: {e}")
        return False

def check_and_ensure_credentials() -> bool:
    """
    Memeriksa apakah kredensial bot sudah lengkap.
    Jika belum dan berada di terminal interaktif (TTY), jalankan wizard otomatis.
    """
    existing = read_existing_env()
    token = existing.get("TELEGRAM_BOT_TOKEN", "").strip()

    if token:
        return True

    # Jika token belum ada dan running di terminal interaktif
    if sys.stdin.isatty():
        print("⚠️ Konfigurasi bot belum lengkap (TELEGRAM_BOT_TOKEN kosong).")
        print("Memulai setup wizard interaktif...\n")
        return run_interactive_setup(force=True)
    else:
        print("❌ Error: TELEGRAM_BOT_TOKEN belum diisi di file .env!")
        print("Jalankan './init.sh' atau edit file .env secara manual.")
        return False

if __name__ == "__main__":
    force_mode = "--force" in sys.argv or "-f" in sys.argv or "--setup" in sys.argv
    success = run_interactive_setup(force=force_mode)
    sys.exit(0 if success else 1)
