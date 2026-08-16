# 🚀 Antigravity Telegram Bridge (Production Edition)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Multimodal](https://img.shields.io/badge/multimodal-Text%20%7C%20Voice%20%7C%20Images-brightgreen.svg)]()
[![Production Ready](https://img.shields.io/badge/systemd-24%2F7%20Daemon-orange.svg)]()
[![Platform](https://img.shields.io/badge/platform-Linux%20VPS%20%7C%20macOS%20%7C%20Windows%20%7C%20Docker-lightgrey.svg)]()

> Jalankan **Google Antigravity CLI (`agy`)** 24/7 di Linux VPS, macOS, atau Windows PC dan berikan instruksi coding secara remote via **Telegram** (Teks, Voice Note, Screenshot Desain, atau Error Log).

---

## 📖 Daftar Isi

- [Arsitektur](#-arsitektur)
- [Fitur Utama](#-fitur-utama)
- [Panduan Instalasi & Deployment](#-panduan-instalasi--deployment)
  - [Metode 1: Linux VPS via Systemd (Production 24/7)](#metode-1-otomatis-via-systemd-disarankan-untuk-vps)
  - [Metode 2: Docker & Docker Compose](#metode-2-docker--docker-compose)
  - [Metode 3: macOS (Apple Silicon / Intel)](#metode-3-menjalankan-di-macos--laptop-lokal)
  - [Metode 4: Windows (10 / 11 / Server)](#metode-4-menjalankan-di-windows-10--11)
- [Konfigurasi `.env`](#-%EF%B8%8F-konfigurasi-env)
- [Daftar Perintah Telegram](#-daftar-perintah-telegram)
- [Monitoring & Healthcheck Server](#-monitoring--healthcheck-server)
- [Keamanan (Security Best Practices)](#-keamanan-security-best-practices)
- [Lisensi](#-lisensi)

---

## 🏗️ Arsitektur

```
┌────────────────────────────────────────────────────────────┐
│                Telegram App (HP / Laptop)                  │
│       [Teks]   •   [Pesan Suara / VN]   •   [Gambar]       │
└────────────────────────────────────────────────────────────┘
                              ▲
                              │ (Telegram Bot API)
                              ▼
┌────────────────────────────────────────────────────────────┐
│            Linux VPS Server (24/7 Background)              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │      Systemd Service: antigravity-telegram.service   │  │
│  │   • Speech Recognition Engine (Indonesian/English)   │  │
│  │   • Telegram HTML Formatting Engine                  │  │
│  │   • Process Group & Timeout Manager (300s guard)     │  │
│  │   • Dynamic Workspace Controller                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                             ▲                              │
│                             │ (JSON IPC / Isolated Subproc)│
│                             ▼                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Google Antigravity Engine (`agy`)           │  │
│  │        & Workspace Server (/var/www / ~/Code)        │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

---

## ✨ Fitur Utama

- 🌐 **Production-Ready 24/7 VPS Daemon**: Terintegrasi penuh dengan `systemd` (auto-restart saat crash, boot on server startup, log rotation via journalctl).
- 🎙️ **Voice Note / Audio Transkripsi**: Rekam suara via Telegram dalam Bahasa Indonesia atau Inggris, otomatis dikonversi menjadi prompt coding.
- 🖼️ **Screenshot & Image Input**: Unggah gambar desain UI atau tangkapan layar error, otomatis disimpan ke folder `uploads/` dan dianalisis oleh agent.
- 🎨 **Telegram HTML Formatting Engine**: Menampilkan blok kode rapi ber-syntax highlighting dengan tombol copy, quote box, dan pemecah kode pintar (*smart chunker*).
- ⏱️ **Timeout & Process Group Isolation**: Dilengkapi batas waktu eksekusi aman (*execution timeout*) dan pembatalan tugas bersih via `/cancel`.
- 📊 **Server Health Metrics**: Perintah `/status` langsung menampilkan Uptime bot, kapasitas Disk, OS, dan status sesi.
- 🔒 **Security Whitelist**: Hanya akun Telegram pemilik (`ALLOWED_TELEGRAM_USER_ID`) yang dapat memberikan instruksi ke server.

---

## 🚀 Panduan Deployment ke Server VPS (Production 24/7)

### Metode 1: Otomatis via Systemd (Disarankan untuk VPS)

#### 1. Masuk ke Server VPS Anda
```bash
ssh user@ip-server-vps-anda
```

#### 2. Clone Repositori
```bash
git clone https://github.com/USERNAME/antigravity-telegram-bridge.git
cd antigravity-telegram-bridge
```

#### 3. Inisiasi & Konfigurasi Kredensial (Interaktif)
Jalankan setup wizard untuk mengatur Token Bot Telegram & User ID secara interaktif dan aman:
```bash
chmod +x init.sh setup_vps.sh start.sh
./init.sh
```
> **Atau konfigurasi manual:** salin file template dengan `cp .env.example .env` lalu edit dengan `nano .env`.

#### 4. Jalankan Setup Sistem & Dependensi VPS
Script ini akan menginstal dependensi OS (Python, FFmpeg) dan virtual environment secara otomatis:
```bash
./setup_vps.sh
```

#### 5. Daftarkan Service Systemd 24/7
```bash
sudo ./install_systemd.sh
```

#### 🛠️ Perintah Kontrol Service di VPS:
```bash
# Cek status service
sudo systemctl status antigravity-telegram

# Pantau live log realtime
sudo journalctl -u antigravity-telegram -f

# Restart service
sudo systemctl restart antigravity-telegram

# Stop service
sudo systemctl stop antigravity-telegram
```

---

### Metode 2: Docker & Docker Compose

Jika Anda lebih memilih container:
```bash
# 1. Clone repo & isi .env
git clone https://github.com/USERNAME/antigravity-telegram-bridge.git
cd antigravity-telegram-bridge
cp .env.example .env && nano .env

# 2. Build dan jalankan container
docker compose up -d --build

# 3. Lihat log container
docker compose logs -f
```

---

### Metode 3: Menjalankan di macOS / Laptop Lokal

```bash
cd antigravity-telegram-bridge

# Jalankan di background
./service.sh start

# Cek status
./service.sh status

# Hentikan
./service.sh stop
```

---

### Metode 4: Menjalankan di Windows (10 / 11 / Server)

#### 1. Buka PowerShell atau Command Prompt (CMD)
```powershell
git clone https://github.com/USERNAME/antigravity-telegram-bridge.git
cd antigravity-telegram-bridge
```

#### 2. Jalankan Setup 1-Klik Otomatis
Cukup klik ganda file `setup_windows.bat` di File Explorer, atau jalankan via terminal:
```cmd
setup_windows.bat
```
*Skrip ini akan membuat Python venv, menginstal dependensi, dan membuka setup wizard untuk mengisi token Telegram Anda.*

#### 3. Menjalankan Bot di Windows
```cmd
start.bat
```

---

## ⚙️ Konfigurasi `.env`

| Variabel | Wajib | Keterangan |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | **Ya** | Token Bot dari [@BotFather](https://t.me/botfather) |
| `ALLOWED_TELEGRAM_USER_ID` | **Ya** | ID Akun Telegram Anda dari [@userinfobot](https://t.me/userinfobot) |
| `ANTIGRAVITY_MODEL` | Tidak | Model Gemini default (default: `gemini-3.7-flash`, opsi: `gemini-3.1-pro`, `gemini-3.6-flash`) |
| `ANTIGRAVITY_EFFORT` | Tidak | Reasoning Effort (`high`, `medium`, `low` - default: `high`) |
| `ANTIGRAVITY_WORKSPACE` | Tidak | Folder kerja awal (misal: `/var/www` atau `/home/user/Code`) |
| `AGY_BINARY_PATH` | Tidak | Path ke binary `agy` (otomatis dideteksi jika dikosongkan) |
| `ANTIGRAVITY_TIMEOUT` | Tidak | Batas waktu tunggu eksekusi dalam detik (default: `300`) |
| `GEMINI_API_KEY` | Tidak | Opsional: API key untuk transkripsi audio tingkat lanjut |

---

## 📱 Daftar Perintah Telegram

| Perintah | Deskripsi |
| :--- | :--- |
| **Kirim Teks** | Mengirimkan tugas coding / instruksi terminal / review code |
| **Voice Note (VN)** | Merekam suara, otomatis ditranskripsikan ke perintah coding via Gemini Multimodal |
| **Kirim Foto/Screenshot** | Mengirim gambar desain UI atau error log beserta caption untuk dianalisis |
| `/menu` / `/start` | Membuka **Dashboard Interaktif** lengkap dengan tombol Inline Keyboard |
| `/status` | Cek status server, RAM Meter, CPU, Disk, Uptime, Workspace, dan model aktif |
| `/model [nama]` | Buka tombol pemilih model atau ganti langsung (contoh: `/model gemini-3.7-flash`) |
| `/effort [level]` | Buka tombol pengatur penalaran reasoning (`high`, `medium`, `low`, `default`) |
| `/workspace [path]` | Berpindah folder kerja proyek secara dinamis atau navigasi via tombol |
| `/ls [subfolder]` | File & folder browser interaktif di workspace dengan icon & ukuran file |
| `/git` | Cek branch aktif, commit terakhir, dan status file yang dimodifikasi |
| `/sh <command>` | Menjalankan perintah shell / terminal cepat langsung di workspace |
| `/mode [plan\|accept-edits]` | Mengatur mode eksekusi Antigravity agent (planning / auto-accept) |
| `/whoami` | Menampilkan User ID Telegram, Nama, Username, dan status otorisasi |
| `/new` / `/reset` | Memulai sesi baru (membersihkan memori percakapan) |
| `/cancel` | Menghentikan paksa proses yang sedang berlangsung seketika |
| `/help` | Menampilkan buku panduan perintah lengkap |

---

## 📊 Monitoring & Healthcheck Server

Cukup ketik `/status` di chat Telegram Anda dari HP, dan bot akan membalas dengan metrik visual server:
* 🖥️ **Host OS & Arsitektur Mesin**
* ⏱️ **Bot Uptime**
* 📈 **Real-Time CPU Usage (%)**
* 🧠 **RAM Server Meter** (Visual Progress Bar `[████░░░░░░]`)
* 💾 **Kapasitas Disk Storage** (Visual Progress Bar `[███░░░░░░░]`)
* 📂 **Workspace Aktif**
* 🧠 **Model Gemini & Reasoning Effort**
* 💬 **ID Sesi Percakapan Aktif**

---

## 🛡️ Keamanan (Security Best Practices)

- **Strict User Whitelist**: Hanya User ID yang tertera di `.env` yang dapat mengakses server.
- **Git Ignore**: File `.gitignore` mencegah file rahasia `.env`, file log, dan folder virtual environment ter-upload ke repositori publik.
- **Process Isolation**: Setiap proses agy berjalan di process group terisolasi dan dilindungi batas waktu (*timeout guard*).

---

## 📄 Lisensi

Didistribusikan di bawah [MIT License](LICENSE). Bebas digunakan dan dimodifikasi untuk kebutuhan personal maupun komersial.
