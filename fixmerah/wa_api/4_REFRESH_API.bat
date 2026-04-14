@echo off
title REFRESH / RIFLES API WHATSAPP
echo === PROSES REFRESH TOTAL API (RIFLES) ===
echo.
echo 1. Menghapus folder node_modules...
if exist "node_modules" rmdir /s /q "node_modules"
echo.
echo 2. Menghapus package-lock.json...
if exist "package-lock.json" del /f /q "package-lock.json"
echo.
echo 3. Menginstall ulang semua module (Ini butuh waktu)...
call npm install express qrcode-terminal @whiskeysockets/baileys pino
call npm install github:pedroslopez/whatsapp-web.js --force
echo.
echo === REFRESH SELESAI ===
echo Silakan jalankan '2_JALANKAN_API.bat' sekarang.
echo.
pause
