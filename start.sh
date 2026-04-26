#!/bin/bash
echo "🚀 Starting Telegram C++ API Server..."
mkdir -p /app/data
# Yahan apna API_ID aur API_HASH environment variable me set zarur karna!
telegram-bot-api --local --api-id="${API_ID}" --api-hash="${API_HASH}" --http-port=8081 --dir=/app/data &

sleep 3

echo "🚀 Starting Ultra-Fast Bot..."
python3 bot.py
