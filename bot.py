#!/usr/bin/env python3
"""
Antigravity Telegram Bridge (Universal Cross-Platform Edition)
Menghubungkan Telegram Chat, Voice/Audio, dan Gambar ke Google Antigravity di Komputer / VPS Linux / macOS / Windows.

Fitur Unggulan & Cross-Platform:
- 🌐 Universal OS Support: Windows (10/11), Linux (Ubuntu, Debian, CentOS, Arch), macOS (Intel & Apple Silicon), Docker
- 📱 Modern Telegram UI: Inline Keyboards, Quick Actions, Status Bar, Menu Bar Integration
- ⚡ Model Selector: Dukungan Gemini 3.7 Flash, Gemini 3.1 Pro, Gemini 3.6 Flash
- 🧠 Reasoning Effort: High, Medium, Low toggle
- 🗂️ Interactive File Explorer (/ls) & Git Status (/git)
- 🖥️ Quick Shell Executor (/sh)
- 📊 Real-Time Server Healthcheck (CPU, RAM meter, Disk meter, Uptime)
- 🎙️ Multimodal Voice Transcriber (Gemini 3.7 / 3.6 Audio)
- 🖼️ Vision & Screenshot Input
- 🛡️ Cross-Platform Process Group Isolation & Fast /cancel (POSIX & Windows taskkill)
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
import subprocess
from typing import Dict, List, Optional, Set
from dotenv import load_dotenv

from init_config import check_and_ensure_credentials, run_interactive_setup

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeDefault,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Audio libraries
import speech_recognition as sr
from pydub import AudioSegment

# Optional psutil for system monitoring
try:
    import psutil
except ImportError:
    psutil = None

# OS Platform Identification
IS_WINDOWS = (platform.system() == "Windows")
IS_MACOS = (platform.system() == "Darwin")
IS_LINUX = (platform.system() == "Linux")

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

# Dynamic Binary Discovery for agy (Cross-Platform)
def find_agy_binary() -> str:
    """Mendeteksi lokasi binary agy di berbagai OS (Linux, macOS, Windows)."""
    env_path = os.getenv("AGY_BINARY_PATH", "").strip()
    if env_path:
        expanded = os.path.abspath(os.path.expanduser(env_path))
        if os.path.exists(expanded):
            return expanded

    # Cek melalui PATH dengan ekstensi binary yang sesuai
    candidate_names = ["agy.cmd", "agy.exe", "agy.bat", "agy"] if IS_WINDOWS else ["agy"]
    for name in candidate_names:
        which_path = shutil.which(name)
        if which_path and os.path.exists(which_path):
            return which_path

    # Path umum default per sistem operasi
    home = os.path.expanduser("~")
    common_paths = []

    if IS_WINDOWS:
        appdata = os.getenv("APPDATA", "")
        localappdata = os.getenv("LOCALAPPDATA", "")
        common_paths.extend([
            os.path.join(home, ".local", "bin", "agy.exe"),
            os.path.join(home, ".local", "bin", "agy.cmd"),
            os.path.join(home, ".local", "bin", "agy.bat"),
            os.path.join(localappdata, "Programs", "Antigravity", "bin", "agy.cmd"),
            os.path.join(localappdata, "Programs", "Antigravity", "agy.exe"),
            r"C:\Program Files\Antigravity\agy.exe",
            r"C:\ProgramData\chocolatey\bin\agy.exe",
        ])
    else:
        common_paths.extend([
            os.path.join(home, ".local", "bin", "agy"),
            "/usr/local/bin/agy",
            "/usr/bin/agy",
            "/opt/homebrew/bin/agy",
            "/home/linuxbrew/.linuxbrew/bin/agy",
        ])

    for p in common_paths:
        if p and os.path.exists(p):
            return p

    return "agy"

AGY_PATH = find_agy_binary()

# Cross-platform Process Tree Killer
def kill_process_tree(pid: Optional[int], sig=signal.SIGTERM):
    """Menghentikan proses dan seluruh child process secara cross-platform."""
    if not pid:
        return
    try:
        if IS_WINDOWS:
            # Di Windows gunakan taskkill untuk mematikan process tree (/T) secara paksa (/F)
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
            logger.info(f"Terminated Windows process tree for PID {pid}")
        else:
            if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                try:
                    os.killpg(os.getpgid(pid), sig)
                except Exception:
                    os.kill(pid, sig)
            else:
                os.kill(pid, sig)
            logger.info(f"Terminated POSIX process group for PID {pid}")
    except Exception as e:
        logger.debug(f"Error killing process {pid}: {e}")

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
        self.mode: Optional[str] = None  # plan, accept-edits
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

# Progress Bar Generator Helper
def make_progress_bar(percent: float, length: int = 10) -> str:
    filled = max(0, min(length, int(round(length * percent / 100.0))))
    return "[" + "█" * filled + "░" * (length - filled) + f"] {percent:.1f}%"

# System Metrics Helper (Cross-Platform)
def get_system_stats() -> dict:
    """Mengambil informasi sistem server (Uptime, OS, CPU, RAM, Disk)."""
    stats = {}
    
    # Uptime bot
    uptime_seconds = int(time.time() - BOT_START_TIME)
    hours, rem = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    stats["uptime"] = f"{hours}h {minutes}m {seconds}s"
    stats["os"] = f"{platform.system()} {platform.release()} ({platform.machine()})"

    # CPU & RAM via psutil
    if psutil:
        try:
            cpu_pct = psutil.cpu_percent(interval=0.05)
            ram = psutil.virtual_memory()
            ram_used_gb = ram.used / (1024 ** 3)
            ram_total_gb = ram.total / (1024 ** 3)
            stats["cpu"] = f"{cpu_pct:.1f}%"
            stats["ram_bar"] = make_progress_bar(ram.percent)
            stats["ram"] = f"{ram_used_gb:.1f}GB / {ram_total_gb:.1f}GB ({ram.percent:.1f}%)"
        except Exception:
            stats["cpu"] = "N/A"
            stats["ram_bar"] = ""
            stats["ram"] = "N/A"
    else:
        stats["cpu"] = "N/A"
        stats["ram_bar"] = ""
        stats["ram"] = "N/A"

    # Disk usage (Cross-platform root drive)
    try:
        drive_root = os.path.splitdrive(os.getcwd())[0] + "\\" if IS_WINDOWS else "/"
        total, used, free = shutil.disk_usage(drive_root)
        disk_pct = (used / total) * 100.0
        used_gb = used // (1024 ** 3)
        total_gb = total // (1024 ** 3)
        free_gb = free // (1024 ** 3)
        stats["disk_bar"] = make_progress_bar(disk_pct)
        stats["disk"] = f"{used_gb}GB / {total_gb}GB (Free: {free_gb}GB)"
    except Exception:
        stats["disk_bar"] = ""
        stats["disk"] = "N/A"

    return stats

# ==========================================
# INLINE KEYBOARD UI BUILDERS
# ==========================================

def build_main_menu_markup() -> InlineKeyboardMarkup:
    """Membuat keyboard menu utama interaktif."""
    keyboard = [
        [
            InlineKeyboardButton("⚡ Ganti Model", callback_data="cb:menu_model"),
            InlineKeyboardButton("🧠 Reasoning Effort", callback_data="cb:menu_effort"),
        ],
        [
            InlineKeyboardButton("📊 Status Server", callback_data="cb:status"),
            InlineKeyboardButton("📁 Workspace", callback_data="cb:menu_ws"),
        ],
        [
            InlineKeyboardButton("🗂️ File Browser (/ls)", callback_data="cb:ls"),
            InlineKeyboardButton("🐙 Git Status (/git)", callback_data="cb:git"),
        ],
        [
            InlineKeyboardButton("🔄 Reset Sesi Baru", callback_data="cb:reset"),
            InlineKeyboardButton("🛑 Batalkan (/cancel)", callback_data="cb:cancel"),
        ],
        [
            InlineKeyboardButton("ℹ️ Bantuan Perintah", callback_data="cb:help"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_model_markup(current_model: Optional[str]) -> InlineKeyboardMarkup:
    """Keyboard pemilih model AI Gemini."""
    curr = current_model or DEFAULT_MODEL or "gemini-3.7-flash"
    
    def mark(m):
        return f"✅ {m}" if curr == m else m

    keyboard = [
        [InlineKeyboardButton(f"⚡ {mark('gemini-3.7-flash')} (Terbaru)", callback_data="cb:set_model:gemini-3.7-flash")],
        [InlineKeyboardButton(f"🔬 {mark('gemini-3.1-pro')}", callback_data="cb:set_model:gemini-3.1-pro")],
        [InlineKeyboardButton(f"🚀 {mark('gemini-3.6-flash')}", callback_data="cb:set_model:gemini-3.6-flash")],
        [InlineKeyboardButton("⚙️ Reset ke Default Server", callback_data="cb:set_model:default")],
        [InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="cb:menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_effort_markup(current_effort: Optional[str]) -> InlineKeyboardMarkup:
    """Keyboard pengatur tingkat penalaran reasoning."""
    curr = current_effort or "default"

    def mark(e, label):
        return f"✅ {label}" if curr == e else label

    keyboard = [
        [
            InlineKeyboardButton(f"🟢 {mark('high', 'High (Maksimal)')}", callback_data="cb:set_effort:high"),
            InlineKeyboardButton(f"🟡 {mark('medium', 'Medium')}", callback_data="cb:set_effort:medium"),
        ],
        [
            InlineKeyboardButton(f"🔵 {mark('low', 'Low (Cepat)')}", callback_data="cb:set_effort:low"),
            InlineKeyboardButton(f"⚪ {mark('default', 'Default')}", callback_data="cb:set_effort:default"),
        ],
        [InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="cb:menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_status_markup() -> InlineKeyboardMarkup:
    """Keyboard untuk tampilan status server."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh Status", callback_data="cb:refresh_status"),
            InlineKeyboardButton("⚡ Ganti Model", callback_data="cb:menu_model"),
        ],
        [
            InlineKeyboardButton("📁 Workspace", callback_data="cb:menu_ws"),
            InlineKeyboardButton("🔙 Menu Utama", callback_data="cb:menu_main"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_workspace_markup(current_dir: str) -> InlineKeyboardMarkup:
    """Keyboard manajemen workspace direktori."""
    keyboard = [
        [
            InlineKeyboardButton("🏠 Home (~)", callback_data="cb:ws_home"),
            InlineKeyboardButton("⬆️ Parent (..)", callback_data="cb:ws_up"),
        ],
        [
            InlineKeyboardButton("🗂️ Lihat Isi Folder", callback_data="cb:ls"),
            InlineKeyboardButton("🐙 Git Status", callback_data="cb:git"),
        ],
        [InlineKeyboardButton("🔙 Kembali ke Menu Utama", callback_data="cb:menu_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_quick_actions_markup() -> InlineKeyboardMarkup:
    """Keyboard ringkas aksi cepat setelah respons selesai."""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Sesi Baru", callback_data="cb:reset"),
            InlineKeyboardButton("📊 Status", callback_data="cb:status"),
            InlineKeyboardButton("⚡ Model", callback_data="cb:menu_model"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==========================================
# TEXT CONTENT BUILDERS
# ==========================================

def build_start_text(username: str, session: UserSession) -> str:
    model_str = session.model or DEFAULT_MODEL or "gemini-3.7-flash"
    effort_str = session.effort or "default"
    return (
        f"🚀 <b>Antigravity Telegram Bridge</b> <code>v2.5</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Halo <b>{username}</b>! Bot siap menerima instruksi AI coding & terminal 24/7 di {platform.system()}.\n\n"
        f"📊 <b>Konfigurasi Aktif:</b>\n"
        f"• 🧠 <b>Model:</b> <code>{html.escape(model_str)}</code>\n"
        f"• ⚡ <b>Reasoning:</b> <code>{html.escape(effort_str)}</code>\n"
        f"• 📂 <b>Workspace:</b> <code>{html.escape(session.workspace_dir)}</code>\n\n"
        f"🎯 <b>Input yang Didukung:</b>\n"
        f"• 💬 <b>Teks:</b> Kirim prompt, instruksi coding, perbaikan bug, refactor.\n"
        f"• 🎙️ <b>Voice Note:</b> Rekam suara, otomatis ditranskripsi oleh Gemini.\n"
        f"• 🖼️ <b>Gambar / Foto:</b> Kirim tangkapan layar UI atau error log.\n\n"
        f"👇 <i>Pilih menu interaktif di bawah untuk mengatur bot:</i>"
    )

def build_status_text(session: UserSession) -> str:
    sys_stats = get_system_stats()
    conv_display = f"<code>{session.conversation_id}</code>" if session.conversation_id else "<i>Belum ada (Sesi Bersih)</i>"
    model_display = f"<code>{html.escape(session.model or DEFAULT_MODEL or 'gemini-3.7-flash')}</code>"
    effort_display = f"<code>{html.escape(session.effort or 'default')}</code>"

    ram_line = ""
    if sys_stats.get("ram_bar"):
        ram_line = f"• 🧠 <b>RAM Server:</b> {sys_stats['ram']}\n  <code>{sys_stats['ram_bar']}</code>\n"

    disk_line = ""
    if sys_stats.get("disk_bar"):
        disk_line = f"• 💾 <b>Disk Storage:</b> {sys_stats['disk']}\n  <code>{sys_stats['disk_bar']}</code>\n"

    cpu_line = f"• 📈 <b>CPU Load:</b> <code>{sys_stats['cpu']}</code>\n" if sys_stats.get("cpu") != "N/A" else ""

    return (
        f"📊 <b>Dashboard Status Antigravity Server</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🖥️ <b>Informasi Host & Sistem:</b>\n"
        f"• <b>OS:</b> <code>{html.escape(sys_stats['os'])}</code>\n"
        f"• ⏱️ <b>Bot Uptime:</b> <code>{sys_stats['uptime']}</code>\n"
        f"{cpu_line}"
        f"{ram_line}"
        f"{disk_line}"
        f"\n🤖 <b>Antigravity Agent & Sesi:</b>\n"
        f"• 🧠 <b>Model Aktif:</b> {model_display}\n"
        f"• ⚡ <b>Reasoning Effort:</b> {effort_display}\n"
        f"• 📂 <b>Workspace:</b> <code>{html.escape(session.workspace_dir)}</code>\n"
        f"• 💬 <b>Session ID:</b> {conv_display}\n"
        f"• 🎙️ <b>Audio Transcriber:</b> 🟢 Aktif\n"
        f"• 🖼️ <b>Vision/Image Guard:</b> 🟢 Aktif\n"
        f"• ⚙️ <b>Binary:</b> <code>{html.escape(AGY_PATH)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>Status:</b> Siap menerima perintah 24/7."
    )

def build_help_text() -> str:
    return (
        f"📖 <b>Panduan Perintah Lengkap</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>🤖 Interaksi AI & Coding:</b>\n"
        f"• <b>Kirim Pesan Teks</b> — Mengeksekusi tugas coding di workspace.\n"
        f"• <b>Voice Note / Audio</b> — Rekam suara, otomatis diproses jadi prompt.\n"
        f"• <b>Kirim Foto / Screenshot</b> — Analisis gambar desain UI atau error log.\n"
        f"• <code>/new</code> atau <code>/reset</code> — Mulai percakapan sesi baru.\n"
        f"• <code>/cancel</code> — Batalkan proses yang sedang berjalan seketika.\n\n"
        f"<b>⚙️ Konfigurasi Model & Server:</b>\n"
        f"• <code>/menu</code> — Tampilkan Dashboard Menu Utama.\n"
        f"• <code>/status</code> — Cek RAM, CPU, Disk, Uptime, & status sesi.\n"
        f"• <code>/model &lt;nama&gt;</code> — Ganti model (contoh: <code>/model gemini-3.7-flash</code>).\n"
        f"• <code>/effort &lt;low|medium|high&gt;</code> — Atur tingkat penalaran.\n"
        f"• <code>/mode &lt;plan|accept-edits&gt;</code> — Atur mode eksekusi agent.\n\n"
        f"<b>📁 Navigasi & File System:</b>\n"
        f"• <code>/workspace &lt;path&gt;</code> — Pindah folder proyek aktif.\n"
        f"• <code>/ls [path]</code> — Jelajahi daftar file & folder di workspace.\n"
        f"• <code>/git</code> — Cek branch & status Git repository.\n"
        f"• <code>/sh &lt;command&gt;</code> — Jalankan terminal command cepat.\n"
        f"• <code>/whoami</code> — Cek Telegram User ID & otorisasi akun."
    )

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

async def send_formatted_message(update: Update, raw_text: str, attach_keyboard: bool = True):
    """Mengirim pesan dengan HTML parser dan fallback teks bersih."""
    if not raw_text or not raw_text.strip():
        raw_text = "<i>(Tidak ada output teks dari agen)</i>"

    chunks = chunk_markdown_safely(raw_text, max_chars=3400)

    for i, chunk in enumerate(chunks):
        formatted_html = markdown_to_telegram_html(chunk)
        # Lampirkan quick actions hanya pada chunk terakhir
        is_last = (i == len(chunks) - 1)
        reply_markup = build_quick_actions_markup() if (is_last and attach_keyboard) else None

        try:
            await update.message.reply_text(
                formatted_html,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.warning(f"HTML parse failed ({e}), sending clean plain text...")
            clean_text = clean_ansi_and_unicode(chunk)
            await update.message.reply_text(
                clean_text,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )

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

# ==========================================
# MULTIMODAL AUDIO TRANSCRIPTION
# ==========================================

async def transcribe_audio_file(file_path: str) -> str:
    """Mengonversi file audio (Voice Note / Audio) ke teks dengan Gemini atau Google SR."""
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
            models_to_try = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.1-pro", "gemini-2.0-flash"]
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

# ==========================================
# COMMAND HANDLERS
# ==========================================

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
    welcome_text = build_start_text(username, session)
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu_markup())

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return
    username = html.escape(update.effective_user.username or update.effective_user.first_name)
    session = get_session(user_id)
    text = build_start_text(username, session)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu_markup())

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return
    help_text = build_help_text()
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu_markup())

async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    session.conversation_id = None
    await update.message.reply_text("🔄 <b>Sesi percakapan telah direset.</b> Percakapan berikutnya akan dimulai dari awal konteks baru.", parse_mode=ParseMode.HTML)

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    status_text = build_status_text(session)
    await update.message.reply_text(status_text, parse_mode=ParseMode.HTML, reply_markup=build_status_markup())

async def workspace_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)

    if not context.args:
        text = (
            f"📂 <b>Workspace Manajemen</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 <b>Folder Aktif:</b> <code>{html.escape(session.workspace_dir)}</code>\n\n"
            f"Untuk berpindah ke folder proyek lain:\n"
            f"<code>/workspace /path/ke/folder/proyek</code>\n\n"
            f"<i>Atau gunakan tombol navigasi cepat di bawah:</i>"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=build_workspace_markup(session.workspace_dir))
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
        parse_mode=ParseMode.HTML,
        reply_markup=build_workspace_markup(session.workspace_dir)
    )

async def model_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)

    if not context.args:
        curr = html.escape(session.model or DEFAULT_MODEL or "gemini-3.7-flash")
        text = (
            f"🧠 <b>Pilihan Model Gemini AI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Model Aktif: <code>{curr}</code>\n\n"
            f"<b>Daftar Model yang Didukung:</b>\n"
            f"• ⚡ <code>gemini-3.7-flash</code> — <i>(Rekomendasi) Tercepat, cerdas & reasoning tinggi</i>\n"
            f"• 🔬 <code>gemini-3.1-pro</code> — <i>Penalaran kompleks, arsitektur & coding mendalam</i>\n"
            f"• 🚀 <code>gemini-3.6-flash</code> — <i>Ringan & responsif</i>\n\n"
            f"<i>Pilih model dengan 1 klik pada tombol di bawah:</i>"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=build_model_markup(session.model))
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
        curr = html.escape(session.effort or "default")
        text = (
            f"⚡ <b>Reasoning Effort Manager</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Tingkat Penalaran Saat Ini: <code>{curr}</code>\n\n"
            f"• 🟢 <b>High:</b> Analisis mendalam & langkah pemecahan masalah teliti.\n"
            f"• 🟡 <b>Medium:</b> Keseimbangan antara kecepatan dan penalaran.\n"
            f"• 🔵 <b>Low:</b> Jawaban langsung dan cepat.\n"
            f"• ⚪ <b>Default:</b> Mengikuti konfigurasi default Antigravity.\n\n"
            f"<i>Pilih level penalaran:</i>"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=build_effort_markup(session.effort))
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

async def mode_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mengatur mode eksekusi Antigravity agent (plan, accept-edits)."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)

    if not context.args:
        curr = html.escape(session.mode or "default")
        text = (
            f"🎯 <b>Antigravity Agent Mode</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Mode Saat Ini: <code>{curr}</code>\n\n"
            f"Pilihan Mode:\n"
            f"• <code>/mode plan</code> — Mode perancangan & pembuatan rencana implementasi.\n"
            f"• <code>/mode accept-edits</code> — Mode eksekusi otomatis tanpa konfirmasi edit.\n"
            f"• <code>/mode default</code> — Mode eksekusi standar."
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    m = context.args[0].lower().strip()
    if m in ["plan", "accept-edits"]:
        session.mode = m
        await update.message.reply_text(f"✅ Agent mode disetel ke: <code>{m}</code>", parse_mode=ParseMode.HTML)
    elif m in ["default", "reset"]:
        session.mode = None
        await update.message.reply_text("✅ Agent mode dikembalikan ke default.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("❌ Mode tidak valid. Gunakan <code>plan</code>, <code>accept-edits</code>, atau <code>default</code>.", parse_mode=ParseMode.HTML)

async def ls_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """File & directory explorer interaktif di workspace (Cross-Platform)."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    target_path = session.workspace_dir
    if context.args:
        custom_sub = " ".join(context.args).strip()
        custom_full = os.path.abspath(os.path.join(session.workspace_dir, os.path.expanduser(custom_sub)))
        if os.path.exists(custom_full) and os.path.isdir(custom_full):
            target_path = custom_full

    try:
        entries = sorted(os.listdir(target_path))
    except Exception as e:
        await update.message.reply_text(f"⚠️ Gagal membaca direktori: <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)
        return

    dirs_list = []
    files_list = []

    for name in entries:
        if name.startswith(".git"):
            continue
        full = os.path.join(target_path, name)
        if os.path.isdir(full):
            dirs_list.append(name)
        else:
            try:
                sz = os.path.getsize(full)
                if sz < 1024:
                    sz_str = f"{sz}B"
                elif sz < 1024 * 1024:
                    sz_str = f"{sz/1024:.1f}KB"
                else:
                    sz_str = f"{sz/(1024*1024):.1f}MB"
            except Exception:
                sz_str = ""
            
            ext = os.path.splitext(name)[1].lower()
            icon = "📄"
            if ext in [".py"]: icon = "🐍"
            elif ext in [".js", ".ts", ".jsx", ".tsx"]: icon = "🟨"
            elif ext in [".json", ".yaml", ".yml", ".toml"]: icon = "📦"
            elif ext in [".md", ".txt"]: icon = "📝"
            elif ext in [".sh", ".bash", ".bat", ".cmd", ".ps1"]: icon = "🐚"
            elif ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]: icon = "🖼️"
            elif ext in [".html", ".css"]: icon = "🌐"

            files_list.append((icon, name, sz_str))

    lines = [
        f"🗂️ <b>File Browser</b>",
        f"📂 <code>{html.escape(target_path)}</code>",
        f"━━━━━━━━━━━━━━━━━━━━━━"
    ]

    if not dirs_list and not files_list:
        lines.append("<i>(Folder kosong)</i>")
    else:
        for d in dirs_list[:15]:
            lines.append(f"📁 <b>{html.escape(d)}/</b>")
        for icon, f_name, sz_str in files_list[:25]:
            size_badge = f" <i>({sz_str})</i>" if sz_str else ""
            lines.append(f"{icon} <code>{html.escape(f_name)}</code>{size_badge}")

        total_items = len(dirs_list) + len(files_list)
        if total_items > 40:
            lines.append(f"\n<i>...dan {total_items - 40} file/folder lainnya.</i>")

    lines.append(f"\n📊 Total: {len(dirs_list)} Folder, {len(files_list)} File")

    keyboard = [
        [
            InlineKeyboardButton("🏠 Home (~)", callback_data="cb:ws_home"),
            InlineKeyboardButton("⬆️ Parent (..)", callback_data="cb:ws_up"),
        ],
        [
            InlineKeyboardButton("🐙 Git Status", callback_data="cb:git"),
            InlineKeyboardButton("🔙 Menu Utama", callback_data="cb:menu_main"),
        ]
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def git_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Melihat status Git repository di workspace aktif (Cross-Platform)."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    ws = session.workspace_dir

    if not os.path.exists(os.path.join(ws, ".git")):
        await update.message.reply_text(
            f"ℹ️ Workspace saat ini bukan merupakan Git repository:\n<code>{html.escape(ws)}</code>",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        # Branch name
        branch_proc = await asyncio.create_subprocess_exec(
            "git", "branch", "--show-current",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=ws
        )
        b_stdout, _ = await branch_proc.communicate()
        branch_name = b_stdout.decode().strip() or "HEAD"

        # Status
        status_proc = await asyncio.create_subprocess_exec(
            "git", "status", "--short",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=ws
        )
        s_stdout, _ = await status_proc.communicate()
        status_out = s_stdout.decode().strip()

        # Last commit
        log_proc = await asyncio.create_subprocess_exec(
            "git", "log", "-1", "--pretty=format:%h - %s (%cr)",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=ws
        )
        l_stdout, _ = await log_proc.communicate()
        last_commit = l_stdout.decode().strip() or "Belum ada commit"

        status_display = f"<pre><code>{html.escape(status_out)}</code></pre>" if status_out else "<i>🟢 Working tree clean (Semua perubahan telah di-commit)</i>"

        text = (
            f"🐙 <b>Git Repository Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📂 <b>Workspace:</b> <code>{html.escape(ws)}</code>\n"
            f"🌿 <b>Branch:</b> <code>{html.escape(branch_name)}</code>\n"
            f"📝 <b>Commit Terakhir:</b> <code>{html.escape(last_commit)}</code>\n\n"
            f"📋 <b>Status File:</b>\n"
            f"{status_display}"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Gagal memeriksa Git: <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)

async def sh_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menjalankan perintah terminal / shell cepat di workspace (Cross-Platform)."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    if not context.args:
        shell_example = "dir" if IS_WINDOWS else "ls -la"
        await update.message.reply_text(
            f"⚡ <b>Shell Command Runner ({platform.system()})</b>\n\n"
            f"Contoh penggunaan:\n"
            f"<code>/sh {shell_example}</code>\n"
            f"<code>/sh git status</code>\n"
            f"<code>/sh npm test</code>",
            parse_mode=ParseMode.HTML
        )
        return

    command_str = " ".join(context.args).strip()
    session = get_session(user_id)
    ws = session.workspace_dir

    start_t = time.time()
    try:
        proc = await asyncio.create_subprocess_shell(
            command_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=ws
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        dur = time.time() - start_t

        out_str = stdout.decode("utf-8", errors="replace").strip()
        err_str = stderr.decode("utf-8", errors="replace").strip()
        combined = out_str or err_str or "(Perintah selesai tanpa output)"

        code_badge = "🟢 SUCCESS" if proc.returncode == 0 else f"🔴 EXIT {proc.returncode}"

        result_header = (
            f"⚡ <b>Terminal Output</b> ({code_badge} • ⏱️ {dur:.2f}s)\n"
            f"📂 <code>{html.escape(ws)}</code>\n"
            f"👉 <code>{html.escape(command_str)}</code>\n\n"
        )
        await send_formatted_message(update, f"{result_header}```bash\n{combined}\n```", attach_keyboard=False)
    except asyncio.TimeoutError:
        await update.message.reply_text("⏱️ <b>Timeout:</b> Perintah shell melebihi batas waktu 60 detik.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"⚠️ <b>Error:</b> <code>{html.escape(str(e))}</code>", parse_mode=ParseMode.HTML)

async def whoami_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menampilkan detail identitas akun Telegram dan status otorisasi."""
    user = update.effective_user
    user_id = user.id
    username = user.username or "(Tidak ada username)"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    authorized = is_authorized(user_id)
    auth_badge = "🟢 Terdaftar (Diizinkan)" if authorized else "🔴 Ditolak (Belum di Whitelist)"

    text = (
        f"👤 <b>Informasi Akun Telegram</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>User ID:</b> <code>{user_id}</code>\n"
        f"• <b>Nama:</b> {html.escape(full_name)}\n"
        f"• <b>Username:</b> @{html.escape(username)}\n"
        f"• <b>Status Whitelist:</b> {auth_badge}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    session = get_session(user_id)
    if session.current_task and not session.current_task.done():
        session.current_task.cancel()
        if session.current_pid:
            kill_process_tree(session.current_pid, signal.SIGTERM)
        await update.message.reply_text("🛑 <b>Tugas yang sedang berjalan berhasil dibatalkan.</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("ℹ️ Tidak ada tugas yang sedang berjalan.", parse_mode=ParseMode.HTML)

# ==========================================
# CALLBACK QUERY HANDLER (INLINE BUTTONS)
# ==========================================

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani interaksi klik pada semua Inline Keyboard Buttons."""
    query = update.callback_query
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await query.answer("⛔ Akses ditolak.", show_alert=True)
        return

    data = query.data or ""
    session = get_session(user_id)

    # 1. Main Menu
    if data == "cb:menu_main":
        username = html.escape(update.effective_user.username or update.effective_user.first_name)
        text = build_start_text(username, session)
        await query.answer()
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_main_menu_markup())

    # 2. Model Menu
    elif data == "cb:menu_model":
        curr = html.escape(session.model or DEFAULT_MODEL or "gemini-3.7-flash")
        text = (
            f"🧠 <b>Pilihan Model Gemini AI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Model Aktif: <code>{curr}</code>\n\n"
            f"• ⚡ <code>gemini-3.7-flash</code> — <i>(Rekomendasi) Tercepat & reasoning tinggi</i>\n"
            f"• 🔬 <code>gemini-3.1-pro</code> — <i>Penalaran kompleks & coding mendalam</i>\n"
            f"• 🚀 <code>gemini-3.6-flash</code> — <i>Ringan & responsif</i>\n\n"
            f"<i>Pilih model dengan 1 klik:</i>"
        )
        await query.answer()
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_model_markup(session.model))

    # 3. Set Model
    elif data.startswith("cb:set_model:"):
        selected = data.split(":", 2)[2]
        if selected == "default":
            session.model = DEFAULT_MODEL if DEFAULT_MODEL else "gemini-3.7-flash"
        else:
            session.model = selected

        await query.answer(f"✅ Model disetel ke {session.model}")
        text = (
            f"✅ <b>Model AI Berhasil Diperbarui!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Model Aktif: <code>{html.escape(session.model)}</code>\n\n"
            f"<i>Pilih model lain atau kembali ke menu:</i>"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_model_markup(session.model))

    # 4. Effort Menu
    elif data == "cb:menu_effort":
        curr = html.escape(session.effort or "default")
        text = (
            f"⚡ <b>Reasoning Effort Manager</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Tingkat Penalaran Saat Ini: <code>{curr}</code>\n\n"
            f"• 🟢 <b>High:</b> Analisis teliti & pemecahan masalah mendalam.\n"
            f"• 🟡 <b>Medium:</b> Keseimbangan kecepatan dan penalaran.\n"
            f"• 🔵 <b>Low:</b> Jawaban cepat dan to-the-point.\n"
            f"• ⚪ <b>Default:</b> Mengikuti konfigurasi server.\n\n"
            f"<i>Pilih level penalaran:</i>"
        )
        await query.answer()
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_effort_markup(session.effort))

    # 5. Set Effort
    elif data.startswith("cb:set_effort:"):
        selected = data.split(":", 2)[2]
        if selected == "default":
            session.effort = None
        else:
            session.effort = selected

        effort_display = session.effort or "default"
        await query.answer(f"✅ Effort diatur ke {effort_display}")
        text = (
            f"✅ <b>Reasoning Effort Diperbarui!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Tingkat Penalaran: <code>{html.escape(effort_display)}</code>\n\n"
            f"<i>Pilih level lain atau kembali ke menu:</i>"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_effort_markup(session.effort))

    # 6. Status & Refresh
    elif data in ["cb:status", "cb:refresh_status"]:
        await query.answer("🔄 Memperbarui metrik server...")
        text = build_status_text(session)
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_status_markup())
        except Exception:
            pass

    # 7. Workspace Menu
    elif data == "cb:menu_ws":
        text = (
            f"📂 <b>Workspace Manajemen</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 <b>Folder Aktif:</b> <code>{html.escape(session.workspace_dir)}</code>\n\n"
            f"<i>Gunakan tombol cepat di bawah atau ketik <code>/workspace /path/ke/proyek</code>:</i>"
        )
        await query.answer()
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_workspace_markup(session.workspace_dir))

    # 8. Workspace Shortcuts
    elif data == "cb:ws_home":
        session.workspace_dir = os.path.expanduser("~")
        session.conversation_id = None
        await query.answer("🏠 Workspace disetel ke Home directory")
        text = (
            f"✅ <b>Workspace diubah ke Home (~)</b>\n"
            f"📁 <code>{html.escape(session.workspace_dir)}</code>\n"
            f"🔄 Sesi direset untuk workspace ini."
        )
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_workspace_markup(session.workspace_dir))

    elif data == "cb:ws_up":
        parent = os.path.abspath(os.path.join(session.workspace_dir, ".."))
        if os.path.exists(parent) and os.path.isdir(parent):
            session.workspace_dir = parent
            session.conversation_id = None
            await query.answer("⬆️ Naik 1 tingkat folder")
            text = (
                f"✅ <b>Workspace naik 1 tingkat</b>\n"
                f"📁 <code>{html.escape(session.workspace_dir)}</code>\n"
                f"🔄 Sesi direset untuk workspace ini."
            )
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_workspace_markup(session.workspace_dir))
        else:
            await query.answer("⚠️ Tidak dapat naik lebih tinggi.", show_alert=True)

    # 9. Reset Session
    elif data == "cb:reset":
        session.conversation_id = None
        await query.answer("🔄 Sesi percakapan direset!", show_alert=True)
        try:
            await query.message.reply_text("🔄 <b>Sesi baru dimulai!</b> Konteks percakapan sebelumnya telah dibersihkan.", parse_mode=ParseMode.HTML)
        except Exception:
            pass

    # 10. Cancel Task
    elif data == "cb:cancel":
        if session.current_task and not session.current_task.done():
            session.current_task.cancel()
            if session.current_pid:
                kill_process_tree(session.current_pid, signal.SIGTERM)
            await query.answer("🛑 Tugas dibatalkan.", show_alert=True)
            await query.message.reply_text("🛑 <b>Tugas berhasil dibatalkan.</b>", parse_mode=ParseMode.HTML)
        else:
            await query.answer("ℹ️ Tidak ada tugas berjalan.", show_alert=True)

    # 11. Helper Shortcuts
    elif data == "cb:help":
        await query.answer()
        await query.edit_message_text(build_help_text(), parse_mode=ParseMode.HTML, reply_markup=build_main_menu_markup())

    elif data == "cb:ls":
        await query.answer()
        class MockContext:
            args = []
        await ls_handler(query, MockContext())

    elif data == "cb:git":
        await query.answer()
        class MockContext:
            args = []
        await git_handler(query, MockContext())

# ==========================================
# AGY EXECUTION & TASK PIPELINE (CROSS-PLATFORM)
# ==========================================

async def execute_antigravity(session: UserSession, prompt: str) -> dict:
    """Menjalankan agy CLI non-interaktif dengan process group isolation & timeout aman di semua OS."""
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

    if session.mode:
        cmd.extend(["--mode", session.mode])

    cmd.extend(["--print", prompt])

    cwd = session.workspace_dir if os.path.exists(session.workspace_dir) else os.path.expanduser("~")

    logger.info(f"Menjalankan agy di '{cwd}' | Model: {session.model} | Prompt: {prompt[:80]}...")

    # Konfigurasi Subprocess Cross-Platform
    subproc_kwargs = {}
    if IS_WINDOWS:
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            subproc_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        if hasattr(os, "setsid"):
            subproc_kwargs["preexec_fn"] = os.setsid

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        **subproc_kwargs
    )
    session.current_pid = process.pid

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=EXECUTION_TIMEOUT)
    except asyncio.TimeoutError:
        if process.pid:
            kill_process_tree(process.pid, signal.SIGKILL if not IS_WINDOWS else signal.SIGTERM)
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
        
        current_model_tag = session.model or DEFAULT_MODEL or "gemini-3.7-flash"
        footer_badges.append(f"🧠 {current_model_tag}")

        if footer_badges:
            response_text += f"\n\n---\n*({' • '.join(footer_badges)})*"

        await send_formatted_message(update, response_text, attach_keyboard=True)

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
        keyboard = [[InlineKeyboardButton("🛑 Batalkan Proses Sekarang", callback_data="cb:cancel")]]
        await update.message.reply_text(
            "⏳ <b>Sedang memproses tugas sebelumnya...</b>\nSilakan tunggu atau klik tombol di bawah untuk membatalkannya:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
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
        keyboard = [[InlineKeyboardButton("🛑 Batalkan Proses Sekarang", callback_data="cb:cancel")]]
        await update.message.reply_text(
            "⏳ Sedang memproses tugas sebelumnya. Klik tombol untuk membatalkannya:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
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
            f"🎙️ <b>Transkripsi Suara (Gemini):</b>\n<blockquote>{html.escape(transcribed_text)}</blockquote>",
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
        keyboard = [[InlineKeyboardButton("🛑 Batalkan Proses Sekarang", callback_data="cb:cancel")]]
        await update.message.reply_text(
            "⏳ Sedang memproses tugas sebelumnya. Klik tombol untuk membatalkannya:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
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

# ==========================================
# POST-INIT TELEGRAM MENU REGISTRATION
# ==========================================

async def post_init_setup(application):
    """Mendaftarkan menu bot otomatis ke Telegram agar muncul di tombol [Menu]."""
    commands = [
        BotCommand("menu", "Tampilkan Dashboard Menu Utama"),
        BotCommand("status", "Cek RAM, CPU, Disk, Uptime, & Model"),
        BotCommand("model", "Pilih / ganti model Gemini AI"),
        BotCommand("effort", "Atur tingkat penalaran reasoning AI"),
        BotCommand("workspace", "Pindah / cek folder proyek aktif"),
        BotCommand("ls", "Jelajahi file & folder di workspace"),
        BotCommand("git", "Cek status Git repository"),
        BotCommand("sh", "Jalankan quick terminal command"),
        BotCommand("new", "Reset percakapan ke sesi baru"),
        BotCommand("cancel", "Hentikan tugas yang sedang berjalan"),
        BotCommand("whoami", "Cek User ID Telegram & otorisasi"),
        BotCommand("help", "Panduan bantuan penggunaan bot"),
    ]
    try:
        await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        logger.info("Daftar perintah bot berhasil didaftarkan ke Telegram.")
    except Exception as e:
        logger.warning(f"Gagal mendaftarkan commands menu ke Telegram: {e}")

# ==========================================
# MAIN ENTRYPOINT
# ==========================================

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
            print("Jalankan './init.sh' atau 'init.bat' untuk inisiasi kredensial.")
            sys.exit(1)

    if not os.path.exists(AGY_PATH) and not shutil.which("agy"):
        logger.error(f"Binary 'agy' tidak ditemukan di path: {AGY_PATH}")
        print(f"❌ Error: Binary 'agy' tidak ditemukan di: {AGY_PATH}")
        print("Pastikan Antigravity CLI telah terinstal di sistem operasi Anda.")
        sys.exit(1)

    if not ALLOWED_USER_IDS:
        print("⚠️ PERINGATAN: ALLOWED_TELEGRAM_USER_ID belum diisi di .env.")
        print("Bot akan menolak semua pesan hingga Anda menambahkan ID Anda.")

    logger.info(f"Memulai Antigravity Telegram Bridge di {platform.system()} ({platform.machine()})...")
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init_setup)
        .build()
    )

    # Daftarkan Handlers Perintah
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("menu", menu_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("reset", reset_handler))
    application.add_handler(CommandHandler("new", reset_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("workspace", workspace_handler))
    application.add_handler(CommandHandler("model", model_handler))
    application.add_handler(CommandHandler("effort", effort_handler))
    application.add_handler(CommandHandler("mode", mode_handler))
    application.add_handler(CommandHandler("ls", ls_handler))
    application.add_handler(CommandHandler("git", git_handler))
    application.add_handler(CommandHandler("sh", sh_handler))
    application.add_handler(CommandHandler("exec", sh_handler))
    application.add_handler(CommandHandler("whoami", whoami_handler))
    application.add_handler(CommandHandler("cancel", cancel_handler))

    # Daftarkan Callback Query Handler (Inline Keyboards)
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    # Handler Pesan Teks
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Handler Pesan Suara & File Audio
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_audio_handler))

    # Handler Foto, Screenshot, dan File Gambar Dokumen
    application.add_handler(MessageHandler(filters.PHOTO, photo_image_handler))
    application.add_handler(MessageHandler(filters.Document.IMAGE, photo_image_handler))

    print(f"🤖 Antigravity Telegram Bridge AKTIF (Cross-Platform Edition)")
    print(f"🖥️ Sistem Operasi: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"⚙️ Binary Path: {AGY_PATH}")
    print(f"🧠 Default Model: {DEFAULT_MODEL} (Effort: {DEFAULT_EFFORT})")
    print(f"📂 Default Workspace: {DEFAULT_WORKSPACE}")
    print(f"🔑 Allowed User IDs: {list(ALLOWED_USER_IDS) if ALLOWED_USER_IDS else 'Belum ada'}")

    application.run_polling()

if __name__ == "__main__":
    main()
