import os

# Telegram API Credentials (MANDATORY FOR PYROGRAM)
# Apne API_ID aur HASH my.telegram.org se lein
API_ID = int(os.environ.get("API_ID", "26404721"))
API_HASH = os.environ.get("API_HASH", "eda8a9e2d0553424b675368e5f9737c0")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8588606800:AAGDQZpPNCCrCKtslaP-Hp5k_r3ZAj4t5js")

# Owner Setup
OWNER_ID = int(os.environ.get("OWNER_ID", "6751462767"))

# Local Font ka path
LOCAL_FONT_PATH = os.environ.get("LOCAL_FONT_PATH", "fonts/custom_font.ttf")
