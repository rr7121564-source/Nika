from pyrogram import Client, filters
from bot.auth import is_allowed_chat

@Client.on_message(filters.command("start") & filters.private)
async def start(client, message):
    if not is_allowed_chat(message.chat.id):
        return await message.reply("⛔ Unauthorized Access.")
    await message.reply("🎬 **Welcome to Ultra Muxer Bot!**\n\nType `/help` to see all my features and commands.")

@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message):
    if not is_allowed_chat(message.chat.id): return
    
    text = (
        "📚 **Bot Commands & Features Guide:**\n\n"
        "🟢 **Muxing (Add Subtitle to Video):**\n"
        "1. Simply ek `MKV` video send karein.\n"
        "2. Bot aapse subtitle mangega, tab `.srt` ya `.ass` send karein.\n"
        "3. Fir file ka naya naam dein ya 'Skip' dabayein.\n"
        "4. **Tabhi** video download start hogi, subtitle ka naam MKV me **'Hinglish'** set ho jayega aur purane subtitles delete ho jayenge.\n\n"
        
        "🟠 **Extract Subtitles (`/extract`):**\n"
        "Kisi bhi Telegram par aayi `MKV` video ko reply karein `/extract` likh kar. Agar usme multiple language (eng, hin, ara) ke subtitle honge toh bot aapko ek list dega, aur aap apna manpasand sub nikal payenge!\n\n"
        
        "🔴 **Admin Commands:**\n"
        "`/addgroup` - Current group ko whitelist karne ke liye.\n"
        "`/removegroup` - Group ko blacklist karne ke liye.\n"
        "`/groups` - Whitelisted groups ki list dekhne ke liye."
    )
    await message.reply(text)
