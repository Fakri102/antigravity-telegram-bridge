# 🚀 Antigravity Telegram Bridge

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Multimodal](https://img.shields.io/badge/multimodal-Text%20%7C%20Voice%20%7C%20Images-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

> Kontrol dan berikan instruksi coding ke **Google Antigravity Desktop / CLI (`agy`)** langsung dari aplikasi **Telegram** menggunakan **Teks**, **Pesan Suara (Voice Note)**, maupun **Gambar / Screenshot**.

---

## 📖 Daftar Isi

- [Tentang Proyek](#-tentang-proyek)
- [Arsitektur](#-arsitektur)
- [Fitur Multimodal Lengkap](#-fitur-multimodal-lengkap)
- [Prasyarat](#-prasyarat)
- [Panduan Instalasi & Penggunaan](#-panduan-instalasi--penggunaan)
  - [1. Clone Repository](#1-clone-repository)
  - [2. Siapkan Virtual Environment & Dependencies](#2-siapkan-virtual-environment--dependencies)
  - [3. Dapatkan Token Telegram & User ID](#3-dapatkan-token-telegram--user-id)
  - [4. Konfigurasi File `.env`](#4-konfigurasi-file-env)
- [Menjalankan Bot](#-menjalankan-bot)
  - [Mode Interaktif](#opsi-a-menjalankan-di-terminal-interaktif)
  - [Mode Background (Daemon Service)](#opsi-b-menjalankan-di-latar-belakang-background-service)
- [Daftar Perintah Telegram](#-daftar-perintah-telegram)
- [Contoh Penggunaan Nyata](#-contoh-penggunaan-nyata)
- [Keamanan (Security Best Practices)](#-keamanan-security-best-practices)
- [Troubleshooting](#-troubleshooting)
- [Lisensi](#-lisensi)

---

## 🌟 Tentang Proyek

**Antigravity Telegram Bridge** adalah aplikasi perantara (*bridge daemon*) berbasis Python yang menghubungkan Telegram Bot API dengan **Google Antigravity CLI (`agy`)**.

Dengan aplikasi ini, Anda dapat menjalankan tugas AI agentik di komputer/desktop lokal Anda secara remote melalui Telegram:
- Membuat, mengedit, atau meninjau kode proyek.
- Mengirimkan rekaman suara (voice note) saat di perjalanan untuk menjalankan tugas coding.
- Mengirimkan screenshot desain UI atau error log untuk langsung diperbaiki oleh agent.
- Mengontrol folder proyek aktif secara dinamis.
- Mengganti model AI atau tingkat penalaran (*reasoning effort*) kapan saja.

---

## 🏗️ Arsitektur

```
┌──────────────────────────────────────────────┐
│          Telegram App (HP / Laptop)          │
│   [Teks]  •  [Pesan Suara]  •  [Gambar/Foto] │
└──────────────────────────────────────────────┘
                       ▲
                       │ (Telegram Bot API)
                       ▼
┌──────────────────────────────────────────────┐
│         Antigravity Telegram Bridge          │
│   • Speech Recognition (Audio to Text)       │
│   • Image Manager (Auto Save to Workspace)   │
│   • Session & Workspace Controller           │
└──────────────────────────────────────────────┘
                       ▲
                       │ (Subprocess / JSON IPC)
                       ▼
┌──────────────────────────────────────────────┐
│        Google Antigravity CLI (`agy`)        │
│          & Workspace Proyek Lokal            │
└──────────────────────────────────────────────┘
```

---

## ✨ Fitur Multimodal Lengkap

- 💬 **Input Teks**: Kirim prompt, instruksi coding, atau pertanyaan biasa.
- 🎙️ **Input Suara (Voice Note & Audio)**:
  - Kirim Voice Note langsung dari Telegram.
  - Bot mentranskripsi suara (Bahasa Indonesia & English) dan meneruskannya ke agent Antigravity.
- 🖼️ **Input Gambar (Foto & Screenshot)**:
  - Kirim screenshot UI/desain, diagram arsitektur, atau tangkapan layar error.
  - Bot otomatis menyimpan gambar ke folder `uploads/` di workspace aktif dan memerintahkan agent untuk menganalisisnya.
- 🧠 **Direct Antigravity Engine**: Langsung memanfaatkan `agy` CLI lokal yang sudah terautentikasi dan memiliki akses ke seluruh tool, skill, dan plugin Antigravity Anda.
- 💬 **Persistent Multi-turn Conversation**: Mempertahankan memori percakapan (`conversation_id`) antar turn secara otomatis.
- 🔒 **Sistem Keamanan Whitelist User ID**: Hanya akun Telegram yang Anda daftarkan di `.env` yang dapat memberikan instruksi ke komputer.
- 📂 **Manajemen Workspace Dinamis**: Pindah folder kerja proyek kapan saja langsung dari chat menggunakan perintah `/workspace <path>`.
- ⚡ **Pengaturan Model & Reasoning Effort**: Ubah model atau tingkat kedalaman berpikir AI via `/model` dan `/effort`.
- ⏳ **Status Typing & Auto-Chunking**: Menampilkan animasi *typing* di Telegram selama agent bekerja, serta otomatis memecah pesan panjang jika melebihi batas limit 4096 karakter Telegram.
- 🛠️ **Service Manager Script**: Dilengkapi `service.sh` untuk memudahkan proses *start, stop, restart, status,* dan *monitoring log* di background.

---

## 📋 Prasyarat

1. **Python 3.10** atau versi lebih baru.
2. **FFmpeg** (untuk pemrosesan audio/voice note).
   - Di macOS: `brew install ffmpeg`
   - Di Ubuntu/Debian: `sudo apt install ffmpeg`
3. **Google Antigravity CLI (`agy`)** sudah terinstal dan terautentikasi di komputer Anda.
4. Akun **Telegram**.

---

## 🚀 Panduan Instalasi & Penggunaan

### 1. Clone Repository
```bash
git clone https://github.com/username-anda/antigravity-telegram-bridge.git
cd antigravity-telegram-bridge
```

### 2. Siapkan Virtual Environment & Dependencies
```bash
# Buat virtual environment
python3 -m venv venv

# Aktifkan virtual environment
source venv/bin/activate

# Instal paket yang dibutuhkan
pip install -r requirements.txt
```

### 3. Dapatkan Token Telegram & User ID

1. **Buat Bot Telegram**:
   - Buka aplikasi Telegram, cari **[@BotFather](https://t.me/botfather)**.
   - Ketik `/newbot`, lalu ikuti panduan untuk menentukan nama dan username bot.
   - Simpan **API Token** yang diberikan.

2. **Dapatkan User ID Anda**:
   - Cari **[@userinfobot](https://t.me/userinfobot)** di Telegram.
   - Kirim pesan apa saja, bot akan membalas dengan **Id** angka Anda (contoh: `123456789`).

### 4. Konfigurasi File `.env`
Salin template konfigurasi:
```bash
cp .env.example .env
```

Buka file `.env` dan masukkan data Anda:
```env
# Token Bot Telegram dari @BotFather
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuvWXyz

# ID Telegram Anda (hanya ID ini yang diizinkan)
ALLOWED_TELEGRAM_USER_ID=123456789

# Direktori default workspace proyek Anda
ANTIGRAVITY_WORKSPACE=/Users/username/Code

# Path binary agy (default: ~/.local/bin/agy)
AGY_BINARY_PATH=/Users/username/.local/bin/agy

# Opsional: Gemini API Key untuk transkripsi audio ultra-akurat
GEMINI_API_KEY=
```

---

## 🏃 Menjalankan Bot

Pastikan script memiliki izin eksekusi:
```bash
chmod +x start.sh service.sh bot.py
```

### Opsi A: Menjalankan di Terminal (Interaktif)
```bash
./start.sh
```

### Opsi B: Menjalankan di Latar Belakang (Background Service)
```bash
# 1. Menjalankan bot di background
./service.sh start

# 2. Mengecek status bot
./service.sh status

# 3. Melihat log aktivitas secara real-time
./service.sh logs

# 4. Merestart bot
./service.sh restart

# 5. Menghentikan bot
./service.sh stop
```

---

## 📱 Daftar Perintah Telegram

| Perintah | Fungsi | Contoh Penggunaan |
| :--- | :--- | :--- |
| **Pesan Teks** | Mengirim prompt / tugas coding ke Antigravity Agent | *"Buatkan skrip backup DB dengan Python"* |
| **Voice Note (VN)** | Merekam suara, otomatis ditranskripsikan dan dikerjakan | *(Kirim rekaman suara via Telegram)* |
| **Kirim Gambar / Foto** | Mengunggah screenshot UI / error beserta caption | *(Kirim gambar dengan caption instruksi)* |
| `/start` / `/help` | Menampilkan menu bantuan dan status bot | `/start` |
| `/new` / `/reset` | Mereset memori percakapan ke sesi baru | `/new` |
| `/status` | Cek workspace aktif, model, audio/image status, dll. | `/status` |
| `/workspace <path>` | Menampilkan atau mengubah folder kerja proyek | `/workspace /Users/user/Code/my-app` |
| `/model <nama>` | Mengubah model AI atau kembali ke default | `/model gemini-2.5-pro` atau `/model default` |
| `/effort <level>` | Mengatur penalaran AI (`low`, `medium`, `high`, `default`) | `/effort high` |
| `/cancel` | Membatalkan tugas yang sedang berlangsung | `/cancel` |

---

## 💡 Contoh Penggunaan Nyata

1. **Membuat UI dari Screenshot Gambar:**
   > Unggah screenshot halaman web dengan caption: *"Buatkan halaman HTML dan Tailwind CSS yang persis seperti desain pada gambar ini di file `landing.html`"*

2. **Memperbaiki Error dari Screenshot Terminal:**
   > Unggah screenshot pesan error terminal dengan caption: *"Perbaiki bug ini di kode proyek saya"*

3. **Memberikan Perintah Melalui Rekaman Suara:**
   > Kirim Voice Note: *"Tolong tambahkan validasi email dan password pada file auth controller"*

---

## 🛡️ Keamanan (Security Best Practices)

> [!CAUTION]
> **JANGAN PERNAH MENGUNGGAH FILE `.env` KE GITHUB!**  
> File `.gitignore` pada repositori ini sudah dikonfigurasi untuk secara otomatis mengabaikan file `.env`.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE). Bebas digunakan dan dikembangkan kembali.
