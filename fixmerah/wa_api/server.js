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
    const DATA_DIR = process.env.DATA_DIR || '.';
    const sessionDir = `${DATA_DIR}/auth_baileys_${uid}`;
    const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
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

    // Masukkan ke Map agar bisa diakses global
    sessions.set(uid, sock);

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect } = update;
        
        if (connection === 'close') {
            const statusCode = (lastDisconnect.error)?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            
            console.log(`[!] UID ${uid} Terputus. Status: ${statusCode}. Reconnect: ${shouldReconnect}`);
            
            if (shouldReconnect) {
                // Beri jeda 5 detik agar tidak terjadi loop spam
                setTimeout(() => startSession(uid, null), 5000);
            } else {
                console.log(`[❌] User ${uid} Logout. Menghapus data sesi...`);
                sessions.delete(uid);
                try { 
                    const sessionDir = `${DATA_DIR}/auth_baileys_${uid}`;
                    fs.rmSync(sessionDir, { recursive: true, force: true }); 
                } catch (e) {}
            }
        } else if (connection === 'open') {
            console.log(`✅ [AKTIF] UID ${uid} Terhubung ke WhatsApp!`);
            sock.isReady = true;
        }
    });

    // Tunggu sebentar untuk trigger pairing code
    if (!sock.authState.creds.registered && phoneNumber) {
        return new Promise((resolve) => {
            setTimeout(async () => {
                try {
                    let cleanNumber = phoneNumber.replace(/[^0-9]/g, '');
                    const code = await sock.requestPairingCode(cleanNumber);
                    console.log(`[PAIR] UID ${uid} Mengeluarkan Kode: ${code}`);
                    resolve({ success: true, code: code });
                } catch (err) {
                    console.error(`[ERR] Gagal Pairing UID ${uid}:`, err.message);
                    resolve({ success: false, error: err.message });
                }
            }, 5000);
        });
    }

    return { success: true, message: "Inisialisasi Berjalan..." };
}

app.get('/api/start_session', async (req, res) => {
    let { uid, phone } = req.query;
    if (!uid) return res.status(400).json({ error: "UID diperlukan" });
    
    let sock = sessions.get(uid);
    if (sock && sock.isReady) return res.json({ connected: true });
    
    const result = await startSession(uid, phone);
    res.json(result);
});

app.get('/api/status', async (req, res) => {
    let { uid } = req.query;
    let sock = sessions.get(uid);
    if (!sock || !sock.isReady) return res.json({ connected: false });
    res.json({ connected: true });
});

app.get('/api/check', async (req, res) => {
    let { uid, numbers } = req.query; 
    let sock = sessions.get(uid);
    if (!sock || !sock.isReady) return res.status(401).json({ error: "Belum login WA" });

    const numList = numbers.split(',').map(n => n.replace(/\D/g, '') + '@s.whatsapp.net');
    let results = [];
    for (const jid of numList) {
        try {
            const [result] = await sock.onWhatsApp(jid);
            if (result && result.exists) {
                let bio = "Tidak ada bio / Privasi disembunyikan";
                try {
                    const status = await sock.fetchStatus(result.jid);
                    if (status && status.status) bio = status.status;
                } catch(e) {}
                results.push({ number: jid.split('@')[0], active: true, bio: bio });
            } else {
                results.push({ number: jid.split('@')[0], active: false, bio: null });
            }
        } catch (error) {
            results.push({ number: jid.split('@')[0], active: false, error: "Gagal API" });
        }
    }
    res.json({ data: results });
});

app.listen(PORT, () => {
    console.log(`🚀 WA SaaS Stable Engine Berjalan di Port ${PORT}`);
    // Auto-resume
    if (fs.existsSync('.')) {
        fs.readdirSync('.').forEach(dir => {
            if (dir.startsWith('auth_baileys_') && fs.lstatSync(dir).isDirectory()) {
                const uid = dir.replace('auth_baileys_', '');
                console.log(`[BOOT] Melanjutkan sesi UID ${uid}...`);
                startSession(uid, null);
            }
        });
    }
});
