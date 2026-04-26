import os, time, asyncio, urllib.request, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- 🌐 RENDER HEALTH CHECK BYPASS ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running with Local API!")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    httpd.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# --- ⚙️ CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
LOCAL_API_URL = "http://127.0.0.1:8081/bot"
USER_STATE, EXTRACT_DATA, ACTIVE_TASKS = {}, {}, {}
QUEUE_LOCK = asyncio.Lock()

LANG_MAP = {
    'eng': 'English', 'hin': 'Hindi', 'ara': 'Arabic', 'fre': 'French',
    'ger': 'German', 'ita': 'Italian', 'jpn': 'Japanese', 'spa': 'Spanish',
    'rus': 'Russian', 'chi': 'Chinese', 'kor': 'Korean', 'tam': 'Tamil', 'tel': 'Telugu'
}

def get_lang_name(code):
    return LANG_MAP.get(code.lower(), code.title())

def get_valid_font():
    os.makedirs("fonts", exist_ok=True)
    for file in os.listdir("fonts"):
        if file.lower().endswith(('.ttf', '.otf')):
            return os.path.join("fonts", file)
    fallback = os.path.join("fonts", "Roboto-Regular.ttf")
    if not os.path.exists(fallback):
        urllib.request.urlretrieve("https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf", fallback)
    return fallback

# --- 🎬 MUXING WORKFLOW ---
async def handle_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    if user_id not in USER_STATE: USER_STATE[user_id] = {'state': 'IDLE', 'del_ids': []}
    
    file_obj = msg.video or msg.document
    if not file_obj: return
    file_name = file_obj.file_name.lower() if file_obj.file_name else "file.ext"
    state = USER_STATE[user_id].get('state', 'IDLE')
    
    if file_name.endswith(('.mkv', '.mp4')):
        bot_msg = await msg.reply_text("✅ **MKV Received!**\nNow send the Subtitle file (`.srt` / `.ass`).", parse_mode="Markdown")
        USER_STATE[user_id] = {'state': 'WAIT_SUB', 'mkv_msg': msg, 'mkv_name': file_name, 'del_ids': [msg.message_id, bot_msg.message_id]}
        
    elif file_name.endswith(('.srt', '.ass')):
        if state != 'WAIT_SUB': return await msg.reply_text("⚠️ Please send MKV video first!")
        kbd = InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Skip (Original Name)", callback_data=f"ren_skip_{user_id}")]])
        bot_msg = await msg.reply_text("📝 **Rename File?**\nType new name or click Skip.", reply_markup=kbd, parse_mode="Markdown")
        USER_STATE[user_id].update({'sub_msg': msg, 'sub_name': file_name, 'state': 'WAIT_REN'})
        USER_STATE[user_id]['del_ids'].extend([msg.message_id, bot_msg.message_id])

async def handle_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    if USER_STATE.get(user_id, {}).get('state') == 'WAIT_REN':
        custom_name = msg.text.strip()
        if not custom_name.lower().endswith('.mkv'): custom_name += '.mkv'
        USER_STATE[user_id]['custom_name'] = custom_name
        USER_STATE[user_id]['del_ids'].append(msg.message_id)
        await execute_mux(update, context, user_id)

async def rename_skip_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = int(query.data.split("_")[2])
    if query.from_user.id != user_id: return await query.answer("Not for you!", show_alert=True)
    USER_STATE[user_id]['custom_name'] = USER_STATE[user_id].get('mkv_name', 'output.mkv')
    await query.message.edit_text("⏭️ **Rename Skipped!**")
    await execute_mux(update, context, user_id)

async def execute_mux(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    chat_id = update.effective_chat.id
    data = USER_STATE.pop(user_id, None)
    if not data: return
    
    status = await context.bot.send_message(chat_id, "⚙️ **Muxing via C++ Engine...**", parse_mode="Markdown")
    data['del_ids'].append(status.message_id)
    
    # Fast path capture (Local API)
    mkv_f = await context.bot.get_file((data['mkv_msg'].video or data['mkv_msg'].document).file_id)
    sub_f = await context.bot.get_file(data['sub_msg'].document.file_id)
    out_path = f"/app/data/mux_{user_id}_{data['custom_name']}"
    
    cmd = [
        "ffmpeg", "-y", "-i", mkv_f.file_path, "-i", sub_f.file_path,
        "-map", "0:v", "-map", "0:a?", "-map", "1",
        "-c:v", "copy", "-c:a", "copy", "-c:s", ("ass" if data['sub_name'].endswith('.ass') else "srt"),
        "-disposition:s:0", "default", "-metadata:s:s:0", "title=Hinglish", "-metadata:s:s:0", "language=hin",
        "-attach", get_valid_font(), "-metadata:s:t:0", "mimetype=application/x-truetype-font", out_path
    ]
    
    async with QUEUE_LOCK:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
    
    if proc.returncode == 0:
        await status.edit_text("🚀 **Uploading Muxed MKV...**", parse_mode="Markdown")
        await context.bot.send_document(chat_id, document=f"file://{out_path}", caption=f"✅ **Muxed:** `{data['custom_name']}`", parse_mode="Markdown")
        # --- AUTO CLEANUP ---
        for mid in data['del_ids']:
            try: await context.bot.delete_message(chat_id, mid)
            except: pass
    else:
        await status.edit_text("❌ Muxing Failed.")
    if os.path.exists(out_path): os.remove(out_path)

# --- 📂 EXTRACTION WORKFLOW ---
async def extract_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
        return await msg.reply_text("⚠️ Reply to an MKV file with `/extract`.")
    
    user_id = msg.from_user.id
    target = msg.reply_to_message.video or msg.reply_to_message.document
    if not target.file_name.lower().endswith('.mkv'): return await msg.reply_text("⚠️ Only MKV supported.")
    
    bot_msg = await msg.reply_text("📥 **Scanning Subtitles...**")
    mkv_f = await context.bot.get_file(target.file_id)
    
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=index,codec_name:stream_tags=language,NUMBER_OF_BYTES', '-of', 'json', mkv_f.file_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    stdout, _ = await proc.communicate()
    
    streams = json.loads(stdout.decode()).get('streams', []) if stdout else []
    if not streams: return await bot_msg.edit_text("❌ No subtitles found.")
    
    base_name = os.path.splitext(target.file_name)[0]
    
    # Single Sub Extract
    if len(streams) == 1:
        await bot_msg.edit_text("⚙️ **Extracting Single Subtitle...**")
        idx, codec = streams[0]['index'], streams[0].get('codec_name', 'subrip')
        ext = ".ass" if codec == "ass" else ".srt"
        out = f"/app/data/{base_name}{ext}"
        await asyncio.create_subprocess_exec('ffmpeg', '-y', '-i', mkv_f.file_path, '-map', f"0:{idx}", '-c:s', 'copy', out).wait()
        await context.bot.send_document(msg.chat_id, document=f"file://{out}", caption="✅ **Extracted Successfully!**")
        await bot_msg.delete()
        if os.path.exists(out): os.remove(out)
        return

    # Multi Sub List
    EXTRACT_DATA[user_id] = {'path': mkv_f.file_path, 'name': base_name, 'streams': {}}
    btns = []
    for s in streams:
        idx, codec = s['index'], s.get('codec_name', 'subrip')
        tags = s.get('tags', {})
        lang = get_lang_name(tags.get('language', 'und'))
        size = tags.get('NUMBER_OF_BYTES')
        text = f"{lang}"
        if size:
            kb = int(size)/1024
            text += f" ({kb/1024:.2f} MB)" if kb > 1024 else f" ({kb:.0f} KB)"
        
        EXTRACT_DATA[user_id]['streams'][str(idx)] = ".ass" if codec == "ass" else ".srt"
        btns.append([InlineKeyboardButton(text, callback_data=f"ext_{user_id}_{idx}")])
    
    await bot_msg.edit_text("📂 **Select Language to Extract:**", reply_markup=InlineKeyboardMarkup(btns))

async def do_extract_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, uid, idx = query.data.split("_")
    if query.from_user.id != int(uid): return await query.answer("Access Denied!", show_alert=True)
    
    data = EXTRACT_DATA.get(int(uid))
    if not data: return await query.message.edit_text("❌ Session Expired.")
    
    await query.message.edit_text("⚙️ **Extracting...**")
    ext = data['streams'].get(idx, ".srt")
    out = f"/app/data/{data['name']}{ext}"
    
    await asyncio.create_subprocess_exec('ffmpeg', '-y', '-i', data['path'], '-map', f"0:{idx}", '-c:s', 'copy', out).wait()
    await context.bot.send_document(query.message.chat_id, document=f"file://{out}", caption="✅ **Extracted!**")
    await query.message.delete()
    if os.path.exists(out): os.remove(out)

# --- 🚀 MAIN BOT ENGINE ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎬 **Ultra Muxer Bot is Ready!**\n\n1. Send MKV\n2. Send Subtitle\n3. Rename & Enjoy!")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).base_url(LOCAL_API_URL).local_mode(True).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("extract", extract_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO, handle_files))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rename))
    app.add_handler(CallbackQueryHandler(rename_skip_cb, pattern="^ren_skip_"))
    app.add_handler(CallbackQueryHandler(do_extract_cb, pattern="^ext_"))
    
    print("🚀 Ultra-Fast C++ Local Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
