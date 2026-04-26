#!/bin/bash
mkdir -p /app/data

echo "🚀 Starting Telegram C++ API Server..."
# API Server start karein
telegram-bot-api --local --api-id="${API_ID}" --api-hash="${API_HASH}" --http-port=8081 --dir=/app/data &

echo "⏳ Waiting for Local API Server (Port 8081) to start..."
# 30 seconds tak check karega ki port 8081 active hua ya nahi
for i in {1..30}; do
    if nc -z 127.0.0.1 8081; then
        echo "✅ Local API Server is LIVE!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 1
done

# Agar 30 sec baad bhi server nahi chala toh error dega
if ! nc -z 127.0.0.1 8081; then
    echo "❌ ERROR: Local API Server failed to start. Check your API_ID and API_HASH."
    exit 1
fi

echo "🚀 Starting Python Bot..."
python3 main.py
