"""
Chronos Daemon – watches Discord, approves, executes.
"""

from __future__ import annotations

import asyncio
import signal
import time
import traceback
from datetime import datetime, timezone

import discord

from daemon.config import DISCORD_TOKEN, COMMAND_CHANNEL_ID
from daemon.approval import request_approval
from daemon.executor import run_command
from daemon.luks import unlock_luks
from daemon.logger import log_event, export_recent
from daemon.inputsim import simulate_input
from daemon.mouse import simulate_mouse
from daemon.history import record as history_record, recent as history_recent, last_command
from daemon.security import (
    is_locked,
    is_alarm,
    set_locked,
    set_alarm,
    alarm_reason,
    check_rate_limit,
    commands_blocked,
    check_lock_password,
    command_allowed_by_policy,
    is_sudomode,
    set_sudomode,
    sudomode_remaining,
    SUDOMODE_TTL,
)
from daemon.screenshot import take_screenshot
from shared.protocol import parse_command, format_alias_list, format_help
from shared.aliases import load_aliases
from shared.config import (
    load_config,
    max_output_chars,
    allowed_command_user_ids,
    whitelist_enabled,
    luks_enabled,
    luks_device,
    luks_mapper_name,
    rate_limit_enabled,
    rate_limit_max,
    rate_limit_window,
    audit_channel_id,
    execution_mode,
    history_enabled,
    command_prefix,
)

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

_unlock_fail_until: dict[int, float] = {}
_shutting_down = False


def _chunk_text(text: str, limit: int) -> list[str]:
    if not text:
        return []
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


def _safe_code_block(text: str) -> str:
    if not text:
        return ""
    return text.replace("```", "``\u200b`")


async def _send_output(message: discord.Message, returncode: int, stdout: str, stderr: str):
    limit = max_output_chars()
    await message.reply(f"**Exit code:** `{returncode}`")

    if stdout:
        for i, chunk in enumerate(_chunk_text(stdout, limit)):
            label = "**stdout:**" if i == 0 else f"**stdout (cont. {i + 1}):**"
            safe = _safe_code_block(chunk)
            await message.reply(f"{label}\n```\n{safe}\n```")

    if stderr:
        for i, chunk in enumerate(_chunk_text(stderr, limit)):
            label = "**stderr:**" if i == 0 else f"**stderr (cont. {i + 1}):**"
            safe = _safe_code_block(chunk)
            await message.reply(f"{label}\n```\n{safe}\n```")

    if not stdout and not stderr:
        await message.reply("_No output_")
