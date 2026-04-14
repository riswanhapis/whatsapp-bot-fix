const { makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion, makeCacheableSignalKeyStore } = require('@whiskeysockets/baileys');
const express = require('express');
const pino = require('pino');
const fs = require('fs');

const app = express();
app.use(express.json());
const PORT = 3000;

const sessions = new Map();

async function startSession(uid, phoneNumber) {
    if (sessions.has(uid) && sessions.get(uid).isReady) {
        return { success: true, message: "Sesi sudah aktif." };
    }

    console.log(`[API] Memulai Sesi Baileys Stable (UID: ${uid})`);
    const { state, saveCreds } = await useMultiFileAuthState(`auth_baileys_${uid}`);
    const { version } = await fetchLatestBaileysVersion();
    
    const sock = makeWASocket({
        version,
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, pino({ level: "silent" }))
        },
        printQRInTerminal: false,
        logger: pino({ level: "silent" }),
        browser: ['Ubuntu', 'Chrome', '122.0.0.0']
    });

    sessions.set(uid, sock);
    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect } = update;
        
        if (connection === 'close') {
            const statusCode = (lastDisconnect.error)?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            if (shouldReconnect) {
                setTimeout(() => startSession(uid, null), 5000);
            } else {
                sessions.delete(uid);
                try { fs.rmSync(`auth_baileys_${uid}`, { recursive: true, force: true }); } catch (e) {}
            }
        } else if (connection === 'open') {
            sock.isReady = true;
        }
    });

    if (!sock.authState.creds.registered && phoneNumber) {
        return new Promise((resolve) => {
            setTimeout(async () => {
                try {
                    const code = await sock.requestPairingCode(phoneNumber.replace(/\D/g, ''));
                    resolve({ success: true, code: code });
                } catch (err) {
                    resolve({ success: false, error: err.message });
                }
            }, 5000);
        });
    }

    return { success: true, message: "Inisialisasi Berjalan..." };
}

app.get('/api/start_session', async (req, res) => {
    let { uid, phone } = req.query;
    const result = await startSession(uid, phone);
    res.json(result);
});

app.listen(PORT, () => console.log(`🚀 WA API jalan di Port ${PORT}`));
