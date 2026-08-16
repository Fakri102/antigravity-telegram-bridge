#!/usr/bin/env python3
"""
Antigravity Telegram Bridge
Menghubungkan Telegram Chat & Voice/Audio ke Google Antigravity di Komputer / Desktop Lokal.
"""

import os
import sys
import json
import tempfile
import asyncio
import logging
from typing import Dict, Optional, Set
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Audio libraries
import speech_recognition as sr
from pydub import AudioSegment

# Load environment configuration
load_dotenv()

# Setup Logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AntigravityBridge")

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USER_IDS_RAW = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
DEFAULT_WORKSPACE = os.getenv("ANTIGRAVITY_WORKSPACE", os.path.expanduser("~"))
AGY_PATH = os.getenv("AGY_BINARY_PATH", os.path.expanduser("~/.local/bin/agy"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Parse allowed IDs
ALLOWED_USER_IDS: Set[int] = set()
if ALLOWED_USER_IDS_RAW:
    for uid in ALLOWED_USER_IDS_RAW.split(","):
        uid_clean = uid.strip()
        if uid_clean.isdigit():
            ALLOWED_USER_IDS.add(int(uid_clean))

# User Session State
class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.conversation_id: Optional[str] = None
        self.workspace_dir: str = DEFAULT_WORKSPACE
        self.model: Optional[str] = None
        self.effort: Optional[str] = None  # low, medium, high
        self.current_task: Optional[asyncio.Task] = None

user_sessions: Dict[int, UserSession] = {}

def get_session(user_id: int) -> UserSession:
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    return user_sessions[user_id]

def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return False
    return user_id in ALLOWED_USER_IDS

async def send_chunked_message(update: Update, text: str):
    """Membagi pesan jika melebihi 4000 karakter Telegram."""
    if not text:
        text = "*(Tidak ada output)*"

    max_chunk = 3900
    total_len = len(text)
    
    if total_len <= max_chunk:
        try:
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(text)
        return

    lines = text.split("\n")
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_chunk:
            if current_chunk:
                try:
                    await update.message.reply_text(current_chunk, parse_mode=ParseMode.MARKDOWN)
                except Exception:
                    await update.message.reply_text(current_chunk)
                current_chunk = ""
        current_chunk += line + "\n"

    if current_chunk.strip():
        try:
            await update.message.reply_text(current_chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(current_chunk)

async def keep_typing(bot, chat_id: int, stop_event: asyncio.Event):
    """Mengirim status 'typing...' setiap 4 detik agar user tahu agent sedang bekerja."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass

# Audio Transcription Function
async def transcribe_audio_file(file_path: str) -> str:
    """Mengonversi file audio/voice note ke teks menggunakan Gemini atau SpeechRecognition."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    # Metode 1: Jika GEMINI_API_KEY ada, gunakan Gemini Multimodal Audio (Sangat Akurat)
    if gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            with open(file_path, "rb") as f:
                audio_bytes = f.read()

            ext = os.path.splitext(file_path)[1].lower()
            mime_type = "audio/ogg" if ext in [".oga", ".ogg"] else "audio/wav"

            prompt_transcribe = (
                "Transcribe this voice message accurately into text. "
                "The user is talking in Indonesian or English about coding, tasks, or instructions. "
                "Output ONLY the transcribed text without quotes, formatting, or extra conversation."
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    prompt_transcribe
                ]
            )
            if response.text and response.text.strip():
                return response.text.strip()
        except Exception as ge:
            logger.warning(f"Gemini audio transcription error: {ge}. Menggunakan engine fallback...")

    # Metode 2: Fallback ke SpeechRecognition + Pydub / FFmpeg (Gratis & Cepat)
    wav_path = file_path + ".wav"
    try:
        # Konversi ke WAV mono 16kHz
        sound = AudioSegment.from_file(file_path)
        sound = sound.set_channels(1).set_frame_rate(16000)
        sound.export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio_data = recognizer.record(source)

        # Coba Bahasa Indonesia terlebih dahulu
        try:
            text = recognizer.recognize_google(audio_data, language="id-ID")
            return text
        except sr.UnknownValueError:
            # Fallback ke Bahasa Inggris jika gagal
            text = recognizer.recognize_google(audio_data, language="en-US")
            return text
    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass

# Command Handlers
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    if not is_authorized(user_id):
        logger.warning(f"Unauthorized access attempt by user {user_id} (@{username})")
        msg = (
            f"⛔ *Akses Ditolak*\n\n"
            f"User ID Telegram Anda: `{user_id}`\n\n"
            f"Tambahkan User ID ini ke file `.env` di komputer Anda:\n"
            f"`ALLOWED_TELEGRAM_USER_ID={user_id}`\n"
            f"Lalu restart bot bridge ini."
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    session = get_session(user_id)
    welcome_text = (
        f"🚀 *Selamat datang di Antigravity Desktop Bridge!*\n\n"
        f"Halo *{username}*, bot ini terhubung langsung ke Google Antigravity di komputer/desktop Anda.\n\n"
        f"📂 *Workspace Saat Ini:* `{session.workspace_dir}`\n"
        f"🧠 *Model:* `{session.model or 'Default (Antigravity Config)'}`\n\n"
        f"*Dukungan Input:*\n"
        f"• 💬 **Teks**: Kirim pesan instruksi biasa.\n"
        f"• 🎙️ **Voice Note / Audio**: Kirim pesan suara, bot akan otomatis mentranskripsinya & memproses instruksi coding Anda!\n\n"
        f"*Daftar Perintah:*\n"
        f"• `/new` atau `/reset` - Mulai percakapan baru (reset konteks).\n"
        f"• `/workspace <path>` - Lihat atau ubah folder kerja proyek.\n"
        f"• `/status` - Cek status agent, token usage, dan sesi aktif.\n"
        f"• `/model <nama>` - Ganti model AI (contoh: `/model gemini-2.5-pro`).\n"
        f"• `/effort <level>` - Atur penalaran (`low`, `medium`, `high`, `default`).\n"
        f"• `/cancel` - Batalkan tugas yang sedang berjalan."
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_handler(update, context)

async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    session.conversation_id = None
    await update.message.reply_text("🔄 *Sesi percakapan telah direset.* Percakapan berikutnya akan dimulai dari sesi baru.", parse_mode=ParseMode.MARKDOWN)

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    conv_display = f"`{session.conversation_id}`" if session.conversation_id else "_Belum ada percakapan aktif_"
    model_display = f"`{session.model}`" if session.model else "_Default Desktop Config_"
    effort_display = f"`{session.effort}`" if session.effort else "_Default_"

    status_text = (
        f"📊 *Status Antigravity Bridge*\n\n"
        f"• 📂 *Workspace:* `{session.workspace_dir}`\n"
        f"• 💬 *Conversation ID:* {conv_display}\n"
        f"• 🧠 *Model:* {model_display}\n"
        f"• ⚡ *Effort:* {effort_display}\n"
        f"• 🎙️ *Audio Support:* 🟢 Aktif (Voice Note & Audio Files)\n"
        f"• ⚙️ *Binary Path:* `{AGY_PATH}`\n"
        f"• 🟢 *Status:* Siap menerima instruksi."
    )
    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

async def workspace_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)

    if not context.args:
        await update.message.reply_text(
            f"📂 *Workspace Aktif:* `{session.workspace_dir}`\n\n"
            f"Untuk mengubah workspace:\n"
            f"`/workspace /path/ke/proyek/anda`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    target_dir = os.path.expanduser(" ".join(context.args).strip())
    if not os.path.exists(target_dir):
        await update.message.reply_text(f"❌ Direktori tidak ditemukan:\n`{target_dir}`", parse_mode=ParseMode.MARKDOWN)
        return

    if not os.path.isdir(target_dir):
        await update.message.reply_text(f"❌ Path bukan merupakan folder:\n`{target_dir}`", parse_mode=ParseMode.MARKDOWN)
        return

    session.workspace_dir = os.path.abspath(target_dir)
    session.conversation_id = None
    await update.message.reply_text(
        f"✅ *Workspace berhasil diubah!*\n"
        f"📂 Direktori baru: `{session.workspace_dir}`\n"
        f"🔄 Sesi percakapan direset otomatis untuk workspace ini.",
        parse_mode=ParseMode.MARKDOWN
    )

async def model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)

    if not context.args:
        curr = session.model or "Default"
        await update.message.reply_text(
            f"🧠 *Model Aktif:* `{curr}`\n\n"
            f"Untuk mengubah model:\n"
            f"`/model gemini-2.5-pro` atau `/model gemini-2.5-flash`\n"
            f"Gunakan `/model default` untuk kembali ke default.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    model_arg = context.args[0].strip()
    if model_arg.lower() in ["default", "reset"]:
        session.model = None
        await update.message.reply_text("✅ Model dikembalikan ke konfigurasi default Antigravity Desktop.")
    else:
        session.model = model_arg
        await update.message.reply_text(f"✅ Model disetel ke: `{session.model}`", parse_mode=ParseMode.MARKDOWN)

async def effort_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)

    if not context.args:
        curr = session.effort or "Default"
        await update.message.reply_text(
            f"⚡ *Reasoning Effort Aktif:* `{curr}`\n\n"
            f"Pilihan:\n"
            f"• `/effort low`\n"
            f"• `/effort medium`\n"
            f"• `/effort high`\n"
            f"• `/effort default`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    effort_val = context.args[0].lower().strip()
    if effort_val in ["low", "medium", "high"]:
        session.effort = effort_val
        await update.message.reply_text(f"✅ Reasoning effort diatur ke: `{effort_val}`", parse_mode=ParseMode.MARKDOWN)
    elif effort_val == "default":
        session.effort = None
        await update.message.reply_text("✅ Reasoning effort dikembalikan ke default.")
    else:
        await update.message.reply_text("❌ Pilihan tidak valid. Gunakan `low`, `medium`, `high`, atau `default`.")

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    if session.current_task and not session.current_task.done():
        session.current_task.cancel()
        await update.message.reply_text("🛑 Permintaan yang sedang berjalan berhasil dibatalkan.")
    else:
        await update.message.reply_text("ℹ️ Tidak ada tugas yang sedang berjalan.")

async def execute_antigravity(session: UserSession, prompt: str) -> dict:
    """Menjalankan agy CLI non-interaktif dengan format output JSON."""
    cmd = [
        AGY_PATH,
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]

    if session.conversation_id:
        cmd.extend(["--conversation", session.conversation_id])

    if session.model:
        cmd.extend(["--model", session.model])

    if session.effort:
        cmd.extend(["--effort", session.effort])

    cmd.extend(["--print", prompt])

    cwd = session.workspace_dir if os.path.exists(session.workspace_dir) else os.path.expanduser("~")

    logger.info(f"Menjalankan agy di '{cwd}' | Prompt: {prompt[:80]}...")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd
    )

    stdout, stderr = await process.communicate()

    stdout_str = stdout.decode("utf-8", errors="replace").strip()
    stderr_str = stderr.decode("utf-8", errors="replace").strip()

    if process.returncode != 0 and not stdout_str:
        raise RuntimeError(f"agy error (code {process.returncode}): {stderr_str or 'Unknown error'}")

    try:
        data = json.loads(stdout_str)
        return data
    except json.JSONDecodeError:
        return {
            "response": stdout_str or stderr_str or "(Selesai tanpa output)",
            "status": "SUCCESS" if process.returncode == 0 else "ERROR",
            "conversation_id": session.conversation_id
        }

async def process_prompt_task(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    user_id = update.effective_user.id
    session = get_session(user_id)
    chat_id = update.effective_chat.id

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(context.bot, chat_id, stop_typing))

    try:
        data = await execute_antigravity(session, prompt)

        if data.get("conversation_id"):
            session.conversation_id = data["conversation_id"]

        response_text = data.get("response", "").strip()

        duration = data.get("duration_seconds")
        usage = data.get("usage")
        footer_parts = []
        if duration:
            footer_parts.append(f"⏱️ {duration:.1f}s")
        if usage and isinstance(usage, dict):
            tokens = usage.get("total_tokens")
            if tokens:
                footer_parts.append(f"🔢 {tokens:,} tok")

        if footer_parts:
            response_text += f"\n\n_({' • '.join(footer_parts)})_"

        await send_chunked_message(update, response_text)

    except asyncio.CancelledError:
        logger.info("Task cancelled by user.")
    except Exception as e:
        logger.error(f"Gagal memproses prompt: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ *Terjadi Kesalahan:*\n`{str(e)}`", parse_mode=ParseMode.MARKDOWN)
    finally:
        stop_typing.set()
        await typing_task
        session.current_task = None

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"⛔ Akses ditolak. User ID Anda: `{user_id}`", parse_mode=ParseMode.MARKDOWN)
        return

    prompt = update.message.text
    if not prompt or not prompt.strip():
        return

    session = get_session(user_id)

    if session.current_task and not session.current_task.done():
        await update.message.reply_text("⏳ Sedang memproses tugas sebelumnya. Gunakan `/cancel` jika ingin membatalkannya.")
        return

    session.current_task = asyncio.create_task(process_prompt_task(update, context, prompt))

async def voice_audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani pesan suara (Voice Note) dan file audio."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"⛔ Akses ditolak. User ID Anda: `{user_id}`", parse_mode=ParseMode.MARKDOWN)
        return

    session = get_session(user_id)
    if session.current_task and not session.current_task.done():
        await update.message.reply_text("⏳ Sedang memproses tugas sebelumnya. Gunakan `/cancel` jika ingin membatalkannya.")
        return

    # Kirim status 'recording voice' / 'typing'
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # Ambil file audio / voice
    audio_obj = update.message.voice or update.message.audio
    if not audio_obj:
        return

    # Tentukan ekstensi file
    file_ext = ".oga" if update.message.voice else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        # Download audio dari Telegram
        telegram_file = await context.bot.get_file(audio_obj.file_id)
        await telegram_file.download_to_drive(custom_path=tmp_path)

        logger.info(f"Mengonversi audio dari user {user_id} ({os.path.getsize(tmp_path)} bytes)...")
        transcribed_text = await transcribe_audio_file(tmp_path)

        if not transcribed_text or not transcribed_text.strip():
            await update.message.reply_text("❓ Tidak dapat mendeteksi suara yang jelas dari audio Anda. Silakan coba lagi atau gunakan teks.")
            return

        # Tampilkan hasil transkripsi ke user
        await update.message.reply_text(
            f"🎙️ *Pesan Suara Terdeteksi:*\n_{transcribed_text}_",
            parse_mode=ParseMode.MARKDOWN
        )

        # Proses teks hasil transkripsi ke Antigravity
        session.current_task = asyncio.create_task(process_prompt_task(update, context, transcribed_text))

    except Exception as e:
        logger.error(f"Error memproses audio: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Gagal memproses audio:\n`{str(e)}`", parse_mode=ParseMode.MARKDOWN)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def main():
    if not os.path.exists(AGY_PATH):
        logger.error(f"Binary 'agy' tidak ditemukan di path: {AGY_PATH}")
        print(f"❌ Error: Binary 'agy' tidak ditemukan di: {AGY_PATH}")
        print("Pastikan Antigravity CLI telah terinstal.")
        sys.exit(1)

    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN belum diisi di file .env")
        sys.exit(1)

    if not ALLOWED_USER_IDS:
        print("⚠️ PERINGATAN: ALLOWED_TELEGRAM_USER_ID belum diisi di .env.")
        print("Bot akan menolak semua pesan hingga Anda menambahkan ID Anda.")

    logger.info("Memulai Antigravity Telegram Bridge dengan Audio Support...")
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Daftarkan Handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("reset", reset_handler))
    application.add_handler(CommandHandler("new", reset_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("workspace", workspace_handler))
    application.add_handler(CommandHandler("model", model_handler))
    application.add_handler(CommandHandler("effort", effort_handler))
    application.add_handler(CommandHandler("cancel", cancel_handler))
    
    # Handler Pesan Teks
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Handler Pesan Suara & File Audio
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_audio_handler))

    print(f"🤖 Antigravity Telegram Bridge aktif! (Voice & Text Ready)")
    print(f"📂 Default Workspace: {DEFAULT_WORKSPACE}")
    print(f"🔑 Allowed User IDs: {list(ALLOWED_USER_IDS) if ALLOWED_USER_IDS else 'Belum ada'}")
    print("Tekan Ctrl+C untuk menghentikan.")

    application.run_polling()

if __name__ == "__main__":
    main()
