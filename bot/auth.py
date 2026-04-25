from bot.config import OWNER_ID

ALLOWED_GROUPS = set()

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_allowed_chat(chat_id: int) -> bool:
    if chat_id == OWNER_ID:
        return True
    return chat_id in ALLOWED_GROUPS
