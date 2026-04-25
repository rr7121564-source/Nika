import math
import time

async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
    if round(diff % 5.00) == 0 or current == total: # Update every 5 seconds to prevent rate limit
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
        estimated_total_time = elapsed_time + time_to_completion

        # Convert sizes to readable format
        def humanbytes(size):
            if not size: return "0 B"
            power = 2**10
            n = 0
            Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
            while size > power:
                size /= power
                n += 1
            return str(math.floor(size * 100) / 100) + " " + Dic_powerN[n] + 'B'

        progress_str = f"[{'█' * math.floor(percentage / 5)}{'░' * (20 - math.floor(percentage / 5))}] {round(percentage, 2)}%"
        tmp = progress_str + f"\n\n🚀 **Speed:** {humanbytes(speed)}/s\n" \
              f"✅ **Done:** {humanbytes(current)} / {humanbytes(total)}"
        
        try:
            await message.edit_text(f"⏳ **{ud_type}**\n\n{tmp}")
        except:
            pass
