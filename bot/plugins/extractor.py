import os
import json
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.auth import is_allowed_chat
from bot.utils import get_lang_name

EXTRACT_DATA = {}

@Client.on_message(filters.command("extract") & filters.private)
async def extract_cmd(client, message):
    if not is_allowed_chat(message.chat.id): return
    
    if not message.reply_to_message or not (message.reply_to_message.video or message.reply_to_message.document):
        return await message.reply("⚠️ Kisi `MKV` file ka reply karke `/extract` command bhejein.")
        
    mkv_msg = message.reply_to_message
    file_name = (mkv_msg.video.file_name if mkv_msg.video else mkv_msg.document.file_name) or "video.mkv"
    if not file_name.lower().endswith('.mkv'):
        return await message.reply("⚠️ Extract karne ke liye sirf `.mkv` file support hoti hai!")
        
    user_id = message.from_user.id
    msg = await message.reply("📥 **Downloading MKV for extraction...**\n_(Kripya intzaar karein)_")
    
    # Download file to local to run ffprobe
    mkv_path = await mkv_msg.download(file_name=f"downloads/ext_{user_id}_{file_name}")
    
    # Run ffprobe to get subtitle streams
    cmd =['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=index,codec_name:stream_tags=language', '-of', 'json', mkv_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    stdout, _ = await proc.communicate()
    
    try:
        streams = json.loads(stdout.decode()).get('streams', [])
    except:
        streams =[]
        
    if not streams:
        os.remove(mkv_path)
        return await msg.edit("❌ Is MKV me koi bhi subtitle stream nahi mili!")

    # Original file ka naam bina extension (.mkv) ke nikalo
    base_name = os.path.splitext(file_name)[0]

    # 🌟 Agar sirf 1 hi subtitle ho, to direct extract and upload
    if len(streams) == 1:
        await msg.edit("⚙️ **Single subtitle found. Extracting automatically...**")
        s = streams[0]
        idx = s['index']
        codec = s.get('codec_name', 'subrip')
        ext = ".ass" if codec == "ass" else ".srt"
        
        # Same naam rakha jayega jo MKV ka tha
        out_file = f"downloads/{base_name}{ext}"
        
        # FFmpeg Extract Command
        ext_cmd =['ffmpeg', '-y', '-i', mkv_path, '-map', f"0:{idx}", '-c:s', 'copy', out_file]
        ext_proc = await asyncio.create_subprocess_exec(*ext_cmd, stderr=asyncio.subprocess.DEVNULL)
        await ext_proc.wait()
        
        if ext_proc.returncode == 0 and os.path.exists(out_file):
            await msg.edit("🚀 **Uploading Extracted Subtitle...**")
            await client.send_document(
                chat_id=message.chat.id,
                document=out_file,
                caption="✅ **Successfully Extracted!**"
            )
            await msg.delete()
            os.remove(out_file)
        else:
            await msg.edit("❌ Extraction failed.")
            
        # Video file ko delete kar do storage bachane ke liye
        if os.path.exists(mkv_path):
            os.remove(mkv_path)
        return

    # 🌟 Agar Multiple Subtitles ho, toh Inline Buttons (List) show karo
    EXTRACT_DATA[user_id] = {'mkv_path': mkv_path, 'streams': {}, 'base_name': base_name}
    buttons =[]
    
    for s in streams:
        idx = s['index']
        codec = s.get('codec_name', 'subrip')
        ext = ".ass" if codec == "ass" else ".srt" 
        
        tags = s.get('tags', {})
        lang_code = tags.get('language', 'und')
        
        # SIRF Language Name aayega (e.g., "Hindi", "English")
        lang_full = get_lang_name(lang_code)
        btn_text = f"{lang_full}" 
        
        # Store stream data
        EXTRACT_DATA[user_id]['streams'][str(idx)] = {'ext': ext}
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"doext_{user_id}_{idx}")])
        
    await msg.edit("📂 **Multiple Subtitles Found!**\nNiche se wo subtitle select karein jise extract karna hai:", reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^doext_"))
async def doext_cb(client, query):
    _, user_id, idx = query.data.split("_")
    user_id = int(user_id)
    if query.from_user.id != user_id: 
        return await query.answer("Ye list aapke liye nahi hai!", show_alert=True)
        
    user_data = EXTRACT_DATA.get(user_id)
    if not user_data or not os.path.exists(user_data['mkv_path']):
        return await query.message.edit_text("❌ File session expired ho gaya ya delete ho gayi. Dobara `/extract` bhejein.")
        
    await query.message.edit_text("⚙️ **Extracting Subtitle...**")
    mkv_path = user_data['mkv_path']
    base_name = user_data['base_name']
    
    stream_info = user_data['streams'].get(str(idx), {'ext': '.srt'})
    out_ext = stream_info['ext']
    
    # 🌟 ISME SIRF MKV KA NAAM HOGA, KOI LANGUAGE ADD NAHI HOGI
    out_file = f"downloads/{base_name}{out_ext}"
    
    # FFmpeg Extract Command
    cmd =['ffmpeg', '-y', '-i', mkv_path, '-map', f"0:{idx}", '-c:s', 'copy', out_file]
    ext_proc = await asyncio.create_subprocess_exec(*cmd, stderr=asyncio.subprocess.DEVNULL)
    await ext_proc.wait()
    
    if ext_proc.returncode == 0 and os.path.exists(out_file):
        await query.message.edit_text("🚀 **Uploading Extracted Subtitle...**")
        await client.send_document(
            chat_id=query.message.chat.id,
            document=out_file,
            caption="✅ **Successfully Extracted!**"
        )
        await query.message.delete()
        os.remove(out_file)
    else:
        await query.message.edit_text("❌ Extraction failed.")
        
    # Cleanup main MKV video
    if os.path.exists(mkv_path):
        os.remove(mkv_path)
    EXTRACT_DATA.pop(user_id, None)
