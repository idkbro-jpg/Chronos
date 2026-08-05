"""
Bot config – thin wrappers around shared.config
"""

from shared.config import (
    discord_token as DISCORD_TOKEN_FN,
    command_channel_id as COMMAND_CHANNEL_ID_FN,
    command_prefix as COMMAND_PREFIX_FN,
    allowed_command_user_ids as ALLOWED_USER_IDS_FN,
    load_config,
)

DISCORD_TOKEN = DISCORD_TOKEN_FN()
COMMAND_CHANNEL_ID = COMMAND_CHANNEL_ID_FN()
COMMAND_PREFIX = COMMAND_PREFIX_FN()
ALLOWED_USER_IDS = ALLOWED_USER_IDS_FN()
load_config()
