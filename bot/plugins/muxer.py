import os
import time
import asyncio
import urllib.request
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.auth import is_allowed_chat, is_owner
from bot.ffmpeg_utils import run_muxer
from bot.utils import progress_for_pyrogram

USER_STATE = {}
USER_LOCKS = {}
ACTIVE_TASKS = {}
QUEUE_LOCK = asyncio.Lock()

def get_valid_font():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    font_dir = os.path.join(base_dir, "fonts")
    os.makedirs(font_dir, exist_ok=True)
    for file in os.listdir(font_dir):
        if file.lower().endswith(('.ttf', '.otf')):
            return os.path.join(font_dir, file)
    fallback = os.path.join(font_dir, "Roboto-Regular.ttf")
    if not os.path.exists(fallback):
        urllib.request.urlretrieve("https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf", fallback)
    return fallback

@Client.on_message((filters.video | filters.document) & filters.private & ~filters.command(["start", "help", "extract", "addgroup", "removegroup", "groups"]))
async def handle_files(client, message):
    if not is_allowed_chat(message.chat.id): return
    
    user_id = message.from_user.id
    if user_id not in USER_STATE: USER_STATE[user_id] = {'state': 'IDLE', 'delete_ids':[]}

    file_name = (message.video.file_name if message.video else message.document.file_name) or "file.ext"
    file_name = file_name.lower()
    state = USER_STATE[user_id].get('state', 'IDLE')

    if file_name.endswith(('.mkv', '.mp4')):
        bot_msg = await message.reply("✅ **MKV File Received!**\n\nAb isme add karne ke liye Subtitle file (`.srt` ya `.ass`) send karein.")
        USER_STATE[user_id] = {
            'state': 'WAIT_SUB', 'mkv_msg': message, 'mkv_name': file_name,
            'delete_ids':[message.id, bot_msg.id] # 🌟 Pura track rakh raha hai ID's ka
        }

    elif file_name.endswith(('.srt', '.ass')):
        if state != 'WAIT_SUB' or 'mkv_msg' not in USER_STATE[user_id]:
            return await message.reply("⚠️ Pehle MKV Video send karein, uske baad subtitle!")
        
        kbd = InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Skip (Keep Original Name)", callback_data=f"rename_skip_{user_id}")]])
        bot_msg = await message.reply("📝 **Rename MKV File:**\n\nAgar aapko naya naam rakhna hai, toh abhi type karke send karein. \n(Ya fir wahi naam rakhne ke liye 'Skip' button dabayein).", reply_markup=kbd)
        
        USER_STATE[user_id]['sub_msg'] = message
        USER_STATE[user_id]['sub_name'] = file_name
        USER_STATE[user_id]['state'] = 'WAIT_RENAME'
        USER_STATE[user_id]['delete_ids'].extend([message.id, bot_msg.id])

@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "extract", "addgroup", "removegroup", "groups"]))
async def handle_rename(client, message):
    user_id = message.from_user.id
    if user_id in USER_STATE and USER_STATE[user_id].get('state') == 'WAIT_RENAME':
        custom_name = message.text.strip()
        custom_name = os.path.basename(custom_name)
        if not custom_name.lower().endswith('.mkv'): custom_name += '.mkv'
            
        bot_msg = await message.reply(f"✅ Naam Set: `{custom_name}`")
        USER_STATE[user_id]['custom_name'] = custom_name
        USER_STATE[user_id]['delete_ids'].extend([message.id, bot_msg.id])
        await process_muxing_workflow(client, message, user_id)

@Client.on_callback_query(filters.regex(r"^rename_skip_"))
async def rename_skip_cb(client, query):
    user_id = int(query.data.split("_")[2])
    if query.from_user.id != user_id: return await query.answer("Not for you!", show_alert=True)
    
    await query.message.edit_text("⏭️ **Rename Skipped!** Original naam hi use hoga.")
    USER_STATE[user_id]['custom_name'] = USER_STATE[user_id].get('mkv_name', 'output.mkv')
    await process_muxing_workflow(client, query.message, user_id)

async def process_muxing_workflow(client, message, user_id):
    if user_id not in USER_LOCKS: USER_LOCKS[user_id] = asyncio.Lock()
    if USER_LOCKS[user_id].locked():
        return await message.reply("⏳ You already have a task running. Please wait!")

    async with USER_LOCKS[user_id]:
        data = USER_STATE.pop(user_id, None)
        if not data: return
        
        mkv_msg, sub_msg, final_name = data['mkv_msg'], data['sub_msg'], data['custom_name']
        ids_to_delete = data.get('delete_ids',[])
        
        font_path = get_valid_font()
        msg = await message.reply("📥 **Downloading MKV Video...**")
        ids_to_delete.append(msg.id) # Add progress message ID to delete list
        
        start_time = time.time()
        video_path = await mkv_msg.download(file_name=f"downloads/{mkv_msg.id}_video.mkv", progress=progress_for_pyrogram, progress_args=("Downloading Video...", msg, start_time))
        
        await msg.edit("📥 **Downloading Subtitle...**")
        sub_path = await sub_msg.download(file_name=f"downloads/{sub_msg.id}_{data['sub_name']}")
        
        output_path = f"downloads/{user_id}_{final_name}"
        cancel_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel Task", callback_data=f"cancel_{user_id}")]])
        
        try:
            await msg.edit("⚙️ **Waiting in Queue...**")
            async with QUEUE_LOCK:
                await msg.edit("⚙️ **Muxing Started...**", reply_markup=cancel_markup)
                task = asyncio.create_task(run_muxer(video_path, sub_path, font_path, output_path, msg, user_id, ACTIVE_TASKS))
                await task
            
            start_time = time.time()
            await msg.edit("🚀 **Uploading Processed MKV...**")
            await client.send_document(
                chat_id=message.chat.id,
                document=output_path,
                caption=f"✅ **Muxed Successfully!**\n📁 File: `{final_name}`\n- Old Subs: Removed\n- New Sub: Hinglish (Default)",
                progress=progress_for_pyrogram,
                progress_args=("Uploading Video...", msg, start_time)
            )
            
            # 🌟 CLEANUP COMMAND: Saari purani history aur bot commands yahan ek sath delete honge
            try:
                await client.delete_messages(chat_id=message.chat.id, message_ids=list(set(ids_to_delete)))
            except: pass
            
        except asyncio.CancelledError:
            await msg.edit("❌ **Task Cancelled by User.**")
        except Exception as e:
            await msg.edit(f"⚠️ **Error:** `{str(e)}`")
        finally:
            ACTIVE_TASKS.pop(user_id, None)
            for p in [video_path, sub_path, output_path]:
                if p and os.path.exists(p):
                    try: os.remove(p)
                    except: pass

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
