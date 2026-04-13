# WhatsApp Bot Fix WA Pro & API

Sistem otomatis permohonan banding WhatsApp terpadu.

## Struktur Project
- `bot_fixwa_pro.py`: Bot Telegram utama (Python).
- `wa_api/`: Server Gateway WhatsApp (Node.js).
- `run.py`: Script launcher terpadu.

## Cara Menjalankan
Cukup jalankan perintah ini untuk memulai kedua sistem sekaligus:
```bash
python run.py
```

## Persyaratan
- Python 3.10+
- Node.js 18+
- Library Python: `python-telegram-bot`, `requests`, `httpx`
- Library Node.js: Terinstal di folder `wa_api` (`npm install`)
