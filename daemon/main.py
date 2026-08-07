"""
Chronos Daemon – watches Discord, approves, executes.
"""

from __future__ import annotations

import asyncio

import discord

from daemon.config import DISCORD_TOKEN, COMMAND_CHANNEL_ID
from daemon.approval import request_approval
from daemon.executor import run_command
from daemon.luks import unlock_luks
from daemon.logger import log_event, export_recent
from daemon.security import (
    is_locked,
    is_alarm,
    set_locked,
    set_alarm,
    alarm_reason,
    check_rate_limit,
    commands_blocked,
    check_lock_password,
)
from daemon.screenshot import take_screenshot
from shared.protocol import parse_command, format_alias_list
from shared.aliases import load_aliases
from shared.config import (
    load_config,
    max_output_chars,
    allowed_command_user_ids,
    whitelist_enabled,
    luks_enabled,
    luks_device,
    luks_mapper_name,
)

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.dm_messages = True

client = discord.Client(intents=intents)


def _chunk_text(text: str, limit: int) -> list[str]:
    if not text:
        return []
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


async def _send_output(message: discord.Message, returncode: int, stdout: str, stderr: str):
    limit = max_output_chars()
    await message.reply(f"**Exit code:** `{returncode}`")

    if stdout:
        for i, chunk in enumerate(_chunk_text(stdout, limit)):
            label = "**stdout:**" if i == 0 else f"**stdout (cont. {i + 1}):**"
            await message.reply(f"{label}\n```\n{chunk}\n```")

    if stderr:
        for i, chunk in enumerate(_chunk_text(stderr, limit)):
            label = "**stderr:**" if i == 0 else f"**stderr (cont. {i + 1}):**"
            await message.reply(f"{label}\n```\n{chunk}\n```")

    if not stdout and not stderr:
        await message.reply("_No output_")


async def _handle_luks_unlock(message: discord.Message):
    summary = f"LUKS unlock device=`{luks_device()}` → mapper=`{luks_mapper_name()}`"
    approved = await request_approval(message, summary, client)
    if not approved:
        return
    await message.add_reaction("🔓")
    ok, msg = await asyncio.to_thread(unlock_luks)
    await message.reply(f"{'🔓 **Success**' if ok else '🔒 **Failed**'}\n{msg}")


@client.event
async def on_ready():
    load_config(force=True)
    load_aliases(force=True)
    print(f"[Daemon] Logged in as {client.user} (ID: {client.user.id})")
    print(f"[Daemon] Watching channel ID: {COMMAND_CHANNEL_ID}")
    print(f"[Daemon] lock={is_locked()} alarm={is_alarm()} luks={luks_enabled()}")
    print("[Daemon] Ready.")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    # --- DM path: only for unlock <password> ---
    if isinstance(message.channel, discord.DMChannel):
        content = message.content.strip()
        low = content.lower()
        if low.startswith("unlock ") or low.startswith("!unlock "):
            pw = content.split(None, 1)[1] if " " in content else ""
            if check_lock_password(pw):
                set_locked(False)
                set_alarm(False)
                log_event("unlock_ok", user_id=message.author.id, user_name=str(message.author))
                await message.reply("Unlocked. Lock + alarm cleared.")
            else:
                log_event(
                    "unlock_fail",
                    user_id=message.author.id,
                    user_name=str(message.author),
                    detail="bad password",
                )
                set_alarm(True, f"failed unlock DM from {message.author.id}")
                await message.reply("Wrong password. Alarm set.")
        else:
            await message.reply("DM only accepts: `unlock <password>`")
        return

    if message.channel.id != COMMAND_CHANNEL_ID:
        return

    uid = message.author.id
    uname = str(message.author)

    # Whitelist
    if whitelist_enabled():
        allowed = allowed_command_user_ids()
        if allowed and uid not in allowed:
            log_event("denied", user_id=uid, user_name=uname, detail="not on whitelist")
            await message.reply("Not on whitelist.")
            return

    cmd = parse_command(message.content)
    if cmd is None:
        return

    # Always log command attempts (including your own)
    log_event("command", user_id=uid, user_name=uname, detail=cmd)

    # Rate limit (logs + optional alarm)
    ok_rl, rl_msg = check_rate_limit(uid)
    if not ok_rl:
        log_event("rate_limited", user_id=uid, user_name=uname, detail=rl_msg)
        await message.reply("⏳ Rate limit exceeded. Alarm may be active — check `!status`.")
        return

    # Built-ins that must work even when locked: unlock instructions, status
    if cmd == "__STATUS__":
        await message.reply(
            f"**Status**\n"
            f"locked: `{is_locked()}`\n"
            f"alarm: `{is_alarm()}`"
            + (f" — {alarm_reason()}" if is_alarm() else "")
            + f"\nwhitelist: `{whitelist_enabled()}`\nluks: `{luks_enabled()}`"
        )
        return

    if cmd == "__UNLOCK__":
        await message.reply(
            "To unlock: **DM this bot** with:\n"
            "```\nunlock DEIN_BITWARDEN_PASSWORT\n```\n"
            "(Password is never typed in the server channel.)"
        )
        return

    if cmd == "__LOCK__":
        set_locked(True)
        log_event("lock", user_id=uid, user_name=uname)
        await message.reply(
            "🔒 **LOCKED.** All commands blocked.\n"
            "Unlock: DM me `unlock <password>`"
        )
        return

    if cmd == "__ALARM_STATUS__":
        await message.reply(
            f"alarm=`{is_alarm()}` reason=`{alarm_reason() or '-'}\n"
            f"Clear via DM `unlock <password>` or delete `state/ALARM`."
        )
        return

    # Block everything else while locked / alarm
    blocked, why = commands_blocked()
    if blocked and cmd not in ("__LIST_ALIASES__",):
        log_event("blocked_lock" if is_locked() else "blocked_alarm", user_id=uid, user_name=uname, detail=cmd)
        await message.reply(f"🚫 {why}")
        return

    if cmd == "__LIST_ALIASES__":
        await message.reply(format_alias_list())
        return

    if cmd == "__RELOAD__":
        load_config(force=True)
        load_aliases(force=True)
        await message.reply("🔄 Config + aliases reloaded.")
        return

    if cmd == "__LUKS_UNLOCK__":
        await _handle_luks_unlock(message)
        return

    if cmd == "__SCREENSHOT__":
        approved = await request_approval(message, "screenshot", client)
        if not approved:
            return
        ok, info, path = await asyncio.to_thread(take_screenshot)
        if not ok or path is None:
            await message.reply(f"Screenshot failed: {info}")
            return
        await message.reply(file=discord.File(path))
        return

    if cmd == "__EXPORT_LOG__":
        approved = await request_approval(message, "exportlog", client)
        if not approved:
            return
        path = await asyncio.to_thread(export_recent)
        if path is None:
            await message.reply("No logs yet.")
            return
        await message.reply("Here are recent logs:", file=discord.File(path))
        return

    # Normal shell / alias command
    print(f"[Daemon] {uname}: {cmd}")
    approved = await request_approval(message, cmd, client)
    if not approved:
        log_event("denied_approval", user_id=uid, user_name=uname, detail=cmd)
        return

    await message.add_reaction("⚙️")
    returncode, stdout, stderr = await asyncio.to_thread(run_command, cmd)
    log_event(
        "executed",
        user_id=uid,
        user_name=uname,
        detail=cmd,
        extra={"returncode": returncode},
    )
    await _send_output(message, returncode, stdout, stderr)


def main():
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
