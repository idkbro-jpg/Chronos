import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_CHANNEL_ID = int(os.getenv("COMMAND_CHANNEL_ID", "0"))
ALLOWED_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip().isdigit()
]
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is missing in .env")
if COMMAND_CHANNEL_ID == 0:
    raise ValueError("COMMAND_CHANNEL_ID is missing in .env")
