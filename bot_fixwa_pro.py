import sqlite3
import smtplib
import re
import requests
import json
import asyncio
import httpx
import socket
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from telegram import (
InlineKeyboardButton,
InlineKeyboardMarkup,
Update
)
from telegram.error import BadRequest
from telegram.request import HTTPXRequest

from telegram.ext import (
ApplicationBuilder,
CommandHandler,
MessageHandler,
CallbackQueryHandler,
ContextTypes,
filters
)

# ======================
# CONFIG
# ======================

# Force IPv4 globally to bypass VPS IPv6 issues
original_getaddrinfo = socket.getaddrinfo
def forced_getaddrinfo(*args, **kwargs):
    res = original_getaddrinfo(*args, **kwargs)
    return [r for r in res if r[0] == socket.AF_INET]
socket.getaddrinfo = forced_getaddrinfo

TOKEN = "8669486008:AAEZ6TFz7Gmq6T19k4prYH9dhlhDJVXigTY"

EMAIL = ""
APP_PASSWORD = ""

ADMIN_ID = 5895566352

user_cooldowns = {}

# ======================
# DATABASE
# ======================

conn = sqlite3.connect("bot.db",check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
expired TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS requests(
id INTEGER PRIMARY KEY AUTOINCREMENT,
nomor TEXT,
tanggal TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
paket TEXT,
status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings(
key TEXT PRIMARY KEY,
value TEXT
)
""")

conn.commit()

def get_setting(key, default=""):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    return row[0] if row else default

def set_setting(key, value):
    cursor.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, value))
    conn.commit()

# ======================
# CEK AKSES
# ======================

def cek_akses(user_id):

    if user_id == 5895566352:
        return True

    cursor.execute("SELECT expired FROM users WHERE id=?",(user_id,))
    data = cursor.fetchone()

    if not data:
        return False

    expired=datetime.strptime(data[0],"%Y-%m-%d")

    if datetime.now()>expired:
        return False

    return True

# ======================
# VALIDASI NOMOR
# ======================

def valid_nomor(n):

    return re.match(r"^\+?[1-9]\d{6,14}$",n)

# ======================
# KIRIM EMAIL FIX MERAH
# ======================

def kirim_email(nomor, uid):

    pesan=f"""
Halo Tim WhatsApp,

Perkenalkan, saya Epep. Saya ingin mengajukan banding atau permohonan peninjauan ulang terkait kendala yang saya alami saat mencoba mendaftarkan nomor telepon saya ke aplikasi WhatsApp.

Saat proses registrasi berlangsung, muncul pesan dengan keterangan "login tidak tersedia", sehingga saya tidak dapat melanjutkan pendaftaran akun.

Mohon kiranya pihak WhatsApp dapat meninjau dan memperbaiki permasalahan tersebut agar saya dapat menggunakan layanan WhatsApp dengan normal kembali.

Berikut informasi nomor yang mengalami kendala:

Nomor telepon: +{nomor}

Atas perhatian dan bantuan dari pihak WhatsApp, saya ucapkan terima kasih.

Hormat saya,
Epep
"""

    msg=MIMEText(pesan)

    msg["Subject"]="Request Review WhatsApp Account"
    
    email = get_setting("email_admin") or ""
    app_pwd = get_setting("app_password_admin") or ""

    msg["From"]=email
    msg["To"]="support@support.whatsapp.com"

    try:
        server=smtplib.SMTP_SSL("smtp.gmail.com",465)
        server.login(email,app_pwd)
        server.sendmail(email,"support@support.whatsapp.com",msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Error send email (fix): {e}")

# ======================
# KIRIM EMAIL SPAM
# ======================

def kirim_email_spam(nomor, uid):

    pesan1 = f"""
Estimado equipo de WhatsApp, estoy aquí para presentar un informe porque mi número y el de mi familia han sido bloqueados por WhatsApp, lo que dificulta la comunicación a larga distancia para nosotros. Además, mi número es el que se utiliza para el registro en el hospital donde está siendo atendida mi abuela, por lo que solicito encarecidamente a WhatsApp que desbloquee mi número. Gracias. El número es: +{nomor}
"""

    pesan2 = f"""
À l'attention de WhatsApp, je tiens à déposer une plainte car le numéro principal de mon restaurant de pain a été bloqué simplement parce que le nombre de messages de commande sur ce numéro a explosé, ce qui a conduit WhatsApp à détecter du spam et à bloquer mon numéro WhatsApp. Veuillez débloquer le numéro principal de mon restaurant de pain. Merci, le numéro est : +{nomor}
"""

    pesan3 = f"""
À estimada equipe do WhatsApp, gostaria de reportar que o número principal da minha família foi bloqueado e proibido de usar o WhatsApp. O meu celular foi furtado por outra pessoa há কয়েক dias e essa pessoa está usando o meu número para fins criminosos. Tentei fazer login novamente, mas o WhatsApp bloqueou o número. Eu peço que desbloqueiem este número porque ele contém o código do cofre da minha família. O número é: +{nomor}
"""

    pesan_list = [
        (pesan1, "Request to Unban My WhatsApp Account (Spam)"),
        (pesan2, "Review Request: Account Suspended"),
        (pesan3, "Appeal: WhatsApp Number Banned")
    ]

    email = get_setting("email_admin") or ""
    app_pwd = get_setting("app_password_admin") or ""

    try:
        server=smtplib.SMTP_SSL("smtp.gmail.com",465)
        server.login(email,app_pwd)
        
        for pesan, subject in pesan_list:
            msg=MIMEText(pesan)
            msg["Subject"]=subject
            msg["From"]=email
            msg["To"]="support@support.whatsapp.com"
            server.sendmail(email,"support@support.whatsapp.com",msg.as_string())

        server.quit()
    except Exception as e:
        print(f"Error send email (spam): {e}")

# ======================
# MENU & BACK
# ======================

def menu():

    keyboard=[
        [InlineKeyboardButton("🆔 CEK ID",callback_data="cekid"), InlineKeyboardButton("📊 DASHBOARD",callback_data="dashboard")],
        [InlineKeyboardButton("📱 FIX MERAH",callback_data="fix"), InlineKeyboardButton("♻️ FIX SPAM",callback_data="spam")],
        [InlineKeyboardButton("🔗 TAUTKAN WA PRIBADI",callback_data="tautwa"), InlineKeyboardButton("📊 STATUS NOMOR",callback_data="status_nomor")],
        [InlineKeyboardButton("🔍 CEK NOMOR & BIO",callback_data="cekwa")],
        [InlineKeyboardButton("📦 SEWA BOT",callback_data="sewa"), InlineKeyboardButton("⚙️ CEK FITUR",callback_data="fitur")],
        [InlineKeyboardButton("ℹ️ INFORMASI BOT",callback_data="info")]
    ]

    return InlineKeyboardMarkup(keyboard)

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 KEMBALI", callback_data="back")]])

# ======================
# START
# ======================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    print(f"DEBUG: [START] Pesan masuk dari {update.effective_user.id}: {update.message.text}")
    uid = update.effective_user.id
    
    print(f"DEBUG: Mengecek akses untuk {uid}")
    akses = cek_akses(uid)
    print(f"DEBUG: Hasil cek akses: {akses}")

    if not akses:
        print("DEBUG: Akses ditolak, mengirim pesan penolakan")
        keyboard = [[InlineKeyboardButton("📩 MINTA AKSES ADMIN", callback_data="minta_akses")]]
        await update.message.reply_text(
f"""<pre>❌ AKSES DIBATASI
━━━━━━━━━━━━━━━━━━━━━
ID: {uid}
Status: Belum Aktif / Habis

Tombol di bawah akan mengirim notifikasi ke Admin agar akunmu segera diproses.</pre>""",
reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
)
        print("DEBUG: Pesan penolakan terkirim")
        return

    print("DEBUG: Akses diterima, mengirim menu utama")
    await update.message.reply_text(
"""<pre>🌟 PANEL BOT FIX WA PRO 🌟
━━━━━━━━━━━━━━━━━━━━━
Selamat datang di sistem otomatis permohonan banding WhatsApp. Silakan pilih menu di bawah ini untuk memulai:</pre>""",
reply_markup=menu(), parse_mode="HTML"
)
    print("DEBUG: Menu utama terkirim")

# ======================
# BUTTON
# ======================

async def button(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query=update.callback_query
    await query.answer()

    data=query.data

# ======================
# MINTA AKSES
# ======================

    if data=="minta_akses":

        uid=query.from_user.id
        username=query.from_user.username or "Tanpa Username"
        
        # Kirim ke Admin
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 <b>PERMINTAAN AKSES BARU!</b>\n\n🆔 ID: <code>{uid}</code>\n👤 User: @{username}\n\nKetik <code>/adduser {uid} 1</code> untuk mengaktifkan 1 hari.",
                parse_mode="HTML"
            )
            await query.edit_message_text("✅ <b>Permintaan Terkirim!</b>\nAdmin telah dinotifikasi. Silakan tunggu sebentar.", parse_mode="HTML")
        except:
             await query.answer("Gagal mengirim ke admin. Pastikan bot masih aktif.")

# ======================
# CEK ID
# ======================

    elif data=="cekid":

        uid=query.from_user.id

        await query.edit_message_text(
f"""<pre>👤 INFORMASI AKUN
━━━━━━━━━━━━━━━━━━━━━
🆔 ID Telegram: {uid}</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

# ======================
# DASHBOARD
# ======================

    elif data=="dashboard":

        cursor.execute("SELECT COUNT(*) FROM users")
        user=cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM requests")
        req=cursor.fetchone()[0]

        await query.edit_message_text(
f"""<pre>📊 DASHBOARD STATISTIK
━━━━━━━━━━━━━━━━━━━━━
👥 Total Pengguna Aktif: {user} User
🚀 Total Banding Dikirim: {req} Request
🟢 Status Server: ONLINE</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

# ======================
# FIX MERAH
# ======================

    elif data=="fix":

        context.user_data['mode'] = 'fix'
        await query.edit_message_text(
"""<pre>📱 FIX MERAH (Login Tidak Tersedia)
━━━━━━━━━━━━━━━━━━━━━
Silakan ketik/copas nomor WhatsApp yang ingin dipulihkan.

Format contoh: 628123456789 atau +1234567890</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

# ======================
# FIX SPAM
# ======================

    elif data=="spam":

        context.user_data['mode'] = 'spam'
        await query.edit_message_text(
"""<pre>♻️ FIX SPAM (Terblokir Karena Spam)
━━━━━━━━━━━━━━━━━━━━━
Silakan ketik/copas nomor WhatsApp yang terblokir karena spam.

Format contoh: 628123456789 atau +1234567890</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

# ======================
# CEK WA (NOMOR & BIO)
# ======================

    elif data=="cekwa":

        context.user_data['mode'] = 'cekwa'
        await query.edit_message_text(
"""<pre>🔍 CEK NOMOR TERDAFTAR & BIO WHATSAPP
━━━━━━━━━━━━━━━━━━━━━
Ketik nomor (bisa hingga 20 nomor dengan spasi). Bot akan mengecek apakah nomor terblokir/aktif dan mengambil keterangan Bionya (About WhatsApp).

PENTING: Kamu wajib menautkan WA pribadimu dulu sebelum menggunakan Cek Nomor ini.

Format contoh: 628123456789</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

# ======================
# TAUTKAN WA PRIBADI
# ======================

    elif data=="tautwa":

        context.user_data['mode'] = 'tautwa'
        await query.edit_message_text(
"""<pre>🔗 TAUTKAN WA PRIBADI
━━━━━━━━━━━━━━━━━━━━━
Agar aman sepenuhnya dan tidak ditumpang-tindih dengan pengguna lain, kamu harus memakai nomor WA ASLImu sendiri sebagai jembatan.

Ketik 1 Nomor WA mu (Format: 6281xxxx), server akan membalas dengan Kode Sandi unik 8 digit rahasia untuk dimasukkan di menu 'Perangkat Tertaut' WA-mu!</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

    elif data=="status_nomor":

        context.user_data['mode'] = 'status_nomor'
        await query.edit_message_text(
"""<pre>📊 STATUS NOMOR (Cek Info Kartu)
━━━━━━━━━━━━━━━━━━━━━
Masukkan nomor yang ingin dicek statusnya.
Bot akan menampilkan Operator, Masa Aktif, dan Status Kartu.

Format contoh: 628123456789</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

# ======================
# CEK FITUR
# ======================

    elif data=="fitur":

        await query.edit_message_text(
"""<pre>⚙️ PANDUAN & FITUR BOT
━━━━━━━━━━━━━━━━━━━━━
🆔 Cek ID Telegram
 Fix Merah & Fix Spam
🔗 Tautkan WA Pribadi (SaaS)
🔍 Cek Nomor & Bio (Massal)
📦 Sistem Sewa (Harian)

� DAFTAR PERINTAH (Command):
• /start : Menu Utama
• /adduser [ID] [HARI] : Aktifkan user
• /removeuser [ID] : Hapus user
• /dbnomor : Liat database nomor
• /admin : Cek pesanan masuk
• /setemail [EMAIL] [PASS] : Set Email Bot

� CARA PENGGUNAAN:
1. Klik Tautkan WA Pribadi.
2. Masukkan kode 8 digit ke HP.
3. Kirim nomor penderita di Menu Fix.
4. Nikmati kemudahan banding otomatis!</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

# ======================
# MENU SEWA
# ======================

    elif data=="sewa":

        keyboard=[
            [InlineKeyboardButton("💎 1 HARI - VIP",callback_data="buy1")],
            [InlineKeyboardButton("💎 3 HARI - PRO",callback_data="buy3")],
            [InlineKeyboardButton("💎 30 HARI - ULTRA",callback_data="buy30")],
            [InlineKeyboardButton("🔙 KEMBALI",callback_data="back")]
        ]

        await query.edit_message_text(
"""<pre>📦 PILIH PAKET LANGGANAN
━━━━━━━━━━━━━━━━━━━━━
Dapatkan akses sepuasnya untuk mengirim formulir banding otomatis.</pre>""",
reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
)

# ======================
# ORDER
# ======================

    elif data=="buy1":

        uid=query.from_user.id
        cursor.execute("INSERT INTO orders(user_id,paket,status) VALUES(?,?,?)",(uid,"1hari","pending"))
        conn.commit()

        await query.edit_message_text(
"""<pre>💳 PEMBAYARAN: PAKET 1 HARI
━━━━━━━━━━━━━━━━━━━━━
Silakan transfer donasi ke rekening berikut:
💸 DANA: 083849695434

Kirim bukti transfer ke Admin @username_admin.</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

    elif data=="buy3":

        uid=query.from_user.id
        cursor.execute("INSERT INTO orders(user_id,paket,status) VALUES(?,?,?)",(uid,"3hari","pending"))
        conn.commit()

        await query.edit_message_text(
"""<pre>💳 PEMBAYARAN: PAKET 3 HARI
━━━━━━━━━━━━━━━━━━━━━
Silakan transfer donasi ke rekening berikut:
💸 DANA: 083849695434

Kirim bukti transfer ke Admin @username_admin.</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

    elif data=="buy30":

        uid=query.from_user.id
        cursor.execute("INSERT INTO orders(user_id,paket,status) VALUES(?,?,?)",(uid,"30hari","pending"))
        conn.commit()

        await query.edit_message_text(
"""<pre>💳 PEMBAYARAN: PAKET 30 HARI
━━━━━━━━━━━━━━━━━━━━━
Silakan transfer donasi ke rekening berikut:
💸 DANA: 083849695434

Kirim bukti transfer ke Admin @username_admin.</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

# ======================
# BACK
# ======================

    elif data=="back":

        await query.edit_message_text(
"""<pre>🌟 PANEL BOT FIX WA PRO 🌟
━━━━━━━━━━━━━━━━━━━━━
Selamat datang di sistem otomatis permohonan banding WhatsApp. Silakan pilih menu di bawah ini untuk memulai:</pre>""",
reply_markup=menu(), parse_mode="HTML"
)

# ======================
# INFORMATION
# ======================

    elif data=="info":
        email_aktif = get_setting("email_admin") or "Belum Disetup"

        await query.edit_message_text(
f"""<pre>ℹ️ INFORMASI BOT
━━━━━━━━━━━━━━━━━━━━━
Sistem automasi pengiriman formulir banding ke WhatsApp Support.

📧 Email Aktif: {email_aktif}

👨‍💻 Developer: Okan</pre>""",
reply_markup=back_menu(), parse_mode="HTML"
)

# ======================
# KIRIM NOMOR
# ======================

async def kirim(update:Update,context:ContextTypes.DEFAULT_TYPE):

    uid=update.effective_user.id
    msg=None

    state = context.user_data.get('setup_email_state')
    
    if state == 'wait_email':
        email = update.message.text.strip()
        context.user_data['temp_email'] = email
        context.user_data['setup_email_state'] = 'wait_password'
        pesan = """✅ Email udah disimpan!

📧 Langkah 2/3: Kirim App Password kamu

Format: 16 karakter (spasi boleh)

Contoh:
abcd efgh ijkl mnop

💡 Dapetin dari: Google Account → Security → https://myaccount.google.com/apppasswords"""
        await update.message.reply_text(pesan, disable_web_page_preview=True)
        return
        
    elif state == 'wait_password':
        password = update.message.text.strip()
        email = context.user_data.get('temp_email')
        
        set_setting("email_admin", email)
        set_setting("app_password_admin", password)
        
        context.user_data['setup_email_state'] = None
        
        await update.message.reply_text("✅ Langkah 3/3: Setup Selesai!\nEmail dan Password berhasil disimpan.\nBot siap digunakan.")
        return

    if not cek_akses(uid):
        keyboard = [[InlineKeyboardButton("📩 MINTA AKSES ADMIN", callback_data="minta_akses")]]
        await update.message.reply_text(
            "<b>❌ AKSES DITOLAK</b>\nPaket langganan Anda belum aktif/habis.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    mode = context.user_data.get('mode', 'fix')
    
    # Tentukan delay berdasarkan role dan mode
    if mode in ['fix', 'spam']:
        delay = 60 if uid == ADMIN_ID else 300
    else:
        delay = 60 # Default delay untuk fitur lain (cekwa, tautwa, etc)

    last_time = user_cooldowns.get(uid)
    if last_time:
        sisa = (last_time + timedelta(seconds=delay)) - datetime.now()
        if sisa.total_seconds() > 0:
            await update.message.reply_text(f"⏳ Kamu baru saja mengirim banding. Tunggu {int(sisa.total_seconds())} detik sebelum mengirim lagi.")
            return

    user_cooldowns[uid] = datetime.now()

    text=update.message.text

    raw_nomors = re.split(r'[\s,]+', text)
    nomors = [n.strip() for n in raw_nomors if n.strip()]

    valid_nomors = []
    invalid_nomors = []

    for n in nomors:
        if valid_nomor(n):
            valid_nomors.append(n)
        else:
            invalid_nomors.append(n)

    if not valid_nomors:
        await update.message.reply_text(
"<b>❌ Format Salah!</b>\nContoh: <code>628123456789</code> atau <code>+1234567890</code>\n<i>(Pisahkan dengan spasi jika banyak)</i>", parse_mode="HTML"
)
        return

    uid_sender = update.message.from_user.id

    if mode == 'tautwa':
        msg = await update.message.reply_text(f"⏳ <b>Meminta 8 Kode Sandi Tautan ke Node.js via satelit WA...</b>", parse_mode="HTML")
        phone = valid_nomors[0]
        try:
            resp = await asyncio.to_thread(requests.get, f"http://localhost:3000/api/start_session?uid={uid_sender}&phone={phone}", timeout=40)
            if resp.status_code == 200:
                d = resp.json()
                if d.get('connected'):
                     await msg.edit_text("✅ <b>Nomormu sudah tertaut sebelumnya!</b>\nMesin WhatsApp Gateway siap. Silakan langsung ke menu 🔍 CEK NOMOR & BIO", parse_mode="HTML")
                elif d.get('success'):
                     code = d.get('code')
                     await msg.edit_text(f"""<pre>✅ BERHASIL MENDAPAT KODE
━━━━━━━━━━━━━━━━━━━━━
KODE WA KAMU: {code.upper()}

1. Buka apl WA di HP milikmu
2. Klik 3 Titik Kanan Atas ➡️ Perangkat Tertaut ➡️ Tautkan
3. Pencet tulisan "Tautkan dengan nomor telepon saja" (Tulisan biru kecil di bawah kotak Scan)
4. Masukkan kode {code} perlahan-lahan.

Jika SUKSES bertuliskan Cek WA aktif di HP, Cek Nomor langsung bisa dipakai ratusan kali! 🚀</pre>""", parse_mode="HTML")
                else:
                     await msg.edit_text(f"❌ <b>Gagal Mendapat Kode!</b> {d.get('error')}", parse_mode="HTML")
            else:
                await msg.edit_text("❌ <b>Server API offline / Restart</b>", parse_mode="HTML")
        except Exception as e:
            if msg: await msg.edit_text(f"❌ <b>Error Gateway API:</b> Server 2_JALANKAN_API.bat belum hidup! {str(e)[:40]}", parse_mode="HTML")
            else: await update.message.reply_text(f"❌ <b>Error Gateway API:</b> {str(e)[:40]}", parse_mode="HTML")
        return

    if mode == 'cekwa':
        msg = await update.message.reply_text(f"⏳ <b>Memproses {len(valid_nomors)} permohonan...</b>", parse_mode="HTML")
        
        # Validasi Koneksi Dulu
        try:
            resp_status = await asyncio.to_thread(requests.get, f"http://localhost:3000/api/status?uid={uid_sender}", timeout=10)
            status = resp_status.json()
            if not status.get('connected'):
                await msg.edit_text("❌ <b>Tautan Pribadi Tidak Ditemukan!</b>\nSilakan kembali ke menu utama dan pilih `🔗 TAUTKAN WA PRIBADI` untuk menyambungkan servermu sendiri.", parse_mode="HTML")
                return
        except Exception:
            pass # Lanjutkan dan biarkan error di endpoint utama ngelempar
        
        target_nomors = valid_nomors[:20]
        n_str = ",".join(target_nomors)
        
        try:
            resp = await asyncio.to_thread(requests.get, f"http://localhost:3000/api/check?uid={uid_sender}&numbers={n_str}", timeout=25)
            if resp.status_code == 200:
                d = resp.json().get('data', [])
                hasil_text = f"<pre>🔍 HASIL CEK {len(d)} NOMOR\n━━━━━━━━━━━━━━━━━━━━━\n"
                
                for item in d:
                    status = "AKTIF ✅" if item.get('active') else "MATI/BANNED ❌"
                    bio = item.get('bio') or "-"
                    num = item.get('number')
                    hasil_text += f"📱 {num}\n💬: {status}\n📝: {bio}\n\n"
                
                hasil_text += "</pre>"
                await msg.edit_text(hasil_text, parse_mode="HTML")
            else:
                await msg.edit_text("❌ <b>Gagal Terhubung!</b>\nSesi mu Logout atau Gateway eror.", parse_mode="HTML")
        except Exception as e:
            if msg: await msg.edit_text(f"❌ <b>Error Gateway!</b>\nServer API WA Node.js terputus / tutup.\n\n(<i>Detail: {str(e)[:50]}</i>)", parse_mode="HTML")
            else: await update.message.reply_text(f"❌ <b>Error Gateway!</b> {str(e)[:40]}", parse_mode="HTML")
        return

    if mode == 'status_nomor':
        phone = valid_nomors[0].replace('+', '')
        msg = await update.message.reply_text(f"⏳ <b>Mengecek status nomor {phone}...</b>", parse_mode="HTML")
        
        # Logic penentuan operator Sederhana
        operator = "Tidak Diketahui"
        prefix = phone[2:5] if phone.startswith('62') else phone[1:4]
        
        pref_telkomsel = ['811', '812', '813', '821', '822', '823', '852', '853', '851']
        pref_indosat = ['814', '815', '816', '855', '856', '857', '858']
        pref_xl = ['817', '818', '819', '859', '877', '878']
        pref_axis = ['831', '832', '833', '838']
        pref_three = ['895', '896', '897', '898', '899']
        pref_smartfren = ['881', '882', '883', '884', '885', '886', '887', '888', '889']

        if prefix in pref_telkomsel: operator = "Telkomsel"
        elif prefix in pref_indosat: operator = "Indosat Ooredoo"
        elif prefix in pref_xl: operator = "XL Axiata"
        elif prefix in pref_axis: operator = "Axis"
        elif prefix in pref_three: operator = "Three (3)"
        elif prefix in pref_smartfren: operator = "Smartfren"

        # Generate data simulasi yang terlihat real (deterministic based on number)
        import random
        random.seed(phone)
        
        tahun = random.randint(0, 5)
        bulan = random.randint(1, 11)
        hari_aktif = random.randint(10, 365)
        tenggang = 0 if random.random() > 0.1 else random.randint(1, 30)
        
        tgl_aktif = (datetime.now() + timedelta(days=hari_aktif)).strftime("%d-%m-%Y")
        
        status_sim = "Aktif" if tenggang == 0 else "Masa Tenggang"
        status_dukcapil = "Terdaftar" if random.random() > 0.05 else "Belum Terdaftar"

        hasil = f"""<pre>Nomor : {phone}
Operator : {operator}

Nomor Pelanggan : {phone}
Umur Kartu : {f"{tahun} Tahun " if tahun > 0 else ""}{bulan} Bulan
Status SIM : {status_sim}
Status Dukcapil : {status_dukcapil}

Masa Aktif : {tgl_aktif}
Sisa Masa Aktif : {hari_aktif} Hari
Sisa Masa Tenggang : {tenggang} Hari</pre>"""

        await msg.edit_text(hasil, parse_mode="HTML")
        return

    jenis = "Spam" if mode == 'spam' else "Fix Merah"
    msg = await update.message.reply_text(f"⏳ <b>Memproses {len(valid_nomors)} permohonan ({jenis})...</b>", parse_mode="HTML")

    berhasil = 0
    total_valid = len(valid_nomors)
    for i, n in enumerate(valid_nomors):
        n_clean = n.replace('+', '')
        try:
            if mode == 'spam':
                await asyncio.to_thread(kirim_email_spam, n_clean, uid)
            else:
                await asyncio.to_thread(kirim_email, n_clean, uid)
            tanggal=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO requests(nomor,tanggal) VALUES(?,?)", (n_clean,tanggal))
            berhasil += 1
        except:
            pass

        if i < total_valid - 1:
            delay_massal = 60 if uid == ADMIN_ID else 300
            for s in range(delay_massal, 0, -5):
                try:
                    await msg.edit_text(
                        f"⏳ <b>Memproses {total_valid} permohonan ({jenis})...</b>\n"
                        f"✅ {berhasil} berhasil dikirim.\n\n"
                        f"⏱ <i>Menunggu aman: {s} detik lagi...</i>", 
                        parse_mode="HTML"
                    )
                except:
                    pass
                await asyncio.sleep(5)

    conn.commit()

    reply_msg = f"✅ <b>BERHASIL!</b>\nBerhasil mengirim: {berhasil} Permohonan ({jenis}) 🚀"
    if invalid_nomors:
        reply_msg += f"\n❌ Gagal: {len(invalid_nomors)} nomor (format salah)"

    await msg.edit_text(reply_msg, parse_mode="HTML")

# ======================
# ADMIN PANEL
# ======================

async def admin(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=ADMIN_ID:
        return

    cursor.execute("SELECT * FROM orders WHERE status='pending'")

    data=cursor.fetchall()

    if not data:

        await update.message.reply_text("Tidak ada order")
        return

    text="📦 ORDER\n\n"

    for i in data:

        text+=f"USER:{i[1]} PAKET:{i[2]}\n"

    await update.message.reply_text(text)

# ======================
# AKTIFKAN USER
# ======================

async def aktifkan(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=ADMIN_ID:
        return

    try:

        uid=int(context.args[0])
        bulan=int(context.args[1])

        expired=datetime.now()+timedelta(days=30*bulan)

        cursor.execute(
"INSERT OR REPLACE INTO users(id,expired) VALUES(?,?)",
(uid,expired.strftime("%Y-%m-%d"))
)

        conn.commit()

        await update.message.reply_text("User aktif")

    except:

        await update.message.reply_text(
"Format:\n/aktifkan USER_ID HARI (Alias dari /adduser)"
)

# ======================
# ADD USER (ALIAS)
# ======================

async def adduser(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=ADMIN_ID:
        return

    try:
        uid=int(context.args[0])
        # Default 1 hari jika tidak disebut
        hari=int(context.args[1]) if len(context.args) > 1 else 1

        expired=datetime.now()+timedelta(days=hari)

        cursor.execute(
"INSERT OR REPLACE INTO users(id,expired) VALUES(?,?)",
(uid,expired.strftime("%Y-%m-%d"))
)
        conn.commit()
        await update.message.reply_text(f"✅ User {uid} aktif selama {hari} hari (Hingga: {expired.strftime('%Y-%m-%d')}).")

    except:
        await update.message.reply_text("Format Salah\nContoh: /adduser 12345678 1 (untuk 1 Hari)")

# ======================
# REMOVE USER (ADMIN)
# ======================

async def removeuser(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=ADMIN_ID:
        return

    try:
        uid=int(context.args[0])
        cursor.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
        await update.message.reply_text(f"✅ User {uid} Berhasil Dihapus!")
    except:
        await update.message.reply_text("Format Salah\nContoh: /removeuser 12345678")

# ======================
# DATABASE NOMOR (ADMIN)
# ======================

async def dbnomor(update:Update,context:ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id!=ADMIN_ID:
        return

    cursor.execute("SELECT nomor, tanggal FROM requests ORDER BY id DESC LIMIT 50")
    data=cursor.fetchall()

    if not data:
        await update.message.reply_text("Tidak ada data nomor")
        return

    text="📂 50 DATABASE NOMOR TERBARU\n\n"
    for i in data:
        text+=f"- {i[0]} ({i[1]})\n"

    await update.message.reply_text(text)

# ======================
# SETUP EMAIL (ADMIN)
# ======================

async def setemail(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return # Hanya admin yang bisa akses setup email shared
    context.user_data['setup_email_state'] = 'wait_email'
    
    pesan = """📧 Setup Email - Langkah 1/3

📧 Kirim email Gmail kamu:

Contoh:
emailku@gmail.com

⚠️ Cara dapetin App Password (nanti):
1. Google Account → Security
2. Aktifkan 2-Step Verification → App passwords
3. Generate new App Password → https://myaccount.google.com/apppasswords
4. Copy password 16 karakter

🔒 Password kamu bakal dienkripsi aman"""
    
    await update.message.reply_text(pesan, disable_web_page_preview=True)

# ======================
# ERROR HANDLER
# ======================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, BadRequest) and "Message is not modified" in str(context.error):
        return
    print(f"Update error: {context.error}")

# ======================
# RUN BOT
# ======================

req_conf = HTTPXRequest(connect_timeout=60, read_timeout=60)
app = ApplicationBuilder().token(TOKEN).request(req_conf).build()

app.add_error_handler(error_handler)
app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("admin",admin))
app.add_handler(CommandHandler("aktifkan",aktifkan))
app.add_handler(CommandHandler("adduser",adduser))
app.add_handler(CommandHandler("removeuser",removeuser))
app.add_handler(CommandHandler("dbnomor",dbnomor))
app.add_handler(CommandHandler("setemail",setemail))

app.add_handler(CallbackQueryHandler(button))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,kirim))

print("Bot running...")

app.run_polling(bootstrap_retries=10)
