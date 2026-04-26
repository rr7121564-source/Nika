import math
import time
import asyncio

LANG_MAP = {
    'eng': 'English', 'hin': 'Hindi', 'ara': 'Arabic', 'fre': 'French',
    'fra': 'French', 'ger': 'German', 'deu': 'German', 'ita': 'Italian',
    'jpn': 'Japanese', 'spa': 'Spanish', 'rus': 'Russian', 'chi': 'Chinese',
    'zho': 'Chinese', 'kor': 'Korean', 'tam': 'Tamil', 'tel': 'Telugu',
    'mal': 'Malayalam', 'kan': 'Kannada', 'ben': 'Bengali', 'urd': 'Urdu',
    'tur': 'Turkish', 'por': 'Portuguese', 'ind': 'Indonesian', 'und': 'Unknown'
}

def get_lang_name(code):
    return LANG_MAP.get(code.lower(), code.title())

# Progress bar ko limit karne ke liye (Taaki download stuck na ho)
LAST_UPDATE_TIME = {}

async def edit_msg(message, text):
    """Background task to edit message without blocking Pyrogram download stream."""
    try:
        await message.edit_text(text)
    except Exception:
        pass

def humanbytes(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(math.floor(size * 100) / 100) + " " + Dic_powerN[n] + 'B'

async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    msg_id = message.id
    
    if msg_id not in LAST_UPDATE_TIME:
        LAST_UPDATE_TIME[msg_id] = start
        
    # Sirf har 8 second me ya 100% complete hone par hi update hoga (Download stuck nahi hoga)
    if current == total or (now - LAST_UPDATE_TIME[msg_id] > 8.0):
        LAST_UPDATE_TIME[msg_id] = now
        percentage = current * 100 / total
        speed = current / (now - start) if (now - start) > 0 else 0

        progress_str = f"[{'█' * math.floor(percentage / 5)}{'░' * (20 - math.floor(percentage / 5))}] {round(percentage, 2)}%"
        tmp = progress_str + f"\n\n🚀 **Speed:** {humanbytes(speed)}/s\n✅ **Done:** {humanbytes(current)} / {humanbytes(total)}"
        
        # Async non-blocking execution call
        asyncio.create_task(edit_msg(message, f"⏳ **{ud_type}**\n\n{tmp}"))
        
        if current == total:
            LAST_UPDATE_TIME.pop(msg_id, None)
