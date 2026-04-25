import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.auth import is_allowed_chat, is_owner
from bot.ffmpeg_utils import run_muxer
from bot.config import LOCAL_FONT_PATH
from bot.utils import progress_for_pyrogram

USER_DATA = {}
USER_LOCKS = {}
ACTIVE_TASKS = {}
QUEUE_LOCK = asyncio.Lock()

@Client.on_message((filters.video | filters.document) & ~filters.command(["start", "addgroup", "removegroup", "groups"]))
async def process_files(client, message):
    if not is_allowed_chat(message.chat.id):
        return

    user_id = message.from_user.id
    
    if user_id not in USER_LOCKS:
        USER_LOCKS[user_id] = asyncio.Lock()

    if USER_LOCKS[user_id].locked():
        return await message.reply("⏳ You already have a task running. Please wait!")

    async with USER_LOCKS[user_id]:
        file_name = ""
        if message.video:
            file_name = message.video.file_name or "video.mkv"
        elif message.document:
            file_name = message.document.file_name or "file.ext"
        
        file_name = file_name.lower()

        # Step 1: Handle MKV Video
        if file_name.endswith(('.mkv', '.mp4')):
            msg = await message.reply("📥 **Downloading MKV Video...**")
            start_time = time.time()
            
            video_path = await message.download(
                file_name=f"downloads/{message.id}_{file_name}",
                progress=progress_for_pyrogram,
                progress_args=("Downloading Video...", msg, start_time)
            )
            
            if user_id not in USER_DATA:
                USER_DATA[user_id] = {}
            USER_DATA[user_id]['video'] = video_path
            await msg.edit("✅ **Video Downloaded!**\n\nNow send the Subtitle File (`.srt` or `.ass`).")

        # Step 2: Handle Subtitle
        elif file_name.endswith(('.srt', '.ass')):
            if user_id not in USER_DATA or 'video' not in USER_DATA[user_id]:
                return await message.reply("⚠️ Please send the **MKV Video** FIRST.")

            # Check Font
            if not os.path.exists(LOCAL_FONT_PATH):
                return await message.reply(f"❌ **Font Missing!** Path: `{LOCAL_FONT_PATH}`")

            cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel Task", callback_data=f"cancel_{user_id}")]])
            msg = await message.reply("📥 **Downloading Subtitle...**", reply_markup=cancel_markup)
            
            sub_path = await message.download(file_name=f"downloads/{message.id}_{file_name}")
            
            video_path = USER_DATA[user_id]['video']
            output_path = f"downloads/muxed_{user_id}_{os.path.basename(video_path)}"

            try:
                # Step 3: Muxing (Queue Management)
                await msg.edit("⚙️ **Waiting in Queue...**", reply_markup=cancel_markup)
                async with QUEUE_LOCK:
                    await msg.edit("⚙️ **Muxing Started...**", reply_markup=cancel_markup)
                    task = asyncio.create_task(run_muxer(video_path, sub_path, LOCAL_FONT_PATH, output_path, msg, user_id, ACTIVE_TASKS))
                    await task
                
                # Step 4: Uploading Output
                start_time = time.time()
                await msg.edit("🚀 **Uploading Processed MKV...**")
                await client.send_document(
                    chat_id=message.chat.id,
                    document=output_path,
                    caption="✅ **File Successfully Muxed!**\n- Old subs deleted\n- New sub is Default\n- Font Attached.",
                    progress=progress_for_pyrogram,
                    progress_args=("Uploading Video...", msg, start_time)
                )
                await msg.delete()
                
            except asyncio.CancelledError:
                await msg.edit("❌ **Task Cancelled by User.**")
            except Exception as e:
                await msg.edit(f"⚠️ **Error occurred:** `{str(e)}`")
            finally:
                # Guaranteed Cleanup
                USER_DATA.pop(user_id, None)
                ACTIVE_TASKS.pop(user_id, None)
                for p in[video_path, sub_path, output_path]:
                    if p and os.path.exists(p):
                        try: os.remove(p)
                        except: pass
        else:
            await message.reply("⚠️ Unsupported file format. Send MKV, SRT, or ASS.")

@Client.on_callback_query(filters.regex(r"^cancel_"))
async def cancel_cb(client, query):
    user_id = int(query.data.split("_")[1])
    if query.from_user.id != user_id and not is_owner(query.from_user.id):
        return await query.answer("You cannot cancel this task!", show_alert=True)
    
    process = ACTIVE_TASKS.get(user_id)
    if process:
        process.kill()
        await query.answer("Task Killed!", show_alert=True)
    else:
        await query.answer("No active task found.", show_alert=True)
