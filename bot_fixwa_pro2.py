import sqlite3
import smtplib
import re
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from telegram import (
InlineKeyboardButton,
InlineKeyboardMarkup,
Update
)

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

TOKEN = "8732760502:AAETLlukc4zP1_p9O52Mw2I7MGcpbKb2oP4"

EMAIL = "rizkyrizzky3@gmail.com"
APP_PASSWORD = "b i b a h c e g e h a b p h w v"

ADMIN_ID = 5895566352

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

def valid_nomor(nomor):

    nomor = nomor.replace("+","").replace(" ","")

    if not nomor.isdigit():
        return False

    if len(nomor) < 8 or len(nomor) > 15:
        return False

    return nomor

# ======================
# KIRIM EMAIL FIX MERAH
# ======================

def kirim_email(nomor):

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
    msg["From"]=EMAIL
    msg["To"]="support@support.whatsapp.com"

    server=smtplib.SMTP_SSL("smtp.gmail.com",465)
    server.login(EMAIL,APP_PASSWORD)
    server.sendmail(EMAIL,"support@support.whatsapp.com",msg.as_string())
    server.quit()

# ======================
# MENU
# ======================

def menu():

    keyboard=[

[InlineKeyboardButton("🆔 CEK ID",callback_data="cekid")],

[InlineKeyboardButton("📊 DASHBOARD",callback_data="dashboard")],

[InlineKeyboardButton("📱 FIX MERAH",callback_data="fix")],

[InlineKeyboardButton("📦 SEWA BOT",callback_data="sewa")],

[InlineKeyboardButton("ℹ INFORMATION",callback_data="info")]

]

    return InlineKeyboardMarkup(keyboard)

# ======================
# START
# ======================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

"""🎛 PANEL BOT FIX MERAH

Pilih menu dibawah
""",

reply_markup=menu()

)

# ======================
# BUTTON
# ======================

async def button(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query=update.callback_query
    await query.answer()

    data=query.data

# ======================
# CEK ID
# ======================

    if data=="cekid":

        uid=query.from_user.id

        await query.edit_message_text(

f"🆔 ID Telegram kamu:\n{uid}",

reply_markup=menu()

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

f"""📊 DASHBOARD BOT

👤 Total User : {user}

📱 Total Fix : {req}

🤖 Status : Online
""",

reply_markup=menu()

)

# ======================
# FIX MERAH
# ======================

    elif data=="fix":

        await query.edit_message_text(

"""📱 FIX MERAH

Kirim nomor dengan format:

628xxxxxxxxxx
""")

# ======================
# MENU SEWA
# ======================

    elif data=="sewa":

        keyboard=[

[InlineKeyboardButton("1 BULAN - 50K",callback_data="buy1")],

[InlineKeyboardButton("3 BULAN - 120K",callback_data="buy3")],

[InlineKeyboardButton("KEMBALI",callback_data="back")]

]

        await query.edit_message_text(

"📦 PILIH PAKET",

reply_markup=InlineKeyboardMarkup(keyboard)

)

# ======================
# ORDER
# ======================

    elif data=="buy1":

        uid=query.from_user.id

        cursor.execute(

"INSERT INTO orders(user_id,paket,status) VALUES(?,?,?)",

(uid,"1bulan","pending")

)

        conn.commit()

        await query.edit_message_text(

"""💳 PEMBAYARAN

DANA : 08123456789

Setelah transfer kirim bukti ke admin
""",

reply_markup=menu()

)

    elif data=="buy3":

        uid=query.from_user.id

        cursor.execute(

"INSERT INTO orders(user_id,paket,status) VALUES(?,?,?)",

(uid,"3bulan","pending")

)

        conn.commit()

        await query.edit_message_text(

"""💳 PEMBAYARAN

DANA : 08123456789

Setelah transfer kirim bukti ke admin
""",

reply_markup=menu()

)

# ======================
# BACK
# ======================

    elif data=="back":

        await query.edit_message_text(

"🎛 PANEL BOT",

reply_markup=menu()

)

# ======================
# INFORMATION
# ======================

    elif data=="info":

        await query.edit_message_text(

"""ℹ BOT FIX MERAH

Bot untuk mengirim request ke support WhatsApp.

Developer : Okan
""",

reply_markup=menu()

)

# ======================
# KIRIM NOMOR
# ======================

async def kirim(update:Update,context:ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id

    if not cek_akses(uid):
        await update.message.reply_text("❌ akses tidak aktif")
        return

    text = update.message.text

    daftar_nomor = text.split("\n")

    berhasil = 0
    gagal = 0

    await update.message.reply_text("⏳ memproses nomor...")

    for n in daftar_nomor:

        nomor = valid_nomor(n)

        if not nomor:
            gagal += 1
            continue

        try:

            kirim_email(nomor)

            tanggal=datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
            "INSERT INTO requests(nomor,tanggal) VALUES(?,?)",
            (nomor,tanggal)
            )

            conn.commit()

            berhasil += 1

        except:
            gagal += 1

    await update.message.reply_text(
f"""📊 HASIL PROSES

✅ Berhasil : {berhasil}
❌ Gagal : {gagal}
"""
)
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
"Format:\n/aktifkan USER_ID BULAN"
)

# ======================
# RUN BOT
# ======================

app=ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("admin",admin))
app.add_handler(CommandHandler("aktifkan",aktifkan))

app.add_handler(CallbackQueryHandler(button))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,kirim))

print("Bot running...")

app.run_polling()
