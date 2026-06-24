# Use the official Puppeteer image which includes Chromium and Node.js pre-installed
FROM ghcr.io/puppeteer/puppeteer:21.5.0

# Run as root to install Python and clean up
USER root

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy root package files and install dependencies
COPY package*.json ./
RUN npm ci

# Copy the rest of the application
COPY . .

# Expose port and start server
ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
