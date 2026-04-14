# Use Node.js 20 as base image
FROM node:20-bookworm

# Install Python and System Dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-full \
    sqlite3 \
    libnss3 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxtst6 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libxext6 \
    libxshmfence1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install PM2 globally
RUN npm install -g pm2

# Copy package files and install Node dependencies
COPY wa_api/package*.json ./wa_api/
RUN cd wa_api && npm install

# Copy requirement files and install Python dependencies
COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt

# Copy the rest of the application
COPY . .

# Ensure start.sh is executable
RUN chmod +x start.sh

# Expose port (if needed, e.g. 3000 for API)
EXPOSE 3000

# Start the application
CMD ["./start.sh"]
