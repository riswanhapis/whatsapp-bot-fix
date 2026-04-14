# Menggunakan Python sebagai base image
FROM python:3.11-slim

# Install Node.js dan npm
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files dan install Node dependencies
COPY wa_api/package*.json ./wa_api/
RUN cd wa_api && npm install && npm install pm2 -g

# Copy requirements dan install Python dependencies
# Catatan: Karena tidak ada requirements.txt, kita install manual package yang umum digunakan
RUN pip install --no-cache-dir \
    python-telegram-bot \
    requests \
    httpx

# Copy seluruh project
COPY . .

# Buat folder data untuk persistensi
RUN mkdir -p /app/data

# Buat script entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Port yang dibuka (sama dengan Node API)
EXPOSE 3000

# Jalankan entrypoint
ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
