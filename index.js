const { 
    makeWASocket, useMultiFileAuthState, DisconnectReason, 
    fetchLatestBaileysVersion, makeCacheableSignalKeyStore 
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
const logger = pino({ level: 'silent' });

// ======================
// DATABASE HELPER (Optimized)
// ======================
const db = new Database(path.join(DATA_DIR, 'bot.db'));
db.pragma('journal_mode = WAL');
db.exec(`
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, expired TEXT);
    CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, nomor TEXT, tanggal TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
`);

const stmt = {
    getSetting: db.prepare("SELECT value FROM settings WHERE key = ?"),
    setSetting: db.prepare("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)"),
    getUser: db.prepare("SELECT expired FROM users WHERE id = ?"),
    addRequest: db.prepare("INSERT INTO requests(nomor, tanggal) VALUES(?, ?)")
};

const getSetting = (key, def = "") => stmt.getSetting.get(key)?.value || def;
const setSetting = (key, val) => stmt.setSetting.run(key, String(val));
const checkAccess = (id) => (id === ADMIN_ID || (stmt.getUser.get(id)?.expired && new Date(stmt.getUser.get(id).expired) > new Date()));

// ======================
// RATE LIMITER
// ======================
const rateLimits = new Map();
const checkRateLimit = (uid, limitMs = 2000) => {
    const now = Date.now();
    const last = rateLimits.get(uid) || 0;
    if (now - last < limitMs) return false;
    rateLimits.set(uid, now);
    return true;
};

// ======================
// SESSION MANAGER (Class Based)
// ======================
class WASessionManager {
    constructor() {
        this.sessions = new Map();
        this.timeouts = new Map();
    }

    async getSocket(uid, phone = null) {
        if (this.sessions.has(uid)) {
            const current = this.sessions.get(uid);
            if (current.isReady) {
                this._resetTimeout(uid);
                return current;
            }
        }
        return await this._createSocket(uid, phone);
    }

    async _createSocket(uid, phone) {
        const sessionDir = path.join(DATA_DIR, `auth_baileys_${uid}`);
        const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
        const { version } = await fetchLatestBaileysVersion();

        const sock = makeWASocket({
            version, logger, printQRInTerminal: false,
            auth: { creds: state.creds, keys: makeCacheableSignalKeyStore(state.keys, logger) },
            browser: ['Ubuntu', 'Chrome', '122.0.0.0']
        });

        this.sessions.set(uid, sock);
        sock.ev.on('creds.update', saveCreds);

        return new Promise((resolve) => {
            sock.ev.on('connection.update', async (up) => {
                const { connection, lastDisconnect, qr } = up;
                if (connection === 'open') {
                    sock.isReady = true;
                    this._resetTimeout(uid);
                    resolve(sock);
                } else if (connection === 'close') {
                    const code = lastDisconnect?.error?.output?.statusCode;
                    if (code !== DisconnectReason.loggedOut) {
                        this._createSocket(uid, phone); // Simple reconnect
                    } else {
                        this.destroy(uid);
                    }
                }
                if (qr && phone) {
                    sock.pairingCode = await sock.requestPairingCode(phone.replace(/\D/g, ''));
                    resolve(sock);
                }
            });
            setTimeout(() => resolve(null), 20000);
        });
    }

    _resetTimeout(uid) {
        if (this.timeouts.has(uid)) clearTimeout(this.timeouts.get(uid));
        this.timeouts.set(uid, setTimeout(() => {
            console.log(`[CLEANUP] Closing idle session: ${uid}`);
            this.destroy(uid);
        }, 600000)); // 10 minutes idle
    }

    destroy(uid) {
        const sock = this.sessions.get(uid);
        if (sock) {
            sock.ev.removeAllListeners('connection.update');
            sock.ws.close();
            this.sessions.delete(uid);
        }
    }
}
const waManager = new WASessionManager();

// ======================
// EMAIL HELPER (Optimized)
// ======================
async function sendOptimizedEmail(nomor, mode) {
    const email = getSetting("email_admin");
    const pass = getSetting("app_password_admin");
    if (!email || !pass) throw new Error("Email admin missing!");

    const transporter = nodemailer.createTransport({ service: 'gmail', auth: { user: email, pass: pass } });
    const delay = (ms) => new Promise(r => setTimeout(r, ms));

    if (mode === 'fix') {
        await transporter.sendMail({ 
            from: email, to: "support@support.whatsapp.com", 
            subject: "Request Review WhatsApp Account", 
            text: `Halo Tim WhatsApp,\n\nSaya ingin mengajukan permohonan peninjauan ulang pada nomor: +${nomor}.`
        });
    } else {
        const templates = [
            { s: "Unban Request (Spam)", t: `My number +${nomor} was blocked. Please review.` },
            { s: "Appeal: Account Suspended", t: `Hello, +${nomor} is my business number. Please unblock.` },
            { s: "Issue with +${nomor}", t: `Kindly unblock +${nomor}. It was banned accidentally.` }
        ];
        for (const tmpl of templates) {
            await transporter.sendMail({ from: email, to: "support@support.whatsapp.com", subject: tmpl.s, text: tmpl.t });
            await delay(2000); // 2s gap between emails
        }
    }
}

// ======================
// TELEGRAM BOT
// ======================
const bot = new Telegraf(TOKEN);
bot.use(session());

const menu = Markup.inlineKeyboard([
    [Markup.button.callback("🆔 CEK ID", "cekid"), Markup.button.callback("📊 DASHBOARD", "dashboard")],
    [Markup.button.callback("📱 FIX MERAH", "fix"), Markup.button.callback("♻️ FIX SPAM", "spam")],
    [Markup.button.callback("🔗 TAUTKAN WA", "tautwa"), Markup.button.callback("🔍 CEK BIO", "cekwa")],
    [Markup.button.callback("ℹ️ INFO", "info")]
]);

bot.start((ctx) => {
    if (!checkAccess(ctx.from.id)) return ctx.reply("❌ AKSES DIBATASI");
    ctx.replyWithHTML("🌟 <b>OKANOKOS BOT OPTIMIZED</b> 🌟", menu);
});

bot.action(/fix|spam|tautwa|cekwa/, (ctx) => {
    ctx.session = { mode: ctx.match[0] };
    ctx.reply(`Masukkan data untuk mode ${ctx.match[0].toUpperCase()}:`);
});

bot.on('text', async (ctx) => {
    const uid = ctx.from.id;
    if (!checkAccess(uid)) return;
    if (!checkRateLimit(uid)) return ctx.reply("⏳ Tunggu sebentar...");

    const mode = ctx.session?.mode;
    const text = ctx.message.text.trim();

    try {
        if (mode === 'tautwa') {
            const sock = await waManager.getSocket(uid, text);
            if (sock?.pairingCode) ctx.reply(`✅ KODE: ${sock.pairingCode}`);
        } else if (mode === 'fix' || mode === 'spam') {
            await sendOptimizedEmail(text, mode);
            stmt.addRequest.run(text, new Date().toISOString());
            ctx.reply("✅ Banding dikirim.");
        } else if (mode === 'cekwa') {
            const numbers = text.split(/\s+/).slice(0, 10);
            const sock = await waManager.getSocket(uid);
            if (!sock?.isReady) return ctx.reply("❌ WA belum tertaut!");
            
            let res = "🔍 <b>HASIL:</b>\n\n";
            for (const n of numbers) {
                const [onwa] = await sock.onWhatsApp(n + "@s.whatsapp.net");
                res += `${onwa?.exists ? '✅' : '❌'} ${n}\n`;
            }
            ctx.replyWithHTML(res);
        }
    } catch (e) { ctx.reply("Error: " + e.message); }
});

bot.launch();
express().listen(3000);
console.log("🚀 Server Ready & Optimized");
