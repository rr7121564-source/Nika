FROM aiogram/telegram-bot-api:latest AS api-server
FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg bash
COPY --from=api-server /usr/local/bin/telegram-bot-api /usr/bin/telegram-bot-api
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x start.sh
CMD ["./start.sh"]
