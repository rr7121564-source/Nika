#!/bin/bash
mkdir -p /app/data
chmod 777 /app/data

echo "🛠️ Validating API Credentials..."
if [[ -z "$API_ID" || -z "$API_HASH" || -z "$BOT_TOKEN" ]]; then
    echo "❌ ERROR: API_ID, API_HASH, or BOT_TOKEN is MISSING in Render Env Variables!"
    exit 1
fi

echo "🚀 Starting Telegram C++ API Server..."
# API Server ko direct run karke logs capture karein
telegram-bot-api --local --api-id="${API_ID}" --api-hash="${API_HASH}" --http-port=8081 --dir=/app/data --verbosity=1 > api_output.log 2>&1 &

echo "⏳ Checking Server Status..."
for i in {1..15}; do
    if nc -z 127.0.0.1 8081; then
        echo "✅ SUCCESS: Local API Server is LIVE on port 8081!"
        python3 main.py
        exit 0
    fi
    echo "Waiting... ($i/15)"
    sleep 2
done

echo "❌ FATAL ERROR: Local API Server could not start."
echo "📝 --- SHOWING BINARY LOGS ---"
cat api_output.log
exit 1
