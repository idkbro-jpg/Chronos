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
from shared.discord_utils import format_exec_replies, fit_discord_message
from shared.config import (
    load_config,
    max_output_chars,
    max_output_chunks,
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

_UNLOCK_FAIL_COOLDOWN = 15.0


def _prune_unlock_fails(now: float | None = None) -> None:
    """Drop expired per-user cooldowns so the dict cannot grow forever."""
    now = time.time() if now is None else now
    stale = [uid for uid, until in _unlock_fail_until.items() if until <= now]
    for uid in stale:
        _unlock_fail_until.pop(uid, None)


async def _send_output(message: discord.Message, returncode: int, stdout: str, stderr: str):
    replies = format_exec_replies(
        returncode,
        stdout,
        stderr,
        max_output_chars(),
        max_output_chunks(),
    )
    for text in replies:
        await message.reply(text)


def _user_allowed(uid: int) -> bool:
    if not whitelist_enabled():
        return True
    return uid in allowed_command_user_ids()
