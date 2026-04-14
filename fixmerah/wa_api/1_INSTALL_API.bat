@echo off
title MENGINSTALL API WHATSAPP STABLE
echo MENGINSTALL MODUL WHATSAPP BAILEYS STABLE...
call npm install express qrcode-terminal @whiskeysockets/baileys pino
call npm install github:pedroslopez/whatsapp-web.js --force
echo SELESAI INSTALLASI. SILAKAN TUTUP DAN BUKA FILE '2_JALANKAN_API.bat'
pause
