# 🚀 Antigravity Telegram Bridge (Production Edition)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Multimodal](https://img.shields.io/badge/multimodal-Text%20%7C%20Voice%20%7C%20Images-brightgreen.svg)]()
[![Production Ready](https://img.shields.io/badge/systemd-24%2F7%20Daemon-orange.svg)]()
[![Platform](https://img.shields.io/badge/platform-Linux%20VPS%20%7C%20macOS%20%7C%20Docker-lightgrey.svg)]()

> Jalankan **Google Antigravity CLI (`agy`)** 24/7 di Server VPS Linux atau Komputer Lokal Anda dan berikan instruksi coding secara remote via **Telegram** (Teks, Voice Note, Screenshot Desain, atau Error Log).

---

## 📖 Daftar Isi

- [Arsitektur](#-arsitektur)
- [Fitur Utama](#-fitur-utama)
- [Panduan Deployment ke Server VPS (Production 24/7)](#-panduan-deployment-ke-server-vps-production-247)
  - [Metode 1: Otomatis via Systemd (Disarankan)](#metode-1-otomatis-via-systemd-disarankan-untuk-vps)
  - [Metode 2: Docker & Docker Compose](#metode-2-docker--docker-compose)
  - [Metode 3: Lokal di macOS / Laptop](#metode-3-menjalankan-di-macos--laptop-lokal)
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

#### 3. Jalankan Script Setup Otomatis
Script ini akan menginstal Python, FFmpeg, dependensi virtual environment, dan Antigravity CLI secara otomatis:
```bash
chmod +x setup_vps.sh install_systemd.sh
./setup_vps.sh
```

#### 4. Edit File `.env`
```bash
nano .env
```
*(Masukkan `TELEGRAM_BOT_TOKEN`, `ALLOWED_TELEGRAM_USER_ID`, dan `ANTIGRAVITY_WORKSPACE`)*.

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

## ⚙️ Konfigurasi `.env`

| Variabel | Wajib | Keterangan |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | **Ya** | Token Bot dari [@BotFather](https://t.me/botfather) |
| `ALLOWED_TELEGRAM_USER_ID` | **Ya** | ID Akun Telegram Anda dari [@userinfobot](https://t.me/userinfobot) |
| `ANTIGRAVITY_WORKSPACE` | Tidak | Folder kerja awal (misal: `/var/www` atau `/home/user/Code`) |
| `AGY_BINARY_PATH` | Tidak | Path ke binary `agy` (otomatis dideteksi jika dikosongkan) |
| `ANTIGRAVITY_TIMEOUT` | Tidak | Batas waktu tunggu eksekusi dalam detik (default: `300`) |
| `GEMINI_API_KEY` | Tidak | Opsional: API key untuk transkripsi audio tingkat lanjut |

---

## 📱 Daftar Perintah Telegram

| Perintah | Deskripsi |
| :--- | :--- |
| **Kirim Teks** | Mengirimkan tugas coding / instruksi terminal |
| **Voice Note (VN)** | Merekam suara, otomatis ditranskripsikan ke perintah coding |
| **Kirim Foto/Screenshot** | Mengirim gambar desain UI atau error log beserta caption |
| `/status` | Cek status server, Disk, Uptime, Workspace, dan model |
| `/workspace <path>` | Berpindah folder kerja proyek secara dinamis |
| `/new` / `/reset` | Memulai sesi baru (reset konteks memori percakapan) |
| `/model <nama>` | Ganti model AI (contoh: `/model gemini-2.5-pro` atau `/model default`) |
| `/effort <level>` | Atur tingkat penalaran (`low`, `medium`, `high`, `default`) |
| `/cancel` | Menghentikan paksa proses yang sedang berlangsung |
| `/help` | Menampilkan menu bantuan lengkap |

---

## 📊 Monitoring & Healthcheck Server

Cukup ketik `/status` di chat Telegram Anda dari HP, dan bot akan membalas dengan metrik server terkini:
* 🖥️ **Host OS & Arsitektur**
* ⏱️ **Bot Uptime**
* 💾 **Kapasitas & Penggunaan Disk Server**
* 📂 **Workspace Aktif**
* 🧠 **Model & Reasoning Effort**

---

## 🛡️ Keamanan (Security Best Practices)

- **Strict User Whitelist**: Hanya User ID yang tertera di `.env` yang dapat mengakses server.
- **Git Ignore**: File `.gitignore` mencegah file rahasia `.env`, file log, dan folder virtual environment ter-upload ke repositori publik.
- **Process Isolation**: Setiap proses agy berjalan di process group terisolasi dan dilindungi batas waktu (*timeout guard*).

---

## 📄 Lisensi

Didistribusikan di bawah [MIT License](LICENSE). Bebas digunakan dan dimodifikasi untuk kebutuhan personal maupun komersial.
