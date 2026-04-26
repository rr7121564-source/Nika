#!/bin/bash

# Folder create karna zaruri hai
mkdir -p /app/data

echo "🚀 Starting Telegram C++ API Server..."
# API Server ko background me start karein
telegram-bot-api --local --api-id="${API_ID}" --api-hash="${API_HASH}" --http-port=8081 --dir=/app/data &

# Jab tak port 8081 open na ho jaye, wait karein (Maximum 30 seconds)
echo "⏳ Waiting for Local API Server to wake up on port 8081..."
timeout 30s bash -c 'until printf "" 2>>/dev/null >/dev/tcp/127.0.0.1/8081; do sleep 1; done'

echo "✅ Local API Server is UP!"
echo "🚀 Starting Python Bot..."
python3 main.py
