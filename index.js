const { 
    makeWASocket, 
    useMultiFileAuthState, 
    DisconnectReason, 
    fetchLatestBaileysVersion, 
    makeCacheableSignalKeyStore 
} = require('@whiskeysockets/baileys');
const { Telegraf, Markup, session } = require('telegraf');
const Database = require('better-sqlite3');
const express = require('express');
const pino = require('pino');
const fs = require('fs');
const nodemailer = require('nodemailer');
const path = require('path');
const axios = require('axios');

// ======================
// CONFIG & CONSTANTS
// ======================
const TOKEN = "8669486008:AAEZ6TFz7Gmq6T19k4prYH9dhlhDJVXigTY";
const ADMIN_ID = 5895566352;
const DATA_DIR = process.env.DATA_DIR || '.';

// ======================
// DATABASE
// ======================
const db = new Database(path.join(DATA_DIR, 'bot.db'));
db.pragma('journal_mode = WAL');

db.exec(`
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, expired TEXT);
    CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, nomor TEXT, tanggal TEXT);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, paket TEXT, status TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
`);

const getSetting = (key, def = "") => db.prepare("SELECT value FROM settings WHERE key = ?").get(key)?.value || def;
const setSetting = (key, val) => db.prepare("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)").run(key, String(val));
const checkAccess = (id) => (id === ADMIN_ID || (db.prepare("SELECT expired FROM users WHERE id = ?").get(id)?.expired && new Date(db.prepare("SELECT expired FROM users WHERE id = ?").get(id).expired) > new Date()));

// ======================
// EMAIL HELPER
// ======================
async function sendEmail(nomor, mode) {
    const email = getSetting("email_admin");
    const pass = getSetting("app_password_admin");
    if (!email || !pass) throw new Error("Email admin belum disetup!");

    const transporter = nodemailer.createTransport({
        service: 'gmail',
        auth: { user: email, pass: pass }
    });

    const subjects = {
        fix: "Request Review WhatsApp Account",
        spam: ["Request to Unban My WhatsApp Account (Spam)", "Review Request: Account Suspended", "Appeal: WhatsApp Number Banned"]
    };

    const messages = {
        fix: `Halo Tim WhatsApp,\n\nSaya ingin mengajukan permohonan peninjauan ulang. Muncul pesan "login tidak tersedia" pada nomor saya: +${nomor}.\n\nMohon bantuannya.\nTerima kasih.`,
        spam: [
            `Estimado equipo, mi número +${nomor} ha sido bloqueado. Solicito su desbloqueo. Gracias.`,
            `Attention WhatsApp, my restaurant number +${nomor} was blocked due to high order volume. Please unblock.`,
            `Estimada equipe, meu número +${nomor} foi bloqueado após furto do celular. Solicito desbloqueo.`
        ]
    };

    if (mode === 'fix') {
        await transporter.sendMail({ from: email, to: "support@support.whatsapp.com", subject: subjects.fix, text: messages.fix });
    } else {
        for (let i = 0; i < 3; i++) {
            await transporter.sendMail({ from: email, to: "support@support.whatsapp.com", subject: subjects.spam[i], text: messages.spam[i] });
        }
    }
}

// ======================
// WHATSAPP (BAILEYS)
// ======================
const sessions = new Map();
async function getWASocket(uid, phone = null) {
    if (sessions.has(uid) && sessions.get(uid).isReady) return sessions.get(uid);
    
    const sessionDir = path.join(DATA_DIR, `auth_baileys_${uid}`);
    const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
    const { version } = await fetchLatestBaileysVersion();
    const sock = makeWASocket({ version, auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, pino({ level: 'silent' })) }, printQRInTerminal: false, browser: ['Ubuntu', 'Chrome', '122.0.0.0'] });
    
    sessions.set(uid, sock);
    sock.ev.on('creds.update', saveCreds);
    
    return new Promise((resolve) => {
        sock.ev.on('connection.update', async (up) => {
            const { connection, qr } = up;
            if (connection === 'open') { sock.isReady = true; resolve(sock); }
            if (qr && phone) {
                const code = await sock.requestPairingCode(phone.replace(/\D/g, ''));
                sock.pairingCode = code;
                resolve(sock);
            }
        });
        setTimeout(() => resolve(null), 15000);
    });
}

// ======================
// TELEGRAM BOT
// ======================
const bot = new Telegraf(TOKEN);
bot.use(session());

const menu = Markup.inlineKeyboard([
    [Markup.button.callback("🆔 CEK ID", "cekid"), Markup.button.callback("📊 DASHBOARD", "dashboard")],
    [Markup.button.callback("📱 FIX MERAH", "fix"), Markup.button.callback("♻️ FIX SPAM", "spam")],
    [Markup.button.callback("🔗 TAUTKAN WA PRIBADI", "tautwa"), Markup.button.callback("📊 STATUS NOMOR", "status_nomor")],
    [Markup.button.callback("🔍 CEK NOMOR & BIO", "cekwa")],
    [Markup.button.callback("📦 SEWA BOT", "sewa")],
    [Markup.button.callback("ℹ️ INFORMASI BOT", "info")]
]);

bot.start((ctx) => {
    if (!checkAccess(ctx.from.id)) return ctx.replyWithHTML("❌ <b>AKSES DIBATASI</b>", Markup.inlineKeyboard([[Markup.button.callback("📩 MINTA AKSES", "minta_akses")]]));
    ctx.replyWithHTML("🌟 <b>PANEL BOT FIX WA PRO</b> 🌟", menu);
});

bot.action("tautwa", (ctx) => { 
    ctx.session = { mode: "tautwa" }; 
    ctx.editMessageText("🔗 <b>TAUTKAN WA</b>\nKetik nomor WA (6281xxx):", { parse_mode: 'HTML', ...Markup.inlineKeyboard([[Markup.button.callback("🔙 KEMBALI", "back")]]) });
});

bot.action(/fix|spam/, (ctx) => {
    ctx.session = { mode: ctx.match[0] };
    ctx.editMessageText(`📱 <b>MODE ${ctx.match[0].toUpperCase()}</b>\nKetik nomornya:`, { parse_mode: 'HTML', ...Markup.inlineKeyboard([[Markup.button.callback("🔙 KEMBALI", "back")]]) });
});

bot.action("cekwa", (ctx) => {
    ctx.session = { mode: "cekwa" };
    ctx.editMessageText("🔍 <b>CEK NOMOR & BIO</b>\nKetik nomor (pisah spasi, maks 20):", { parse_mode: 'HTML', ...Markup.inlineKeyboard([[Markup.button.callback("🔙 KEMBALI", "back")]]) });
});

bot.action("status_nomor", (ctx) => {
    ctx.session = { mode: "status_nomor" };
    ctx.editMessageText("📊 <b>STATUS NOMOR</b>\nKetik nomor kartu (628xxx):", { parse_mode: 'HTML', ...Markup.inlineKeyboard([[Markup.button.callback("🔙 KEMBALI", "back")]]) });
});

bot.action("sewa", (ctx) => {
    ctx.editMessageText("📦 <b>PILIH PAKET</b>\n1. VIP (1 Hari)\n2. PRO (3 Hari)\n3. ULTRA (30 Hari)\n\nHubungi Admin @Okan untuk aktivasi.", { parse_mode: 'HTML', ...Markup.inlineKeyboard([[Markup.button.callback("🔙 KEMBALI", "back")]]) });
});

bot.action("info", (ctx) => {
    const email = getSetting("email_admin", "Belum disetup");
    ctx.editMessageText(`ℹ️ <b>INFO BOT</b>\nEmail Aktif: ${email}\nDev: Okan`, { parse_mode: 'HTML', ...Markup.inlineKeyboard([[Markup.button.callback("🔙 KEMBALI", "back")]]) });
});

bot.on('text', async (ctx) => {
    const uid = ctx.from.id;
    if (!checkAccess(uid)) return;
    const { mode } = ctx.session || {};
    const text = ctx.message.text.trim();

    if (mode === 'tautwa') {
        ctx.reply("⌛ Mendapat kode...");
        const sock = await getWASocket(uid, text);
        if (sock?.pairingCode) ctx.replyWithHTML(`✅ KODE ANDA: <b>${sock.pairingCode}</b>`);
        else if (sock?.isReady) ctx.reply("✅ Sudah terhubung!");
    } else if (mode === 'fix' || mode === 'spam') {
        ctx.reply("⌛ Mengirim banding...");
        try {
            await sendEmail(text.replace(/\D/g, ''), mode);
            db.prepare("INSERT INTO requests(nomor, tanggal) VALUES(?, ?)").run(text, new Date().toISOString());
            ctx.reply("✅ Berhasil dikirim!");
        } catch (e) { ctx.reply("❌ Gagal: " + e.message); }
    } else if (mode === 'cekwa') {
        const numbers = text.split(/\s+/).map(n => n.replace(/\D/g, '') + '@s.whatsapp.net');
        const sock = await getWASocket(uid);
        if (!sock?.isReady) return ctx.reply("❌ WA belum tertaut!");
        ctx.reply("⌛ Mengecek...");
        let res = "🔍 <b>HASIL:</b>\n\n";
        for (const jid of numbers.slice(0, 20)) {
            const [onwa] = await sock.onWhatsApp(jid);
            if (onwa?.exists) {
                const status = await sock.fetchStatus(onwa.jid).catch(() => ({ status: "Privacy" }));
                res += `✅ ${jid.split('@')[0]}\n📝: ${status.status || "Privacy"}\n\n`;
            } else res += `❌ ${jid.split('@')[0]}\n\n`;
        }
        ctx.replyWithHTML(res);
    } else if (mode === 'status_nomor') {
        const phone = text.replace(/\D/g, '');
        ctx.replyWithHTML(`<pre>Nomor: ${phone}\nOperator: Cek Manual\nStatus: Aktif</pre>`);
    } else if (ctx.session?.setupEmail) {
        if (ctx.session.setupEmail === 'email') {
            ctx.session.tempEmail = text;
            ctx.session.setupEmail = 'pass';
            ctx.reply("Ketik App Password Gmail:");
        } else {
            setSetting("email_admin", ctx.session.tempEmail);
            setSetting("app_password_admin", text);
            ctx.session.setupEmail = null;
            ctx.reply("✅ Berhasil disimpan!");
        }
    }
});

bot.command('setemail', (ctx) => {
    if (ctx.from.id !== ADMIN_ID) return;
    ctx.session = { setupEmail: 'email' };
    ctx.reply("Ketik Email Gmail Admin:");
});

bot.command('admin', (ctx) => {
    if (ctx.from.id !== ADMIN_ID) return;
    const orders = db.prepare("SELECT * FROM orders WHERE status = 'pending' LIMIT 5").all();
    let msg = "📊 <b>PENDING ORDERS:</b>\n";
    orders.forEach(o => msg += `ID: ${o.user_id} - ${o.paket}\n`);
    ctx.replyWithHTML(msg);
});

bot.action("back", (ctx) => ctx.editMessageText("🌟 <b>PANEL BOT FIX WA PRO</b> 🌟", { parse_mode: 'HTML', ...menu }));
bot.action("cekid", (ctx) => ctx.answerCbQuery(`ID Anda: ${ctx.from.id}`, { show_alert: true }));

bot.launch().then(() => console.log("🤖 Connected!"));

const app = express();
app.listen(3000);
