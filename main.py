import nest_asyncio
from pyrogram import Client
from bot.config import BOT_TOKEN, API_ID, API_HASH
from bot.server import keep_alive

nest_asyncio.apply()

def main():
    # Render Health Check Bypass
    keep_alive()

    # Initialize Pyrogram Client
    app = Client(
        "MuxBotSession",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(root="bot.plugins")
    )

    print("🚀 Pyrogram MTProto Bot Engine is Running...")
    app.run()

if __name__ == "__main__":
    main()
