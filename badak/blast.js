const { 
    default: makeWASocket, 
    useMultiFileAuthState, 
    DisconnectReason,
    fetchLatestBaileysVersion,
    makeCacheableSignalKeyStore
} = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const NodeCache = require('node-cache');

// --- KONFIGURASI BADAK ---
const CONTACTS_FILE = './contacts.json';
const AUTH_DIR = './auth_info_baileys';

// Cache untuk retry store jika diperlukan
const msgRetryCounterCache = new NodeCache();

// Helpers
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
// Fungsi random untuk delay (mimic human behavior)
const randomDelay = (min, max) => Math.floor(Math.random() * (max - min + 1) + min);

// Setup Logger: silent saat production agar rapi, ubah ke 'debug' jika butuh trace error
const logger = pino({ level: 'silent' });

function loadContacts() {
    try {
        if (fs.existsSync(CONTACTS_FILE)) {
            const data = fs.readFileSync(CONTACTS_FILE, 'utf8');
            return JSON.parse(data);
        }
    } catch (err) {
        console.error('Error membaca contacts.json:', err);
    }
    return [];
}

async function startWhatsAppBlast() {
    console.log('Menyiapkan sesi koneksi...');
    
    // Mendapatkan versi WA Web terbaru agar sinkron dan tidak dicurigai versi usang
    const { version, isLatest } = await fetchLatestBaileysVersion();
    console.log(`Menggunakan WA v${version.join('.')}, isLatest: ${isLatest}`);

    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

    // KUNCI BADAK 1: Konfigurasi Socket untuk me-mimic browser agar tidak terdeteksi bot standar
    const sock = makeWASocket({
        version,
        logger,
        printQRInTerminal: false, // Kita manual qr code untuk versi baileys terbaru
        auth: {
            creds: state.creds,
            /** Caching membuat decrypt msg jadi lebih cepat & stabil (mencegah limit device) */
            keys: makeCacheableSignalKeyStore(state.keys, logger),
        },
        msgRetryCounterCache,
        generateHighQualityLinkPreviews: true,
        browser: ['Ubuntu', 'Chrome', '115.0.0.0'], // Mimic browser Chrome di OS Linux
        markOnlineOnConnect: false // Jangan langsung online saat connect (stealth mode)
    });

    sock.ev.on('creds.update', saveCreds);

    // Handling Connection
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log('\n--- SCAN QR CODE INI MENGGUNAKAN WHATSAPP ANDA ---');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const isLoggedOut = statusCode === DisconnectReason.loggedOut;
            const message = lastDisconnect?.error?.message;
            
            console.log('\nKoneksi terputus! Alasan:', message || statusCode);

            // KUNCI BADAK 2: Penanganan Auto-Reconnect yang Sabar
            if (isLoggedOut) {
                console.log('STATUS: Anda telah LOGOUT dari perangkat/HP. Silakan hapus folder "auth_info_baileys", lalu start ulang script.');
                process.exit(1);
            } else {
                console.log('STATUS: Retrying koneksi dalam 10 detik...');
                setTimeout(startWhatsAppBlast, 10000); // Backoff 10 detik sebelum reconnect (jangan instant agar IP tidak di-block)
            }
        } 
        else if (connection === 'open') {
            console.log('\n✅ [BERHASIL] Terhubung ke WhatsApp!');
            await processBlast(sock);
        }
    });
}

async function processBlast(sock) {
    const contacts = loadContacts();
    
    if (contacts.length === 0) {
        console.log('Daftar kontak kosong (contacts.json) atau file tidak ditemukan.');
        return;
    }

    console.log(`\n🚀 Memulai operasi blast ke ${contacts.length} nomor tujuan...\n`);

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < contacts.length; i++) {
        const { phone, message } = contacts[i];
        
        // Parsing nomor
        let formatPhone = phone.toString().replace(/\D/g, '');
        if (formatPhone.startsWith('0')) {
            formatPhone = '62' + formatPhone.slice(1);
        }
        formatPhone = formatPhone + '@s.whatsapp.net';

        try {
            console.log(`[${i + 1}/${contacts.length}] Target: ${phone}...`);
            
            // KUNCI BADAK 3: Emulasi "Mengetik" (composing) sebelum mengirim pesan (human-like)
            await sock.sendPresenceUpdate('composing', formatPhone);
            const typingTime = randomDelay(2000, 5000); // Seakan mengetik 2-5 detik
            await delay(typingTime); 

            // Kirim pesan
            await sock.sendMessage(formatPhone, { text: message });
            await sock.sendPresenceUpdate('paused', formatPhone); // Berhenti mengetik

            console.log(` ✅ Berhasil terkirim.`);
            successCount++;
            
            // KUNCI BADAK 4: Delay panjang antar nomor agar tidak dideteksi mesin spam
            if (i < contacts.length - 1) {
                const sleepTime = randomDelay(8000, 15000); // Jeda acak 8 s.d 15 detik
                console.log(` ⏳ Menunggu ${sleepTime / 1000} detik sebelum target berikutnya...`);
                await delay(sleepTime);
            }
        } catch (error) {
            console.error(` ❌ Gagal ke ${phone}:`, error.message);
            failCount++;
        }
    }

    console.log('\n======================================');
    console.log(`📊 REKAPITULASI BLAST`);
    console.log(`✅ Sukses: ${successCount}`);
    console.log(`❌ Gagal: ${failCount}`);
    console.log('======================================\n');
    console.log('Operasi selesai. Menutup koneksi (opsional) atau biarkan standby.');
    // process.exit(0); // Buka comment ini jika ingin bot mati otomatis setelah blast selesai
}

// Jalankan sistem
startWhatsAppBlast();
