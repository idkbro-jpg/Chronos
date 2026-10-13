"""
Chronos Daemon – watches Discord, approves, executes.

One gateway connection. Prefer running only this process (not bot/ + daemon
with the same token at once).
"""

from __future__ import annotations

import asyncio
import signal
import time
from pathlib import Path

import discord

from daemon.approval import request_approval
from daemon.config import COMMAND_CHANNEL_ID, DISCORD_TOKEN
from daemon.executor import run_command
from daemon import history
from daemon.inputsim import simulate_input
from daemon.logger import export_recent, log_event
from daemon.luks import unlock_luks
from daemon.mouse import simulate_mouse
from daemon.screenshot import take_screenshot
from daemon.sysinfo import gather_sysinfo
from daemon.security import (
    check_lock_password,
    check_rate_limit,
    command_allowed_by_policy,
    commands_blocked,
    is_alarm,
    is_locked,
    is_sudomode,
    set_alarm,
    set_locked,
    set_sudomode,
    sudomode_remaining,
    alarm_reason,
)
from shared.aliases import load_aliases
from shared.config import (
    allowed_command_user_ids,
    audit_channel_id,
    load_config,
    max_output_chars,
    max_output_chunks,
    whitelist_enabled,
)
from shared.discord_utils import fit_discord_message, format_exec_replies, safe_inline
from shared.permissions import (
    get_user_effective_permissions,
    has_permission,
    list_ranks,
    list_special_permissions,
    load_permissions,
    save_permissions,
)
from shared.protocol import format_alias_list, format_help, parse_command

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # needed for role-based permissions
intents.reactions = True

client = discord.Client(intents=intents)

_start_time = time.time()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_whitelisted(user_id: int) -> bool:
    if not whitelist_enabled():
        return True
    allowed = allowed_command_user_ids()
    return user_id in allowed


async def _safe_reply(message: discord.Message, content: str) -> None:
    try:
        await message.reply(fit_discord_message(content), mention_author=False)
    except discord.HTTPException:
        try:
            await message.channel.send(fit_discord_message(content))
        except discord.HTTPException:
            pass


async def _send_chunks(channel: discord.abc.Messageable, replies: list[str]) -> None:
    for text in replies:
        try:
            await channel.send(fit_discord_message(text))
        except discord.HTTPException:
            pass


async def _maybe_audit(text: str) -> None:
    cid = audit_channel_id()
    if not cid:
        return
    ch = client.get_channel(cid)
    if ch is None:
        try:
            ch = await client.fetch_channel(cid)
        except Exception:
            return
    try:
        await ch.send(fit_discord_message(text))
    except Exception:
        pass


def _needs_approval(cmd_token: str) -> bool:
    """Built-ins that are informational never need approval."""
    no_approval = {
        "__HELP__",
        "__PING__",
        "__STATUS__",
        "__SYSINFO__",
        "__LIST_ALIASES__",
        "__ALARM_STATUS__",
        "__HISTORY__",
        "__LAST__",
        "__PERM__",
        "__UNLOCK__",  # just prints how-to
    }
    if cmd_token in no_approval or cmd_token.startswith("__PERM__"):
        return False
    if is_sudomode():
        return False
    return True
