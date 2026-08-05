"""
Daemon config – thin wrappers around shared.config
"""

from shared.config import (
    discord_token as DISCORD_TOKEN_FN,
    command_channel_id as COMMAND_CHANNEL_ID_FN,
    load_config,
)

# Eager validate secrets on import
DISCORD_TOKEN = DISCORD_TOKEN_FN()
COMMAND_CHANNEL_ID = COMMAND_CHANNEL_ID_FN()
load_config()
