from pyrogram import Client, filters
from bot.auth import is_owner, ALLOWED_GROUPS

@Client.on_message(filters.command("addgroup"))
async def add_group(client, message):
    if not is_owner(message.from_user.id):
        return await message.reply("⛔ You are not the bot owner.")
    
    chat_id = message.chat.id
    ALLOWED_GROUPS.add(chat_id)
    await message.reply(f"✅ Group {chat_id} added to Whitelist!")

@Client.on_message(filters.command("removegroup"))
async def remove_group(client, message):
    if not is_owner(message.from_user.id):
        return await message.reply("⛔ You are not the bot owner.")
    
    chat_id = message.chat.id
    if chat_id in ALLOWED_GROUPS:
        ALLOWED_GROUPS.remove(chat_id)
        await message.reply(f"❌ Group {chat_id} removed from Whitelist!")
    else:
        await message.reply("Group is not in whitelist.")

@Client.on_message(filters.command("groups"))
async def groups(client, message):
    if not is_owner(message.from_user.id):
        return
    await message.reply(f"📁 **Allowed Groups:**\n`{list(ALLOWED_GROUPS)}`")
