@echo off
title MEMBERSIHKAN SESI WHATSAPP API
echo SEDANG MEMATIKAN SEMUA BROWSER WHATSAPP YANG NYANGKUT...
taskkill /F /IM chrome.exe /FI "WINDOWTITLE eq about:blank" /T 2>nul
echo.
echo SEDANG MENGHAPUS SEMUA SESI BAILEYS YANG TERSIMPAN...
for /d %%i in (auth_baileys_*) do rmdir /s /q "%%i"
echo.
echo BERHASIL DIBERSIHKAN! 
echo SILAKAN JALANKAN ULANG '2_JALANKAN_API.bat'
pause
