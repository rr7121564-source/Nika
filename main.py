import os, time, asyncio, urllib.request, json, math
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Credentials (Environment variables me set karein)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
LOCAL_API_URL = "http://127.0.0.1:8081/bot" # C++ Server Local path

USER_STATE, EXTRACT_DATA, ACTIVE_TASKS = {}, {}, {}
QUEUE_LOCK = asyncio.Lock()

LANG_MAP = {
    'eng': 'English', 'hin': 'Hindi', 'ara': 'Arabic', 'fre': 'French',
    'ger': 'German', 'ita': 'Italian', 'jpn': 'Japanese', 'spa': 'Spanish',
    'rus': 'Russian', 'chi': 'Chinese', 'kor': 'Korean', 'tam': 'Tamil'
}

def get_valid_font():
    os.makedirs("fonts", exist_ok=True)
    for file in os.listdir("fonts"):
        if file.lower().endswith(('.ttf', '.otf')):
            return os.path.join("fonts", file)
    fallback = os.path.join("fonts", "Roboto-Regular.ttf")
    if not os.path.exists(fallback):
        urllib.request.urlretrieve("https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf", fallback)
    return fallback

# =======================[ MUXING ENGINE ] =======================
async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    if user_id not in USER_STATE: USER_STATE[user_id] = {'state': 'IDLE', 'del_ids':[]}
    
    file_obj = msg.video or msg.document
    file_name = file_obj.file_name.lower() if file_obj.file_name else "video.ext"
    state = USER_STATE[user_id].get('state', 'IDLE')
    
    if file_name.endswith(('.mkv', '.mp4')):
        bot_msg = await msg.reply_text("✅ **MKV File Received!**\nAb Subtitle file (`.srt` / `.ass`) send karein.", parse_mode="Markdown")
        USER_STATE[user_id] = {'state': 'WAIT_SUB', 'mkv_msg': msg, 'mkv_name': file_name, 'del_ids':[msg.message_id, bot_msg.message_id]}
        
    elif file_name.endswith(('.srt', '.ass')):
        if state != 'WAIT_SUB': return await msg.reply_text("⚠️ Pehle MKV Video bhejein!")
        kbd = InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Skip (Keep Original)", callback_data=f"ren_skip_{user_id}")]])
        bot_msg = await msg.reply_text("📝 **Rename MKV File:**\nNaya naam type karein ya 'Skip' dabayein.", reply_markup=kbd)
        
        USER_STATE[user_id].update({'sub_msg': msg, 'sub_name': file_name, 'state': 'WAIT_REN'})
        USER_STATE[user_id]['del_ids'].extend([msg.message_id, bot_msg.message_id])

async def handle_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    if USER_STATE.get(user_id, {}).get('state') == 'WAIT_REN':
        custom_name = msg.text.strip()
        if not custom_name.lower().endswith('.mkv'): custom_name += '.mkv'
        bot_msg = await msg.reply_text(f"✅ Naam Set: `{custom_name}`", parse_mode="Markdown")
        USER_STATE[user_id]['custom_name'] = custom_name
        USER_STATE[user_id]['del_ids'].extend([msg.message_id, bot_msg.message_id])
        await execute_mux(update, context, user_id)

async def rename_skip_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = int(query.data.split("_")[2])
    if query.from_user.id != user_id: return await query.answer("Not for you!", show_alert=True)
    await query.message.edit_text("⏭️ **Rename Skipped!**")
    USER_STATE[user_id]['custom_name'] = USER_STATE[user_id].get('mkv_name', 'output.mkv')
    await execute_mux(update, context, user_id)

async def execute_mux(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    chat_id = update.effective_chat.id
    data = USER_STATE.pop(user_id, None)
    if not data: return
    
    msg = await context.bot.send_message(chat_id, "⚙️ **Processing via C++ Local Engine...**", parse_mode="Markdown")
    data['del_ids'].append(msg.message_id)
    
    # ⚡ ZERO-SECOND DOWNLOAD (Local API instantly provides the file path)
    mkv_file = await context.bot.get_file((data['mkv_msg'].video or data['mkv_msg'].document).file_id)
    sub_file = await context.bot.get_file(data['sub_msg'].document.file_id)
    mkv_path, sub_path = mkv_file.file_path, sub_file.file_path
    
    output_path = f"/app/data/muxed_{user_id}_{data['custom_name']}"
    sub_ext = data['sub_name'].split('.')[-1]
    
    # FFmpeg Muxing 
    cmd =[
        "ffmpeg", "-y", "-i", mkv_path, "-i", sub_path,
        "-map", "0:v", "-map", "0:a?", "-map", "1", # ? removes audio errors
        "-c:v", "copy", "-c:a", "copy", "-c:s", "ass" if sub_ext == "ass" else "srt",
        "-disposition:s:0", "default", "-metadata:s:s:0", "title=Hinglish", "-metadata:s:s:0", "language=hin",
        "-attach", get_valid_font(), "-metadata:s:t:0", "mimetype=application/x-truetype-font", output_path
    ]
    
    async with QUEUE_LOCK:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
    
    if proc.returncode == 0:
        await msg.edit_text("🚀 **Uploading to Telegram Cloud (50MB/s)...**", parse_mode="Markdown")
        await context.bot.send_document(chat_id, document=f"file://{output_path}", caption="✅ **Muxed Successfully!**")
        
        # 🧹 AUTO CLEANUP OF ALL OLD MESSAGES
        for mid in set(data['del_ids']):
            try: await context.bot.delete_message(chat_id, mid)
            except: pass
    else:
        await msg.edit_text("❌ FFmpeg Muxing Failed.")
    
    if os.path.exists(output_path): os.remove(output_path)

# ======================= [ EXTRACT ENGINE ] =======================
async def extract_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
        return await msg.reply_text("⚠️ Kisi MKV file ka reply karke `/extract` bhejein.")
        
    user_id = msg.from_user.id
    file_obj = msg.reply_to_message.video or msg.reply_to_message.document
    base_name = os.path.splitext(file_obj.file_name or "video")[0]
    
    bot_msg = await msg.reply_text("📥 **Scanning MKV...**")
    
    # ⚡ ZERO-SECOND DOWNLOAD
    mkv_file = await context.bot.get_file(file_obj.file_id)
    mkv_path = mkv_file.file_path
    
    cmd =['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=index,codec_name:stream_tags=language,NUMBER_OF_BYTES', '-of', 'json', mkv_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    stdout, _ = await proc.communicate()
    
    streams = json.loads(stdout.decode()).get('streams', []) if stdout else[]
    if not streams: return await bot_msg.edit_text("❌ Is MKV me koi Subtitle nahi hai.")
    
    # Single Subtitle Bypass
    if len(streams) == 1:
        await bot_msg.edit_text("⚙️ **Single Subtitle Found. Extracting...**")
        idx, codec = streams[0]['index'], streams[0].get('codec_name', 'subrip')
        ext = ".ass" if codec == "ass" else ".srt"
        out_file = f"/app/data/{base_name}{ext}"
        
        await asyncio.create_subprocess_exec('ffmpeg', '-y', '-i', mkv_path, '-map', f"0:{idx}", '-c:s', 'copy', out_file, stderr=asyncio.subprocess.DEVNULL).wait()
        await bot_msg.edit_text("🚀 **Uploading Extracted Subtitle...**")
        await context.bot.send_document(msg.chat_id, document=f"file://{out_file}")
        await bot_msg.delete()
        if os.path.exists(out_file): os.remove(out_file)
        return

    # Multiple Subtitles UI
    EXTRACT_DATA[user_id] = {'mkv_path': mkv_path, 'base_name': base_name, 'streams': {}}
    buttons =[]
    for s in streams:
        idx, codec = s['index'], s.get('codec_name', 'subrip')
        lang_code = s.get('tags', {}).get('language', 'und')
        size_bytes = s.get('tags', {}).get('NUMBER_OF_BYTES')
        
        lang_full = LANG_MAP.get(lang_code.lower(), lang_code.title())
        btn_text = f"{lang_full}"
        if size_bytes and size_bytes.isdigit():
            skb = int(size_bytes)/1024
            btn_text += f" ({skb/1024:.2f} MB)" if skb > 1024 else f" ({skb:.0f} KB)"
            
        EXTRACT_DATA[user_id]['streams'][str(idx)] = ".ass" if codec == "ass" else ".srt"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"ext_{user_id}_{idx}")])
        
    await bot_msg.edit_text("📂 **Select Subtitle to Extract:**", reply_markup=InlineKeyboardMarkup(buttons))

async def doext_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, user_id, idx = query.data.split("_")
    if query.from_user.id != int(user_id): return await query.answer("Not for you!", show_alert=True)
    
    data = EXTRACT_DATA.get(int(user_id))
    if not data: return await query.message.edit_text("❌ Session expired.")
    
    await query.message.edit_text("⚙️ **Extracting...**")
    out_ext = data['streams'].get(idx, ".srt")
    out_file = f"/app/data/{data['base_name']}{out_ext}"
    
    await asyncio.create_subprocess_exec('ffmpeg', '-y', '-i', data['mkv_path'], '-map', f"0:{idx}", '-c:s', 'copy', out_file, stderr=asyncio.subprocess.DEVNULL).wait()
    
    await query.message.edit_text("🚀 **Uploading Extracted Subtitle...**")
    await context.bot.send_document(query.message.chat_id, document=f"file://{out_file}")
    await query.message.delete()
    if os.path.exists(out_file): os.remove(out_file)

# ======================= [ MAIN ] =======================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).base_url(LOCAL_API_URL).local_mode(True).build()
    
    app.add_handler(CommandHandler("extract", extract_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO, handle_files))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rename))
    app.add_handler(CallbackQueryHandler(rename_skip_cb, pattern="^ren_skip_"))
    app.add_handler(CallbackQueryHandler(doext_cb, pattern="^ext_"))
    
    print("🚀 Ultra-Fast C++ Core Bot is Running!")
    app.run_polling()

if __name__ == "__main__":
    main()
