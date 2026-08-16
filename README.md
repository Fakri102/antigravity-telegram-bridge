# 🚀 Antigravity Telegram Bridge

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

> Kontrol dan berikan instruksi coding ke **Google Antigravity Desktop / CLI (`agy`)** langsung dari aplikasi **Telegram** di smartphone atau perangkat lain di mana pun Anda berada.

---

## 📖 Daftar Isi

- [Tentang Proyek](#-tentang-proyek)
- [Arsitektur](#-arsitektur)
- [Fitur Utama](#-fitur-utama)
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
- Menjalankan analisis dan debugging pada workspace lokal.
- Mengontrol folder proyek aktif secara dinamis.
- Mengganti model AI atau tingkat penalaran (*reasoning effort*) kapan saja.

---

## 🏗️ Arsitektur

```
┌────────────────────────────────┐
│   Telegram App (HP / Laptop)   │
└────────────────────────────────┘
                ▲
                │ (Telegram Bot API)
                ▼
┌────────────────────────────────┐
│  Antigravity Telegram Bridge   │
│     (Python Script / Bot)      │
└────────────────────────────────┘
                ▲
                │ (Subprocess / JSON IPC)
                ▼
┌────────────────────────────────┐
│ Google Antigravity CLI (`agy`) │
│    & Workspace Proyek Lokal    │
└────────────────────────────────┘
```

---

## ✨ Fitur Utama

- 🧠 **Direct Antigravity Engine**: Langsung memanfaatkan `agy` CLI lokal yang sudah terautentikasi dan memiliki akses ke seluruh tool, skill, dan plugin Antigravity Anda.
- 💬 **Persistent Multi-turn Conversation**: Mempertahankan memori percakapan (`conversation_id`) antar turn secara otomatis seperti layaknya chatting di aplikasi desktop.
- 🔒 **Sistem Keamanan Whitelist User ID**: Hanya akun Telegram yang Anda daftarkan di `.env` yang dapat memberikan instruksi ke komputer.
- 📂 **Manajemen Workspace Dinamis**: Pindah folder kerja proyek kapan saja langsung dari chat menggunakan perintah `/workspace <path>`.
- ⚡ **Pengaturan Model & Reasoning Effort**: Ubah model atau tingkat kedalaman berpikir AI via `/model` dan `/effort`.
- ⏳ **Status Typing & Auto-Chunking**: Menampilkan animasi *typing* di Telegram selama agent bekerja, serta otomatis memecah pesan panjang jika melebihi batas limit 4096 karakter Telegram.
- 🛠️ **Service Manager Script**: Dilengkapi `service.sh` untuk memudahkan proses *start, stop, restart, status,* dan *monitoring log* di background.

---

## 📋 Prasyarat

1. **Python 3.10** atau versi lebih baru.
2. **Google Antigravity CLI (`agy`)** sudah terinstal dan terautentikasi di komputer Anda.
   *(Cek via terminal: `agy --version`)*.
3. Akun **Telegram**.

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
# Di macOS / Linux:
source venv/bin/activate
# Di Windows:
# .\venv\Scripts\activate

# Instal paket yang dibutuhkan
pip install -r requirements.txt
```

### 3. Dapatkan Token Telegram & User ID

1. **Buat Bot Telegram**:
   - Buka aplikasi Telegram, cari **[@BotFather](https://t.me/botfather)**.
   - Ketik `/newbot`, lalu ikuti panduan untuk menentukan nama dan username bot.
   - Simpan **API Token** yang diberikan (contoh: `123456789:ABCdefGhIJK...`).

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
```

---

## 🏃 Menjalankan Bot

Pastikan script memiliki izin eksekusi (*executable*):
```bash
chmod +x start.sh service.sh bot.py
```

### Opsi A: Menjalankan di Terminal (Interaktif)
Cocok untuk pengujian awal dan melihat log secara langsung di layar:
```bash
./start.sh
```

### Opsi B: Menjalankan di Latar Belakang (Background Service)
Cocok agar bot tetap aktif bekerja meskipun aplikasi Terminal Anda ditutup:

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
| **Pesan Biasa** | Mengirimkan prompt / tugas coding ke Antigravity Agent | *"Buatkan skrip backup DB dengan Python"* |
| `/start` / `/help` | Menampilkan menu bantuan dan status bot | `/start` |
| `/new` / `/reset` | Mereset memori percakapan ke sesi baru | `/new` |
| `/status` | Cek workspace aktif, model, dan conversation ID | `/status` |
| `/workspace <path>` | Menampilkan atau mengubah folder kerja proyek | `/workspace /Users/user/Code/my-app` |
| `/model <nama>` | Mengubah model AI atau kembali ke default | `/model gemini-2.5-pro` atau `/model default` |
| `/effort <level>` | Mengatur penalaran AI (`low`, `medium`, `high`, `default`) | `/effort high` |
| `/cancel` | Membatalkan tugas yang sedang berlangsung | `/cancel` |

---

## 💡 Contoh Penggunaan Nyata

1. **Memeriksa & Memodifikasi File Proyek:**
   > *"Tolong cek file `src/app.py`, apakah ada potensi error pada penanganan error database?"*

2. **Membuat Fitur Baru:**
   > *"Buatkan endpoint baru di Express.js untuk autentikasi JWT di file `routes/auth.js`"*

3. **Pindah Proyek:**
   > Kirim: `/workspace /home/username/Code/project-b`  
   > Lalu kirim: *"Jelaskan arsitektur folder di proyek ini"*

---

## 🛡️ Keamanan (Security Best Practices)

> [!CAUTION]
> **JANGAN PERNAH MENGUNGGAH FILE `.env` KE GITHUB!**  
> File `.env` berisi Token Bot Telegram dan User ID pribadi Anda. File `.gitignore` pada repositori ini sudah dikonfigurasi untuk secara otomatis mengabaikan file `.env`.

- **Whitelist User ID**: Pastikan `ALLOWED_TELEGRAM_USER_ID` diisi dengan benar agar orang lain di Telegram tidak dapat mengeksekusi perintah di komputer Anda.
- **Autentikasi Lokal**: Program ini berjalan langsung di komputer Anda secara lokal dan hanya berkomunikasi melalui channel bot Telegram resmi.

---

## ❓ Troubleshooting

1. **Bot tidak merespons di Telegram?**
   - Pastikan bot sedang berjalan: `./service.sh status`
   - Cek log error: `./service.sh logs`
   - Pastikan User ID Telegram Anda sesuai dengan `ALLOWED_TELEGRAM_USER_ID` di `.env`.

2. **Error `Binary 'agy' tidak ditemukan`?**
   - Pastikan Antigravity CLI sudah terpasang. Jalankan `which agy` di terminal Anda.
   - Sesuaikan path `AGY_BINARY_PATH` di `.env` sesuai hasil dari `which agy`.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE). Bebas digunakan, dimodifikasi, dan dikembangkan kembali.
