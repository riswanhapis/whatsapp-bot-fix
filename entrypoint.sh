#!/bin/bash

echo "🚀 Starting Node.js API..."
cd /app/wa_api && pm2 start server.js --name "wa-api"

echo "🚀 Starting Python Bot..."
cd /app && python3 bot_fixwa_pro.py &

echo "✅ App is running!"
# Keep the container alive by waiting on pm2 or tailing logs
pm2 logs
