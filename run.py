import subprocess
import sys
import time
import os
import signal

# Configuration
NODE_API_PATH = os.path.join("wa_api", "server.js")
PYTHON_BOT_PATH = "bot_fixwa_pro.py"

def run_app():
    processes = []
    
    print("🌟 PANEL BOT FIX WA PRO - Unified Launcher 🌟")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. Start Node.js API
    print(f"🚀 Memulai Node.js API ({NODE_API_PATH})...")
    try:
        node_proc = subprocess.Popen(
            ["node", NODE_API_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        processes.append(node_proc)
    except FileNotFoundError:
        print("❌ Error: 'node' tidak ditemukan. Pastikan Node.js sudah terinstal.")
        return

    # 2. Start Python Bot
    print(f"🚀 Memulai Python Bot ({PYTHON_BOT_PATH})...")
    python_executable = sys.executable
    bot_proc = subprocess.Popen(
        [python_executable, PYTHON_BOT_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    processes.append(bot_proc)

    print("✅ Semua sistem berjalan! Tekan Ctrl+C untuk berhenti.\n")

    # Function to handle output streaming
    def stream_output(process, prefix):
        for line in iter(process.stdout.readline, ""):
            if line:
                print(f"[{prefix}] {line.strip()}")

    # We'll use a simple loop to check if processes are alive
    # and print their output
    import threading
    
    t1 = threading.Thread(target=stream_output, args=(node_proc, "API"), daemon=True)
    t2 = threading.Thread(target=stream_output, args=(bot_proc, "BOT"), daemon=True)
    
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
            if node_proc.poll() is not None:
                print("⚠️ Node.js API telah berhenti.")
                break
            if bot_proc.poll() is not None:
                print("⚠️ Python Bot telah berhenti.")
                break
    except KeyboardInterrupt:
        print("\n🛑 Memberhentikan semua proses...")
    finally:
        for p in processes:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("👋 Selesai.")

if __name__ == "__main__":
    run_app()
