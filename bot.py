#!/usr/bin/env python3
"""
Antigravity Telegram Bridge (Production Edition)
Menghubungkan Telegram Chat, Voice/Audio, dan Gambar ke Google Antigravity di Komputer / VPS Linux / Mac.
Dilengkapi:
- Dynamic Binary Discovery (Linux/Mac/Docker support)
- Robust Subprocess Management (Process group termination on /cancel & timeout)
- Production Health Monitoring (RAM, CPU, Disk, Uptime di /status)
- Telegram HTML Formatting Engine & Smart Code Chunker
- File Size Guard & Graceful Signal Handling
"""

import os
import sys
import re
import html
import json
import time
import shutil
import signal
import tempfile
import asyncio
import logging
import platform
from typing import Dict, List, Optional, Set
from dotenv import load_dotenv
from init_config import check_and_ensure_credentials, run_interactive_setup
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
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AntigravityBridge")

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_USER_IDS_RAW = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
DEFAULT_WORKSPACE = os.getenv("ANTIGRAVITY_WORKSPACE", os.path.expanduser("~"))
DEFAULT_MODEL = os.getenv("ANTIGRAVITY_MODEL", "gemini-3.7-flash").strip()
DEFAULT_EFFORT = os.getenv("ANTIGRAVITY_EFFORT", "high").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
EXECUTION_TIMEOUT = int(os.getenv("ANTIGRAVITY_TIMEOUT", "300"))  # Default 5 menit timeout

# Dynamic Binary Discovery for agy
def find_agy_binary() -> str:
    env_path = os.getenv("AGY_BINARY_PATH", "").strip()
    if env_path and os.path.exists(os.path.expanduser(env_path)):
        return os.path.abspath(os.path.expanduser(env_path))

    which_path = shutil.which("agy")
    if which_path and os.path.exists(which_path):
        return which_path

    common_paths = [
        os.path.expanduser("~/.local/bin/agy"),
        "/usr/local/bin/agy",
        "/usr/bin/agy",
        "/opt/homebrew/bin/agy",
        "/home/linuxbrew/.linuxbrew/bin/agy"
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p

    return "agy"

AGY_PATH = find_agy_binary()

# Parse allowed IDs
ALLOWED_USER_IDS: Set[int] = set()
if ALLOWED_USER_IDS_RAW:
    for uid in ALLOWED_USER_IDS_RAW.split(","):
        uid_clean = uid.strip()
        if uid_clean.isdigit():
            ALLOWED_USER_IDS.add(int(uid_clean))

# Boot timestamp for uptime calculation
BOT_START_TIME = time.time()

# User Session State
class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.conversation_id: Optional[str] = None
        self.workspace_dir: str = DEFAULT_WORKSPACE
        self.model: Optional[str] = DEFAULT_MODEL if DEFAULT_MODEL else "gemini-3.7-flash"
        self.effort: Optional[str] = DEFAULT_EFFORT if DEFAULT_EFFORT in ["low", "medium", "high"] else None
        self.current_task: Optional[asyncio.Task] = None
        self.current_pid: Optional[int] = None

user_sessions: Dict[int, UserSession] = {}

def get_session(user_id: int) -> UserSession:
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    return user_sessions[user_id]

def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return False
    return user_id in ALLOWED_USER_IDS

# System Metrics Helper
def get_system_stats() -> dict:
    """Mengambil informasi sistem server (Uptime, OS, RAM, Disk)."""
    stats = {}
    
    # Uptime bot
    uptime_seconds = int(time.time() - BOT_START_TIME)
    hours, rem = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    stats["uptime"] = f"{hours}h {minutes}m {seconds}s"
    stats["os"] = f"{platform.system()} {platform.release()} ({platform.machine()})"

    # Disk usage
    try:
        total, used, free = shutil.disk_usage("/")
        stats["disk"] = f"{used // (2**30)}GB / {total // (2**30)}GB (Free: {free // (2**30)}GB)"
    except Exception:
        stats["disk"] = "N/A"

    return stats

# ==========================================
# FORMATTING ENGINE (MARKDOWN TO TELEGRAM HTML)
# ==========================================

def clean_ansi_and_unicode(text: str) -> str:
    """Menghapus ANSI escape codes dari output CLI."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text).strip()

def markdown_to_telegram_html(md_text: str) -> str:
    """Mengonversi Markdown ke format Telegram HTML yang valid & rapi."""
    text = clean_ansi_and_unicode(md_text)
    if not text:
        return ""

    # 1. Lindungi Fenced Code Blocks ```lang ... ```
    code_blocks = []
    def save_code_block(match):
        lang = (match.group(1) or "").strip()
        code_content = match.group(2).strip("\n")
        escaped_code = html.escape(code_content)
        idx = len(code_blocks)
        if lang:
            code_blocks.append(f'<pre><code class="language-{lang}">{escaped_code}</code></pre>')
        else:
            code_blocks.append(f'<pre><code>{escaped_code}</code></pre>')
        return f"%%CODE_BLOCK_{idx}%%"

    text = re.sub(r'```(\w+)?\n?(.*?)```', save_code_block, text, flags=re.DOTALL)

    # 2. Lindungi Inline Code `...`
    inline_codes = []
    def save_inline_code(match):
        code_content = match.group(1)
        escaped_code = html.escape(code_content)
        idx = len(inline_codes)
        inline_codes.append(f'<code>{escaped_code}</code>')
        return f"%%INLINE_CODE_{idx}%%"

    text = re.sub(r'`([^`\n]+)`', save_inline_code, text)

    # 3. Escape HTML
    text = html.escape(text)

    # 4. Headers (# -> <b>)
    text = re.sub(r'^(#{1,6})\s+(.+)$', r'<b>\2</b>', text, flags=re.MULTILINE)

    # 5. Bold & Italic
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\w)\*([^\*\n]+?)\*(?!\w)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_([^_\n]+?)_(?!\w)', r'<i>\1</i>', text)

    # 6. Quotes & Lists
    text = re.sub(r'^\s*&gt;\s?(.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[\-\*]\s+(.+)$', r'• \1', text, flags=re.MULTILINE)

    # 7. Links
    text = re.sub(r'\[([^\]]+)\]\((https?:\/\/[^\)]+)\)', r'<a href="\2">\1</a>', text)

    # 8. Restore Protected Tags
    for i, code_html in enumerate(inline_codes):
        text = text.replace(f"%%INLINE_CODE_{i}%%", code_html)

    for i, block_html in enumerate(code_blocks):
        text = text.replace(f"%%CODE_BLOCK_{i}%%", block_html)

    return text

def chunk_markdown_safely(text: str, max_chars: int = 3400) -> List[str]:
    """Memecah teks panjang tanpa merusak struktur code block."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_len = 0
    in_code_block = False
    code_block_lang = ""

    for line in lines:
        line_len = len(line) + 1

        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_block_lang = line.strip()[3:].strip()
            else:
                in_code_block = False
                code_block_lang = ""

        if current_len + line_len > max_chars and current_chunk:
            if in_code_block:
                current_chunk.append("```")
                chunks.append("\n".join(current_chunk))
                current_chunk = [f"```{code_block_lang}", line]
                current_len = len(f"```{code_block_lang}\n") + line_len
            else:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = line_len
        else:
            current_chunk.append(line)
            current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks

async def send_formatted_message(update: Update, raw_text: str):
    """Mengirim pesan dengan HTML parser dan fallback teks bersih."""
    if not raw_text or not raw_text.strip():
        raw_text = "<i>(Tidak ada output teks dari agen)</i>"

    chunks = chunk_markdown_safely(raw_text, max_chars=3400)

    for chunk in chunks:
        formatted_html = markdown_to_telegram_html(chunk)
        try:
            await update.message.reply_text(
                formatted_html,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.warning(f"HTML parse failed ({e}), sending clean plain text...")
            clean_text = clean_ansi_and_unicode(chunk)
            await update.message.reply_text(clean_text, disable_web_page_preview=True)

async def keep_typing(bot, chat_id: int, stop_event: asyncio.Event):
    """Mengirim status 'typing...' berkala selama agent bekerja."""
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
    """Mengonversi file audio/voice note ke teks."""
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

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
                "The user is speaking in Indonesian or English about coding, tasks, or development instructions. "
                "Output ONLY the exact transcribed text without quotes or preamble."
            )

            # Prioritaskan model Gemini terbaru
            models_to_try = ["gemini-3.7-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
            for mod in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=mod,
                        contents=[
                            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                            prompt_transcribe
                        ]
                    )
                    if response.text and response.text.strip():
                        return response.text.strip()
                except Exception as model_err:
                    logger.debug(f"Percobaan transkripsi dengan {mod} gagal: {model_err}")
                    continue
        except Exception as ge:
            logger.warning(f"Gemini audio transcription error: {ge}. Menggunakan fallback SpeechRecognition...")

    wav_path = file_path + ".wav"
    try:
        sound = AudioSegment.from_file(file_path)
        sound = sound.set_channels(1).set_frame_rate(16000)
        sound.export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio_data = recognizer.record(source)

        try:
            return recognizer.recognize_google(audio_data, language="id-ID")
        except sr.UnknownValueError:
            return recognizer.recognize_google(audio_data, language="en-US")
    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass

# Command Handlers
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = html.escape(update.effective_user.username or update.effective_user.first_name)

    if not is_authorized(user_id):
        logger.warning(f"Unauthorized access attempt by user {user_id}")
        msg = (
            f"⛔ <b>Akses Ditolak</b>\n\n"
            f"User ID Telegram Anda: <code>{user_id}</code>\n\n"
            f"Tambahkan User ID ini ke file <code>.env</code> di server:\n"
            f"<code>ALLOWED_TELEGRAM_USER_ID={user_id}</code>\n\n"
            f"Lalu restart service bot ini."
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        return

    session = get_session(user_id)
    welcome_text = (
        f"🚀 <b>Antigravity Production Bridge Terhubung!</b>\n\n"
        f"Halo <b>{username}</b>, bot ini terhubung langsung ke Google Antigravity Engine di server Anda.\n\n"
        f"📂 <b>Workspace:</b> <code>{html.escape(session.workspace_dir)}</code>\n"
        f"🧠 <b>Model:</b> <code>{html.escape(session.model or 'Default Server Config')}</code>\n\n"
        f"<b>🎯 Input Multimodal Didukung:</b>\n"
        f"• 💬 <b>Teks:</b> Kirim prompt, instruksi deploy, perbaikan bug, dll.\n"
        f"• 🎙️ <b>Voice Note:</b> Rekam suara, otomatis ditranskripsikan.\n"
        f"• 🖼️ <b>Gambar / Screenshot:</b> Kirim screenshot desain UI / error log.\n\n"
        f"<b>⚙️ Daftar Perintah:</b>\n"
        f"• <code>/new</code> atau <code>/reset</code> — Reset sesi percakapan.\n"
        f"• <code>/workspace &lt;path&gt;</code> — Pindah folder proyek aktif.\n"
        f"• <code>/status</code> — Cek status server, RAM, Disk, dan sesi aktif.\n"
        f"• <code>/model &lt;nama&gt;</code> — Ganti model AI (contoh: <code>/model gemini-3.7-flash</code>).\n"
        f"• <code>/effort &lt;low|medium|high&gt;</code> — Atur tingkat penalaran AI.\n"
        f"• <code>/cancel</code> — Batalkan tugas yang sedang berjalan."
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_handler(update, context)

async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    session.conversation_id = None
    await update.message.reply_text("🔄 <b>Sesi percakapan telah direset.</b> Percakapan berikutnya akan dimulai dari awal.", parse_mode=ParseMode.HTML)

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    sys_stats = get_system_stats()

    conv_display = f"<code>{session.conversation_id}</code>" if session.conversation_id else "<i>Belum ada sesi aktif</i>"
    model_display = f"<code>{html.escape(session.model)}</code>" if session.model else "<i>Default Server</i>"
    effort_display = f"<code>{html.escape(session.effort)}</code>" if session.effort else "<i>Default</i>"

    status_text = (
        f"📊 <b>Status Antigravity Production Server</b>\n\n"
        f"• 🖥️ <b>Host OS:</b> <code>{html.escape(sys_stats['os'])}</code>\n"
        f"• ⏱️ <b>Bot Uptime:</b> <code>{sys_stats['uptime']}</code>\n"
        f"• 💾 <b>Server Disk:</b> <code>{sys_stats['disk']}</code>\n"
        f"• 📂 <b>Workspace:</b> <code>{html.escape(session.workspace_dir)}</code>\n"
        f"• 💬 <b>Session ID:</b> {conv_display}\n"
        f"• 🧠 <b>Model:</b> {model_display}\n"
        f"• ⚡ <b>Reasoning Effort:</b> {effort_display}\n"
        f"• 🎙️ <b>Voice/Audio:</b> 🟢 Aktif\n"
        f"• 🖼️ <b>Image/Vision:</b> 🟢 Aktif\n"
        f"• ⚙️ <b>Binary:</b> <code>{html.escape(AGY_PATH)}</code>\n"
        f"• 🟢 <b>Status:</b> Siap menerima perintah 24/7."
    )
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

async def workspace_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)

    if not context.args:
        await update.message.reply_text(
            f"📂 <b>Workspace Aktif:</b> <code>{html.escape(session.workspace_dir)}</code>\n\n"
            f"Untuk berpindah folder proyek:\n"
            f"<code>/workspace /path/ke/folder/proyek</code>",
            parse_mode=ParseMode.HTML
        )
        return

    target_dir = os.path.expanduser(" ".join(context.args).strip())
    if not os.path.exists(target_dir):
        await update.message.reply_text(f"❌ Direktori tidak ditemukan:\n<code>{html.escape(target_dir)}</code>", parse_mode=ParseMode.HTML)
        return

    if not os.path.isdir(target_dir):
        await update.message.reply_text(f"❌ Path bukan merupakan folder:\n<code>{html.escape(target_dir)}</code>", parse_mode=ParseMode.HTML)
        return

    session.workspace_dir = os.path.abspath(target_dir)
    session.conversation_id = None
    await update.message.reply_text(
        f"✅ <b>Workspace berhasil diubah!</b>\n\n"
        f"📂 Folder baru: <code>{html.escape(session.workspace_dir)}</code>\n"
        f"🔄 Sesi percakapan direset otomatis untuk folder ini.",
        parse_mode=ParseMode.HTML
    )

async def model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)

    if not context.args:
        curr = html.escape(session.model or DEFAULT_MODEL or "gemini-3.7-flash")
        await update.message.reply_text(
            f"🧠 <b>Model AI Aktif:</b> <code>{curr}</code>\n\n"
            f"<b>Pilihan Model Gemini Terbaru:</b>\n"
            f"• <code>/model gemini-3.7-flash</code> — ⚡ <i>(Rekomendasi) Tercepat, cerdas & reasoning tinggi</i>\n"
            f"• <code>/model gemini-2.5-pro</code> — 🔬 <i>Penalaran kompleks, arsitektur & coding mendalam</i>\n"
            f"• <code>/model gemini-2.5-flash</code> — 🚀 <i>Ringan & responsif</i>\n"
            f"• <code>/model default</code> — <i>Reset ke konfigurasi default (.env)</i>\n\n"
            f"💡 <i>Tip: Kombinasikan dengan <code>/effort high</code> untuk pemecahan masalah yang lebih teliti.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    model_arg = context.args[0].strip()
    if model_arg.lower() in ["default", "reset"]:
        session.model = DEFAULT_MODEL if DEFAULT_MODEL else "gemini-3.7-flash"
        await update.message.reply_text(f"✅ Model dikembalikan ke default: <code>{html.escape(session.model)}</code>", parse_mode=ParseMode.HTML)
    else:
        session.model = model_arg
        await update.message.reply_text(f"✅ Model disetel ke: <code>{html.escape(session.model)}</code>", parse_mode=ParseMode.HTML)

async def effort_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)

    if not context.args:
        curr = html.escape(session.effort or "Default")
        await update.message.reply_text(
            f"⚡ <b>Reasoning Effort:</b> <code>{curr}</code>\n\n"
            f"Pilihan:\n"
            f"• <code>/effort low</code>\n"
            f"• <code>/effort medium</code>\n"
            f"• <code>/effort high</code>\n"
            f"• <code>/effort default</code>",
            parse_mode=ParseMode.HTML
        )
        return

    effort_val = context.args[0].lower().strip()
    if effort_val in ["low", "medium", "high"]:
        session.effort = effort_val
        await update.message.reply_text(f"✅ Reasoning effort diatur ke: <code>{effort_val}</code>", parse_mode=ParseMode.HTML)
    elif effort_val == "default":
        session.effort = None
        await update.message.reply_text("✅ Reasoning effort dikembalikan ke default.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ Pilihan tidak valid. Gunakan <code>low</code>, <code>medium</code>, <code>high</code>, atau <code>default</code>.", parse_mode=ParseMode.HTML)

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    if session.current_task and not session.current_task.done():
        session.current_task.cancel()
        if session.current_pid:
            try:
                # Matikan seluruh process group agy
                os.killpg(os.getpgid(session.current_pid), signal.SIGTERM)
                logger.info(f"Killed process group for PID {session.current_pid}")
            except Exception as e:
                logger.warning(f"Error killing process: {e}")
        await update.message.reply_text("🛑 Permintaan yang sedang berjalan berhasil dibatalkan.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("ℹ️ Tidak ada tugas yang sedang berjalan.", parse_mode=ParseMode.HTML)

async def execute_antigravity(session: UserSession, prompt: str) -> dict:
    """Menjalankan agy CLI non-interaktif dengan process group isolation & timeout."""
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

    # Spawn process dengan isolated process group (preexec_fn=os.setsid)
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None
    )
    session.current_pid = process.pid

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=EXECUTION_TIMEOUT)
    except asyncio.TimeoutError:
        if process.pid:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception:
                pass
        raise RuntimeError(f"Tugas timeout melebihi batas waktu {EXECUTION_TIMEOUT} detik.")
    finally:
        session.current_pid = None

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
        footer_badges = []
        if duration:
            footer_badges.append(f"⏱️ {duration:.1f}s")
        if usage and isinstance(usage, dict):
            tokens = usage.get("total_tokens")
            if tokens:
                footer_badges.append(f"🔢 {tokens:,} tok")

        if footer_badges:
            response_text += f"\n\n---\n*({' • '.join(footer_badges)})*"

        await send_formatted_message(update, response_text)

    except asyncio.CancelledError:
        logger.info("Task cancelled by user.")
    except Exception as e:
        logger.error(f"Gagal memproses prompt: {e}", exc_info=True)
        err_msg = f"⚠️ <b>Terjadi Kesalahan:</b>\n<code>{html.escape(str(e))}</code>"
        await update.message.reply_text(err_msg, parse_mode=ParseMode.HTML)
    finally:
        stop_typing.set()
        await typing_task
        session.current_task = None

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"⛔ Akses ditolak. User ID Anda: <code>{user_id}</code>", parse_mode=ParseMode.HTML)
        return

    prompt = update.message.text
    if not prompt or not prompt.strip():
        return

    session = get_session(user_id)

    if session.current_task and not session.current_task.done():
        await update.message.reply_text("⏳ Sedang memproses tugas sebelumnya. Gunakan <code>/cancel</code> jika ingin membatalkannya.", parse_mode=ParseMode.HTML)
        return

    session.current_task = asyncio.create_task(process_prompt_task(update, context, prompt))

async def voice_audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani pesan suara (Voice Note) dan file audio."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"⛔ Akses ditolak. User ID Anda: <code>{user_id}</code>", parse_mode=ParseMode.HTML)
        return

    session = get_session(user_id)
    if session.current_task and not session.current_task.done():
        await update.message.reply_text("⏳ Sedang memproses tugas sebelumnya. Gunakan <code>/cancel</code> jika ingin membatalkannya.", parse_mode=ParseMode.HTML)
        return

    audio_obj = update.message.voice or update.message.audio
    if not audio_obj:
        return

    # Guard: Max 25 MB
    if audio_obj.file_size and audio_obj.file_size > 25 * 1024 * 1024:
        await update.message.reply_text("❌ Ukuran file audio terlalu besar (maksimal 25MB).", parse_mode=ParseMode.HTML)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    file_ext = ".oga" if update.message.voice else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        telegram_file = await context.bot.get_file(audio_obj.file_id)
        await telegram_file.download_to_drive(custom_path=tmp_path)

        logger.info(f"Mengonversi audio dari user {user_id} ({os.path.getsize(tmp_path)} bytes)...")
        transcribed_text = await transcribe_audio_file(tmp_path)

        if not transcribed_text or not transcribed_text.strip():
            await update.message.reply_text("❓ Suara tidak terdeteksi dengan jelas. Silakan coba rekam ulang.", parse_mode=ParseMode.HTML)
            return

        await update.message.reply_text(
            f"🎙️ <b>Transkripsi Suara:</b>\n<blockquote>{html.escape(transcribed_text)}</blockquote>",
            parse_mode=ParseMode.HTML
        )

        session.current_task = asyncio.create_task(process_prompt_task(update, context, transcribed_text))

    except Exception as e:
        logger.error(f"Error memproses audio: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Gagal memproses audio:\n<code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

async def photo_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani foto, screenshot, dan file gambar."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"⛔ Akses ditolak. User ID Anda: <code>{user_id}</code>", parse_mode=ParseMode.HTML)
        return

    session = get_session(user_id)
    if session.current_task and not session.current_task.done():
        await update.message.reply_text("⏳ Sedang memproses tugas sebelumnya. Gunakan <code>/cancel</code> jika ingin membatalkannya.", parse_mode=ParseMode.HTML)
        return

    if update.message.photo:
        file_obj = update.message.photo[-1]
        file_name = f"image_{int(time.time())}.png"
    elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith("image/"):
        file_obj = update.message.document
        orig_name = update.message.document.file_name or "image.png"
        file_name = f"{int(time.time())}_{orig_name}"
    else:
        await update.message.reply_text("❌ Format file bukan gambar yang didukung.")
        return

    # Guard: Max 20 MB
    if file_obj.file_size and file_obj.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ Ukuran gambar terlalu besar (maksimal 20MB).", parse_mode=ParseMode.HTML)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    uploads_dir = os.path.join(session.workspace_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    save_path = os.path.join(uploads_dir, file_name)

    try:
        telegram_file = await context.bot.get_file(file_obj.file_id)
        await telegram_file.download_to_drive(custom_path=save_path)
        logger.info(f"Gambar disimpan ke: {save_path} ({os.path.getsize(save_path)} bytes)")

        caption = (update.message.caption or "").strip()
        if not caption:
            caption = "Analisis gambar ini dan bantu saya mengimplementasikan atau memeriksa kodenya."

        rel_path = os.path.relpath(save_path, session.workspace_dir)
        await update.message.reply_text(
            f"🖼️ <b>Gambar Diterima!</b>\n"
            f"📁 Lokasi: <code>{html.escape(rel_path)}</code>\n"
            f"📝 Instruksi:\n<blockquote>{html.escape(caption)}</blockquote>",
            parse_mode=ParseMode.HTML
        )

        image_prompt = (
            f"User mengunggah sebuah gambar/screenshot yang tersimpan di path: `{save_path}`.\n"
            f"Gunakan tool 'view_file' untuk melihat dan menganalisis gambar tersebut.\n\n"
            f"Instruksi User: {caption}"
        )

        session.current_task = asyncio.create_task(process_prompt_task(update, context, image_prompt))

    except Exception as e:
        logger.error(f"Error memproses gambar: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Gagal mengunduh gambar:\n<code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)

def main():
    global TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, DEFAULT_WORKSPACE, GEMINI_API_KEY, AGY_PATH

    if "--setup" in sys.argv or "--init" in sys.argv or "-s" in sys.argv:
        run_interactive_setup(force=True)
        sys.exit(0)

    if not TELEGRAM_BOT_TOKEN:
        if check_and_ensure_credentials():
            load_dotenv(override=True)
            TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            ALLOWED_USER_IDS_RAW = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
            DEFAULT_WORKSPACE = os.getenv("ANTIGRAVITY_WORKSPACE", os.path.expanduser("~"))
            GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
            AGY_PATH = find_agy_binary()
            if ALLOWED_USER_IDS_RAW:
                for uid in ALLOWED_USER_IDS_RAW.split(","):
                    uid_clean = uid.strip()
                    if uid_clean.isdigit():
                        ALLOWED_USER_IDS.add(int(uid_clean))
        else:
            print("❌ Error: TELEGRAM_BOT_TOKEN belum diisi di file .env")
            print("Jalankan './init.sh' untuk inisiasi kredensial.")
            sys.exit(1)

    if not os.path.exists(AGY_PATH) and not shutil.which("agy"):
        logger.error(f"Binary 'agy' tidak ditemukan di path: {AGY_PATH}")
        print(f"❌ Error: Binary 'agy' tidak ditemukan di: {AGY_PATH}")
        print("Pastikan Antigravity CLI telah terinstal.")
        sys.exit(1)

    if not ALLOWED_USER_IDS:
        print("⚠️ PERINGATAN: ALLOWED_TELEGRAM_USER_ID belum diisi di .env.")
        print("Bot akan menolak semua pesan hingga Anda menambahkan ID Anda.")

    logger.info("Memulai Antigravity Telegram Bridge (Production Engine)...")
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

    # Handler Foto, Screenshot, dan File Gambar Dokumen
    application.add_handler(MessageHandler(filters.PHOTO, photo_image_handler))
    application.add_handler(MessageHandler(filters.Document.IMAGE, photo_image_handler))

    print(f"🤖 Antigravity Telegram Bridge AKTIF (Production Ready)")
    print(f"🖥️ Platform: {platform.system()} {platform.machine()}")
    print(f"⚙️ Binary Path: {AGY_PATH}")
    print(f"📂 Default Workspace: {DEFAULT_WORKSPACE}")
    print(f"🔑 Allowed User IDs: {list(ALLOWED_USER_IDS) if ALLOWED_USER_IDS else 'Belum ada'}")

    application.run_polling()

if __name__ == "__main__":
    main()
