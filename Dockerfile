FROM aiogram/telegram-bot-api:latest AS api-server
FROM python:3.10-slim
WORKDIR /app

# API Server ke liye zaruri system libraries install karein
RUN apt-get update && apt-get install -y \
    ffmpeg bash procps netcat-openbsd \
    libssl-dev zlib1g-dev libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Binary copy karein
COPY --from=api-server /usr/local/bin/telegram-bot-api /usr/bin/telegram-bot-api

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh
CMD ["./start.sh"]
