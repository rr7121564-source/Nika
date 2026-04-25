from pyrogram import Client, filters
from bot.auth import is_allowed_chat

@Client.on_message(filters.command("start") & filters.private)
async def start(client, message):
    if not is_allowed_chat(message.chat.id):
        return await message.reply("⛔ Unauthorized Access. Ask Owner to whitelist this chat.")
    
    text = (
        "🎬 **Welcome to Pyrogram Ultra Muxer Bot!**\n\n"
        "1️⃣ Send an `MKV` Video.\n"
        "2️⃣ Send a Subtitle (`SRT` / `ASS`).\n\n"
        "⚡ I will process up to 2GB files without hassle!"
    )
    await message.reply(text)
