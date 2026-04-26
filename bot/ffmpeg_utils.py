import os
import time
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def get_duration(file_path):
    cmd =['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    stdout, _ = await proc.communicate()
    try: return float(stdout.decode().strip())
    except ValueError: return 0.0

async def run_muxer(video_path: str, sub_path: str, font_path: str, output_path: str, message, user_id, active_tasks):
    sub_ext = sub_path.split('.')[-1].lower()
    sub_codec = "ass" if sub_ext == "ass" else "srt"
    duration = await get_duration(video_path)
    
    os.makedirs("fonts", exist_ok=True)
    fonts_dir = "fonts"
    font_args =[]
    font_index = 0

    for font_file in os.listdir(fonts_dir):
        f_path = os.path.join(fonts_dir, font_file)
        ext = os.path.splitext(font_file)[1].lower()
        mimetype = "application/x-truetype-font" if ext in['.ttf', '.ttc'] else "application/vnd.ms-opentype" if ext == '.otf' else ""
        if mimetype:
            font_args.extend(["-attach", f_path, f"-metadata:s:t:{font_index}", f"mimetype={mimetype}"])
            font_index += 1

    if not font_args and os.path.exists(font_path):
        font_args.extend(["-attach", font_path, "-metadata:s:t:0", "mimetype=application/x-truetype-font"])

    # 🌟 MAGIC: -metadata:s:s:0 title=Hinglish is added here
    cmd =[
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", sub_path,
        "-map", "0:v", "-map", "0:a", "-map", "1",
        "-c:v", "copy", "-c:a", "copy",
        "-c:s", sub_codec,
        "-disposition:s:0", "default",
        "-metadata:s:s:0", "title=Hinglish",
        "-metadata:s:s:0", "language=hin"
    ] + font_args +["-progress", "pipe:1", output_path]

    process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    active_tasks[user_id] = process
    start_time = time.time()
    last_update = start_time
    speed = "N/A"
    
    cancel_kbd = InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel Task", callback_data=f"cancel_{user_id}")]])

    try:
        while True:
            line = await process.stdout.readline()
            if not line: break
            line = line.decode('utf-8').strip()

            if line.startswith('speed='): speed = line.split('=')[1]
            if line.startswith('out_time_us='):
                out_time_us = line.split('=')[1]
                if out_time_us.isdigit() and duration > 0:
                    current_time = int(out_time_us) / 1000000
                    percentage = min(100, (current_time / duration) * 100)
                    now = time.time()
                    
                    if now - last_update > 3:
                        last_update = now
                        elapsed = now - start_time
                        eta_secs = (elapsed / percentage) * (100 - percentage) if percentage > 0 else 0
                        eta_str = time.strftime('%H:%M:%S', time.gmtime(eta_secs)) if percentage > 0 else "Calculating..."
                        
                        filled = int(percentage / 5)
                        bar = f"[{'█' * filled}{'░' * (20 - filled)}]"
                        
                        text = (f"⚙️ **Muxing MKV...**\n\n**Progress:** `{percentage:.2f}%`\n`{bar}`\n\n"
                                f"🚀 **Speed:** `{speed}`\n⏳ **ETA:** `{eta_str}`\n\n"
                                f"✅ _Old subs deleted | Muxed as 'Hinglish'_")
                        try: await message.edit_text(text, reply_markup=cancel_kbd, parse_mode='Markdown')
                        except: pass

        await process.wait()
    except asyncio.CancelledError:
        process.kill()
        raise

    if process.returncode != 0:
        raise Exception("FFmpeg failed to process the file.")
