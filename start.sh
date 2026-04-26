#!/bin/bash
mkdir -p /app/data
chmod 777 /app/data

echo "🛠️ Checking Environment Variables..."
if [ -z "$API_ID" ] || [ -z "$API_HASH" ]; then
    echo "❌ ERROR: API_ID or API_HASH is missing in Render Environment Variables!"
    exit 1
fi

echo "🚀 Starting Telegram C++ API Server..."
# Is baar hum logs ko 'api_logs.txt' me save karenge taaki error dekh sakein
telegram-bot-api --local --api-id="${API_ID}" --api-hash="${API_HASH}" --http-port=8081 --dir=/app/data --verbosity=1 > api_logs.txt 2>&1 &

echo "⏳ Waiting for Local API Server (Port 8081)..."
for i in {1..20}; do
    if nc -z 127.0.0.1 8081; then
        echo "✅ Local API Server is LIVE!"
        python3 main.py
        exit 0
    fi
    echo "Waiting... ($i/20)"
    sleep 2
done

echo "❌ ERROR: Local API Server failed to start."
echo "📝 --- LAST 20 LINES OF API LOGS ---"
tail -n 20 api_logs.txt
exit 1
