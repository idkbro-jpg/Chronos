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


def _user_allowed(uid: int) -> bool:
    if not whitelist_enabled():
        return True
    return uid in allowed_command_user_ids()


async def _maybe_approve(message: discord.Message, summary: str) -> bool:
    """Skip \u2705 when sudomode is active."""
    if is_sudomode():
        print(f"[Daemon] sudomode: auto-approve {summary!r}", flush=True)
        return True
    return await request_approval(message, summary, client)


async def _audit(text: str) -> None:
    cid = audit_channel_id()
    if not cid:
        return
    try:
        channel = client.get_channel(cid)
        if channel is None:
            channel = await client.fetch_channel(cid)
        if channel is not None:
            await channel.send(text[:1900])
    except Exception as e:
        print(f"[Audit] failed: {e}")


async def _handle_luks_unlock(message: discord.Message):
    summary = f"LUKS unlock device=`{luks_device()}` \u2192 mapper=`{luks_mapper_name()}`"
    approved = await _maybe_approve(message, summary)
    if not approved:
        return
    await message.add_reaction("\U0001f513")
    ok, msg = await asyncio.to_thread(unlock_luks)
    await message.reply(f"{'\U0001f513 **Success**' if ok else '\U0001f512 **Failed**'}\n{msg}")
    await _audit(f"LUKS unlock by {message.author}: {'ok' if ok else 'failed'}")


@client.event
async def on_ready():
    load_config(force=True)
    load_aliases(force=True)
    print(f"[Daemon] Logged in as {client.user} (ID: {client.user.id})")
    print(f"[Daemon] Watching channel ID: {COMMAND_CHANNEL_ID}")
    print(
        f"[Daemon] lock={is_locked()} alarm={is_alarm()} "
        f"sudomode={is_sudomode()}({sudomode_remaining()}s) luks={luks_enabled()}"
    )
    print(f"[Daemon] execution.mode={execution_mode()}")
    if not whitelist_enabled():
        print(
            "[Daemon] \u26a0\ufe0f  WHITELIST OFF \u2014 anyone in the command channel can propose "
            "shell commands (after reaction approval). This can mean full control of "
            "the machine if the daemon user has privileges. Enable whitelist in config.yml."
        )
    else:
        print(f"[Daemon] whitelist ON \u2014 {len(allowed_command_user_ids())} user id(s)")
    print("[Daemon] Ready.")


@client.event
async def on_message(message: discord.Message):
    if _shutting_down:
        return

    is_self = message.author == client.user
    if is_self:
        content = (message.content or "").strip()
        prefix = command_prefix()
        if not content.startswith(prefix):
            return

    if isinstance(message.channel, discord.DMChannel):
        if is_self:
            return
        await _handle_dm(message)
        return

    if message.channel.id != COMMAND_CHANNEL_ID:
        return

    uid = message.author.id
    uname = str(message.author)

    if not is_self and not _user_allowed(uid):
        log_event("denied", user_id=uid, user_name=uname, detail="not on whitelist")
        await message.reply("Not on whitelist.")
        return

    cmd = parse_command(message.content)
    if cmd is None:
        return

    try:
        await _dispatch_command(message, uid, uname, cmd)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Daemon] unhandled error for cmd={cmd!r}: {e}\n{tb}", flush=True)
        log_event(
            "error",
            user_id=uid,
            user_name=uname,
            detail=cmd,
            extra={"error": str(e)[:500]},
        )
        try:
            await message.reply(
                f"Internal error while handling command. Check logs. ({type(e).__name__})"
            )
        except Exception:
            pass


async def _handle_dm(message: discord.Message) -> None:
    content = message.content.strip()
    low = content.lower()
    uid = message.author.id
    uname = str(message.author)

    # unlock <password>
    if low.startswith("unlock ") or low.startswith("!unlock "):
        until = _unlock_fail_until.get(uid, 0)
        if time.time() < until:
            await message.reply("Too many failed attempts. Wait a bit.")
            return

        pw = content.split(None, 1)[1] if " " in content else ""
        if check_lock_password(pw):
            set_locked(False)
            set_alarm(False)
            _unlock_fail_until.pop(uid, None)
            log_event("unlock_ok", user_id=uid, user_name=uname, detail="lock+alarm cleared")
            await message.reply("Unlocked. Lock + alarm cleared.")
            await _audit(f"Unlock OK by {uname} ({uid})")
        else:
            _unlock_fail_until[uid] = time.time() + 15
            log_event(
                "unlock_fail",
                user_id=uid,
                user_name=uname,
                detail="bad password",
                extra={"password_attempted": pw},
            )
            set_alarm(True, f"failed unlock DM from {uid}")
            await message.reply("Wrong password. Alarm set. Try again in 15s.")
            await _audit(f"Unlock FAIL by {uname} ({uid}) \u2014 alarm set")
        return

    # sudomode <password>  |  sudomode off
    if low.startswith("sudomode") or low.startswith("!sudomode"):
        parts = content.split(None, 1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        arg_low = arg.lower()

        if arg_low in ("off", "stop", "disable", "0"):
            set_sudomode(False)
            log_event("sudomode_off", user_id=uid, user_name=uname)
            await message.reply("Sudomode **off**. \u2705 required again.")
            await _audit(f"SUDOMODE OFF by {uname} ({uid})")
            return

        if not arg:
            await message.reply(
                "Usage:\n"
                "```\nsudomode YOUR_LOCK_PASSWORD\nsudomode off\n```\n"
                f"Currently: `{'ON (' + str(sudomode_remaining()) + 's left)' if is_sudomode() else 'OFF'}`"
            )
            return

        if check_lock_password(arg):
            set_sudomode(True, ttl=SUDOMODE_TTL, user_id=uid)
            log_event(
                "sudomode_on",
                user_id=uid,
                user_name=uname,
                detail=f"ttl={SUDOMODE_TTL}s",
            )
            await message.reply(
                f"Sudomode **ON** for ~{SUDOMODE_TTL // 60} min. "
                "Commands skip \u2705 approval. DM `sudomode off` to stop early."
            )
            await _audit(f"SUDOMODE ON by {uname} ({uid}) ttl={SUDOMODE_TTL}s")
        else:
            log_event(
                "sudomode_fail",
                user_id=uid,
                user_name=uname,
                detail="bad password",
                extra={"password_attempted": arg},
            )
            set_alarm(True, f"failed sudomode DM from {uid}")
            await message.reply("Wrong password. Alarm set.")
            await _audit(f"SUDOMODE FAIL by {uname} ({uid})")
        return

    await message.reply(
        "DM accepts:\n"
        "```\nunlock <password>\nsudomode <password>\nsudomode off\n```"
    )


async def _dispatch_command(
    message: discord.Message, uid: int, uname: str, cmd: str
) -> None:
    log_event("command", user_id=uid, user_name=uname, detail=cmd)

    if cmd == "__STATUS__":
        rl = (
            f"`{rate_limit_max()}` / `{rate_limit_window()}s`"
            if rate_limit_enabled()
            else "disabled"
        )
        wl = (
            f"`on` ({len(allowed_command_user_ids())} ids)"
            if whitelist_enabled()
            else "`OFF \u26a0\ufe0f anyone in channel can propose commands`"
        )
        sudo = (
            f"`ON` ({sudomode_remaining()}s left)"
            if is_sudomode()
            else "`off`"
        )
        await message.reply(
            f"**Status**\n"
            f"locked: `{is_locked()}`\n"
            f"alarm: `{is_alarm()}`"
            + (f" \u2014 {alarm_reason()}" if is_alarm() else "")
            + f"\nsudomode: {sudo}\n"
            + f"whitelist: {wl}\n"
            f"execution mode: `{execution_mode()}`\n"
            f"luks: `{luks_enabled()}`"
            + (f" (`{luks_device()}` \u2192 `{luks_mapper_name()}`)" if luks_enabled() else "")
            + f"\nrate limit: {rl}"
        )
        return

    if cmd == "__PING__":
        created = message.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        lag_ms = int((datetime.now(timezone.utc) - created).total_seconds() * 1000)
        ws = client.latency
        ws_ms = int(ws * 1000) if ws is not None and ws >= 0 else -1
        await message.reply(
            f"Pong \u00b7 message lag `~{lag_ms}ms` \u00b7 gateway latency `~{ws_ms}ms`"
        )
        return

    if cmd == "__HELP__":
        await message.reply(format_help())
        return

    if cmd == "__UNLOCK__":
        await message.reply(
            "To unlock: **DM this bot** with:\n"
            "```\nunlock YOUR_LONG_PASSWORD\n```\n"
            "(Never type the password in the server channel.)"
        )
        return

    if cmd == "__SUDOMODE__":
        if is_sudomode():
            await message.reply(
                f"Sudomode is **ON** (~{sudomode_remaining()}s left).\n"
                "DM `sudomode off` to disable."
            )
        else:
            await message.reply(
                "Sudomode is **OFF**.\n"
                "To enable (skips \u2705 for a while): **DM** the bot:\n"
                "```\nsudomode YOUR_LOCK_PASSWORD\n```\n"
                "Same password as unlock. Never post it in the channel."
            )
        return

    if cmd == "__ALARM_STATUS__":
        await message.reply(
            f"alarm=`{is_alarm()}` reason=`{alarm_reason() or '-'}\n"
            f"Clear via DM `unlock <password>` or delete `state/ALARM`."
        )
        return

    if cmd == "__HISTORY__":
        if not history_enabled():
            await message.reply("History is disabled in config.")
            return
        entries = history_recent(15)
        if not entries:
            await message.reply("No history yet.")
            return
        now_utc = datetime.now(timezone.utc)
        lines = ["**Recent commands** (UTC):", "```"]
        for e in entries:
            dt = datetime.fromtimestamp(e.get("ts", 0), tz=timezone.utc)
            if dt.date() == now_utc.date():
                ts = dt.strftime("%H:%M:%S")
            else:
                ts = dt.strftime("%Y-%m-%d %H:%M:%S")
            rc = e.get("returncode")
            rc_s = f" rc={rc}" if rc is not None else ""
            lines.append(f"{ts} {e.get('user_name', '?')}: {e.get('command', '')}{rc_s}")
        lines.append("```")
        await message.reply("\n".join(lines))
        return

    if cmd == "__LAST__":
        entry = last_command()
        if not entry:
            await message.reply("No history yet.")
            return
        await message.reply(
            f"**Last command** by `{entry.get('user_name')}`:\n"
            f"```\n{entry.get('command')}\n```"
            + (f"exit `{entry.get('returncode')}`" if entry.get("returncode") is not None else "")
        )
        return

    ok_rl, rl_msg, retry_after = check_rate_limit(uid)
    if not ok_rl:
        log_event("rate_limited", user_id=uid, user_name=uname, detail=rl_msg)
        await message.reply(
            f"\u23f3 Rate limit exceeded. Try again in ~**{retry_after}s**. Check `!status`."
        )
        return

    if cmd == "__LOCK__":
        approved = await _maybe_approve(message, "LOCK system")
        if not approved:
            return
        set_locked(True)
        set_sudomode(False)  # lock clears sudo
        log_event("lock", user_id=uid, user_name=uname)
        await message.reply(
            "\U0001f512 **LOCKED.** All commands blocked.\n"
            "Unlock: DM me `unlock <password>`"
        )
        await _audit(f"LOCK by {uname} ({uid})")
        return

    blocked, why = commands_blocked()
    if blocked:
        log_event(
            "blocked_lock" if is_locked() else "blocked_alarm",
            user_id=uid,
            user_name=uname,
            detail=cmd,
        )
        await message.reply(f"\U0001f6ab {why}")
        return

    if cmd == "__LIST_ALIASES__":
        await message.reply(format_alias_list())
        return

    if cmd == "__RELOAD__":
        load_config(force=True)
        load_aliases(force=True)
        await message.reply("\U0001f504 Config + aliases reloaded.")
        return

    if cmd == "__LUKS_UNLOCK__":
        await _handle_luks_unlock(message)
        return

    if cmd == "__SCREENSHOT__":
        approved = await _maybe_approve(message, "screenshot")
        if not approved:
            return
        ok, info, path = await asyncio.to_thread(take_screenshot)
        if not ok or path is None:
            await message.reply(f"Screenshot failed: {info}")
            return
        await message.reply(file=discord.File(path))
        return

    if cmd == "__EXPORT_LOG__":
        approved = await _maybe_approve(message, "exportlog")
        if not approved:
            return
        path = await asyncio.to_thread(export_recent)
        if path is None:
            await message.reply("No logs yet.")
            return
        await message.reply("Here are recent logs:", file=discord.File(path))
        return

    if cmd.startswith("__INPUT__:"):
        spec = cmd[len("__INPUT__:"):].strip()
        summary = f"keyboard input: {spec or '(empty)'}"
        approved = await _maybe_approve(message, summary)
        if not approved:
            return
        ok, info = await asyncio.to_thread(simulate_input, spec)
        log_event(
            "input",
            user_id=uid,
            user_name=uname,
            detail=spec,
            extra={"ok": ok, "info": info[:200]},
        )
        if ok:
            await message.reply(f"\u2328\ufe0f {info}")
        else:
            await message.reply(f"\u2328\ufe0f Failed: {info}")
        return

    if cmd.startswith("__MOUSE__:"):
        spec = cmd[len("__MOUSE__:"):].strip()
        summary = f"mouse: {spec or '(empty)'}"
        approved = await _maybe_approve(message, summary)
        if not approved:
            return
        ok, info = await asyncio.to_thread(simulate_mouse, spec)
        log_event(
            "mouse",
            user_id=uid,
            user_name=uname,
            detail=spec,
            extra={"ok": ok, "info": info[:200]},
        )
        if ok:
            await message.reply(f"\U0001f5b1\ufe0f {info}")
        else:
            await message.reply(f"\U0001f5b1\ufe0f Failed: {info}")
        return

    allowed, policy_msg = command_allowed_by_policy(cmd)
    if not allowed:
        log_event("denied_policy", user_id=uid, user_name=uname, detail=cmd)
        await message.reply(f"\U0001f6ab {policy_msg}")
        return

    print(f"[Daemon] {uname}: {cmd}", flush=True)
    approved = await _maybe_approve(message, cmd)
    if not approved:
        log_event("denied_approval", user_id=uid, user_name=uname, detail=cmd)
        return

    await message.add_reaction("\u2699\ufe0f")
    returncode, stdout, stderr = await asyncio.to_thread(run_command, cmd)
    log_event(
        "executed",
        user_id=uid,
        user_name=uname,
        detail=cmd,
        extra={
            "returncode": returncode,
            "stdout": stdout[:12000],
            "stderr": stderr[:4000],
        },
    )
    history_record(uid, uname, cmd, returncode)
    await _audit(f"exec by {uname}: `{cmd[:200]}` \u2192 rc={returncode}")
    await _send_output(message, returncode, stdout, stderr)


async def _close_gracefully() -> None:
    global _shutting_down
    _shutting_down = True
    print("[Daemon] Shutting down\u2026", flush=True)
    log_event("shutdown", detail="signal")
    try:
        await client.close()
    except Exception:
        pass


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _handle_sig(*_args):
        print("[Daemon] signal received", flush=True)
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_close_gracefully()))

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_sig)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _handle_sig())

    try:
        loop.run_until_complete(client.start(DISCORD_TOKEN))
    except KeyboardInterrupt:
        loop.run_until_complete(_close_gracefully())
    finally:
        loop.run_until_complete(client.close())
        loop.close()


if __name__ == "__main__":
    main()
