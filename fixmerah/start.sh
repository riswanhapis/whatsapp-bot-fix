#!/bin/bash

# Jalankan API WhatsApp di folder wa_api
echo "Starting WhatsApp API..."
cd wa_api && pm2 start server.js --name "wa-api" && cd ..

# Jalankan Bot Telegram
echo "Starting Telegram Bot..."
pm2-runtime start bot_fixwa_pro.py --name "telegram-bot" --interpreter python3
