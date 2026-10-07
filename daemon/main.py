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


def _perm_for_token(cmd_token: str, raw_body: str) -> str | None:
    """
    Map a parsed command token to the Chronos permission name that guards it.
    Returns None when the command is unrestricted (help/ping/status etc.).
    """
    mapping = {
        "__LOCK__": "lock",
        "__UNLOCK__": "unlock",
        "__SUDOMODE__": "sudomode",
        "__SCREENSHOT__": "screenshot",
        "__INPUT__": "input",
        "__MOUSE__": "mouse",
        "__LUKS_UNLOCK__": "luksunlock",
        "__EXPORT_LOG__": "exportlog",
        "__HISTORY__": "history",
        "__LAST__": "history",
        "__RELOAD__": "manage_bot",
        "__PERM__": "manage_permissions",
    }
    if cmd_token in mapping:
        return mapping[cmd_token]
    if cmd_token.startswith("__INPUT__"):
        return "input"
    if cmd_token.startswith("__MOUSE__"):
        return "mouse"
    if cmd_token.startswith("__PERM__"):
        return "manage_permissions"

    # Shell / alias / raw command → permission is the first word (alias name)
    # or "cmd" for explicit !cmd / free-form shell.
    first = (raw_body or cmd_token).split(None, 1)[0].lower() if (raw_body or cmd_token) else ""
    if first:
        return first
    return "cmd"


# ---------------------------------------------------------------------------
# !perm subcommand handler
# ---------------------------------------------------------------------------


async def _handle_perm(message: discord.Message, rest: str) -> None:
    """
    !perm check @user
    !perm give @user permission <name>
    !perm give @user rank <rankname>
    !perm remove @user permission <name>
    !perm remove @user rank <rankname>
    !perm list
    !perm reload
    !perm help
    """
    member = message.author
    if not isinstance(member, discord.Member):
        # DM – try to resolve guild member from the command channel's guild
        guild = None
        ch = client.get_channel(COMMAND_CHANNEL_ID)
        if ch and getattr(ch, "guild", None):
            guild = ch.guild
        if guild:
            member = guild.get_member(message.author.id) or member

    if not has_permission(member, "manage_permissions") and not has_permission(member, "sudo"):
        await _safe_reply(message, "You need the `manage_permissions` permission to use `!perm`.")
        return

    parts = (rest or "").strip().split()
    if not parts or parts[0].lower() in ("help", "?"):
        p = "!"  # display only
        await _safe_reply(
            message,
            f"**!perm usage**\n"
            f"```\n"
            f"{p}perm check @user\n"
            f"{p}perm give @user permission <name>\n"
            f"{p}perm give @user rank <rankname>\n"
            f"{p}perm remove @user permission <name>\n"
            f"{p}perm remove @user rank <rankname>\n"
            f"{p}perm list\n"
            f"{p}perm reload\n"
            f"```\n"
            f"Permission names = special ones (`sudo`, `screenshot`, …) or any alias/command name.",
        )
        return

    sub = parts[0].lower()

    if sub == "reload":
        load_permissions(force=True)
        await _safe_reply(message, "Permissions reloaded from `permissions.yml`.")
        return

    if sub == "list":
        ranks = list_ranks()
        specials = list_special_permissions()
        lines = ["**Chronos ranks**"]
        for name, r in sorted(ranks.items(), key=lambda x: x[1].get("level", 0)):
            perms = ", ".join(r.get("permissions") or []) or "(none)"
            lines.append(f"• **{name}** (level {r.get('level', 0)}): `{perms}`")
        lines.append("\n**Special permissions**")
        for name, desc in sorted(specials.items()):
            lines.append(f"• `{name}` — {desc}")
        await _safe_reply(message, "\n".join(lines))
        return

    if sub == "check":
        target = _resolve_member(message, parts[1:])
        if target is None:
            await _safe_reply(message, "Usage: `!perm check @user`")
            return
        perms = sorted(get_user_effective_permissions(target))
        if not perms:
            await _safe_reply(message, f"**{target.display_name}** has no Chronos permissions.")
            return
        shown = ", ".join(f"`{p}`" for p in perms[:40])
        extra = f" (+{len(perms) - 40} more)" if len(perms) > 40 else ""
        await _safe_reply(
            message,
            f"**{target.display_name}** effective permissions:\n{shown}{extra}",
        )
        return

    if sub in ("give", "remove", "add", "revoke"):
        if len(parts) < 4:
            await _safe_reply(
                message,
                f"Usage: `!perm {sub} @user permission|rank <name>`",
            )
            return
        target = _resolve_member(message, parts[1:])
        if target is None:
            await _safe_reply(message, "Could not resolve the target user. Mention them or use their ID.")
            return

        # Find the type token (permission / rank) after the mention/id
        type_idx = None
        for i, tok in enumerate(parts[1:], start=1):
            if tok.lower() in ("permission", "perm", "rank", "role"):
                type_idx = i
                break
        if type_idx is None or type_idx + 1 >= len(parts):
            await _safe_reply(
                message,
                f"Usage: `!perm {sub} @user permission|rank <name>`",
            )
            return

        kind = parts[type_idx].lower()
        name = parts[type_idx + 1].lower().strip()
        adding = sub in ("give", "add")

        cfg = load_permissions()
        overrides = cfg.setdefault("user_overrides", {})
        entry = overrides.setdefault(str(target.id), {})

        if kind in ("permission", "perm"):
            if adding:
                lst = entry.setdefault("extra_permissions", [])
                denied = entry.get("denied_permissions") or []
                if name in [str(x).lower() for x in denied]:
                    entry["denied_permissions"] = [x for x in denied if str(x).lower() != name]
                if name not in [str(x).lower() for x in lst]:
                    lst.append(name)
                action = f"granted permission `{name}`"
            else:
                extras = entry.get("extra_permissions") or []
                new_extras = [x for x in extras if str(x).lower() != name]
                if len(new_extras) != len(extras):
                    entry["extra_permissions"] = new_extras
                    action = f"removed extra permission `{name}`"
                else:
                    denied = entry.setdefault("denied_permissions", [])
                    if name not in [str(x).lower() for x in denied]:
                        denied.append(name)
                    action = f"denied permission `{name}`"
        else:  # rank
            ranks = cfg.get("ranks") or {}
            if name not in ranks:
                await _safe_reply(
                    message,
                    f"Unknown rank `{name}`. Known: {', '.join(sorted(ranks)) or '(none)'}",
                )
                return
            lst = entry.setdefault("extra_ranks", [])
            if adding:
                if name not in [str(x).lower() for x in lst]:
                    lst.append(name)
                action = f"granted rank `{name}`"
            else:
                entry["extra_ranks"] = [x for x in lst if str(x).lower() != name]
                action = f"removed rank `{name}`"

        # Clean empty lists
        for k in list(entry.keys()):
            if isinstance(entry[k], list) and not entry[k]:
                del entry[k]
        if not entry:
            overrides.pop(str(target.id), None)

        save_permissions(cfg)
        await _safe_reply(message, f"{action} for **{target.display_name}**.")
        log_event(
            "perm_change",
            user_id=message.author.id,
            user_name=str(message.author),
            detail=f"{action} → {target.id}",
        )
        return

    await _safe_reply(message, f"Unknown subcommand `{sub}`. Try `!perm help`.")


def _resolve_member(message: discord.Message, tokens: list[str]) -> discord.Member | None:
    """Resolve a member from mention, raw ID, or display name fragment."""
    if message.mentions:
        u = message.mentions[0]
        if isinstance(u, discord.Member):
            return u
        if message.guild:
            return message.guild.get_member(u.id)
        return None

    guild = message.guild
    if guild is None:
        ch = client.get_channel(COMMAND_CHANNEL_ID)
        guild = getattr(ch, "guild", None)
    if guild is None:
        return None

    for tok in tokens:
        tok = tok.strip("<@!>").strip()
        if tok.isdigit():
            m = guild.get_member(int(tok))
            if m:
                return m
        # fuzzy name
        low = tok.lower()
        for m in guild.members:
            if low in (m.name or "").lower() or low in (m.display_name or "").lower():
                return m
    return None


# ---------------------------------------------------------------------------
# Builtin handlers
# ---------------------------------------------------------------------------


async def _handle_builtin(message: discord.Message, token: str) -> bool:
    """
    Handle built-in commands. Returns True if fully handled (caller should stop).
    """
    author = message.author
    uid = author.id
    uname = str(author)

    if token == "__HELP__":
        await _safe_reply(message, format_help())
        return True

    if token == "__LIST_ALIASES__":
        await _safe_reply(message, format_alias_list())
        return True

    if token == "__PING__":
        lag = (time.time() - message.created_at.timestamp()) * 1000
        ws = client.latency * 1000 if client.latency is not None else -1
        await _safe_reply(
            message,
            f"Pong. message lag ≈ `{lag:.0f} ms` · gateway ≈ `{ws:.0f} ms`",
        )
        return True

    if token == "__STATUS__":
        locked = is_locked()
        alarm = is_alarm()
        sudo = is_sudomode()
        rem = sudomode_remaining()
        wl = whitelist_enabled()
        lines = [
            "**Chronos status**",
            f"• Locked: **{'yes' if locked else 'no'}**",
            f"• Alarm: **{'yes — ' + (alarm_reason() or 'active') if alarm else 'no'}**",
            f"• Sudomode: **{'yes (' + str(rem) + 's left)' if sudo else 'no'}**",
            f"• Whitelist: **{'on' if wl else 'off'}**",
            f"• Uptime: `{int(time.time() - _start_time)}s`",
        ]
        if not wl:
            lines.append(
                "_⚠️ whitelist is OFF — anyone in the channel can propose commands._"
            )
        await _safe_reply(message, "\n".join(lines))
        return True

    if token == "__ALARM_STATUS__":
        if is_alarm():
            await _safe_reply(message, f"Alarm is **active**: {alarm_reason() or 'unknown'}")
        else:
            await _safe_reply(message, "Alarm is **not** active.")
        return True

    if token == "__UNLOCK__":
        await _safe_reply(
            message,
            "To unlock, **DM** the bot:\n`unlock <password>`\n"
            "(Password is never accepted in the public channel.)",
        )
        return True

    if token == "__HISTORY__":
        entries = history.recent(10)
        if not entries:
            await _safe_reply(message, "No history yet.")
            return True
        lines = ["**Recent commands**"]
        for e in reversed(entries):
            ts = time.strftime("%H:%M:%S", time.gmtime(e.get("ts", 0)))
            rc = e.get("returncode")
            rc_s = f"rc={rc}" if rc is not None else ""
            lines.append(f"`{ts}` {e.get('user_name', '?')}: `{safe_inline(e.get('command', ''), 80)}` {rc_s}")
        await _safe_reply(message, "\n".join(lines))
        return True

    if token == "__LAST__":
        last = history.last_command()
        if not last:
            await _safe_reply(message, "No history yet.")
            return True
        await _safe_reply(
            message,
            f"Last: `{safe_inline(last.get('command', ''), 150)}` "
            f"by {last.get('user_name', '?')} (rc={last.get('returncode')})",
        )
        return True

    if token == "__RELOAD__":
        load_config(force=True)
        load_aliases(force=True)
        load_permissions(force=True)
        await _safe_reply(message, "Reloaded `config.yml`, `aliases.yml`, and `permissions.yml`.")
        log_event("reload", user_id=uid, user_name=uname)
        return True

    if token.startswith("__PERM__"):
        rest = token.split(":", 1)[1] if ":" in token else ""
        await _handle_perm(message, rest)
        return True

    # ---- actions that may need approval / permissions ----

    if token == "__LOCK__":
        set_locked(True)
        await _safe_reply(message, "🔒 Machine **locked**. DM `unlock <password>` to unlock.")
        log_event("lock", user_id=uid, user_name=uname)
        await _maybe_audit(f"LOCK by {uname} ({uid})")
        return True

    if token == "__SUDOMODE__":
        if is_sudomode():
            await _safe_reply(
                message,
                f"Sudomode is **on** ({sudomode_remaining()}s remaining).",
            )
        else:
            await _safe_reply(
                message,
                "Sudomode is **off**. Enable via DM: `sudomode <password>`",
            )
        return True

    if token == "__SCREENSHOT__":
        ok, msg, path = await asyncio.to_thread(take_screenshot)
        if ok and path:
            try:
                await message.reply(f"Screenshot ({msg})", file=discord.File(str(path)))
            except discord.HTTPException as e:
                await _safe_reply(message, f"Screenshot ok but upload failed: {e}")
        else:
            await _safe_reply(message, f"Screenshot failed: {msg}")
        log_event("screenshot", user_id=uid, user_name=uname, detail=msg)
        return True

    if token.startswith("__INPUT__"):
        spec = token.split(":", 1)[1] if ":" in token else ""
        ok, msg = await asyncio.to_thread(simulate_input, spec)
        await _safe_reply(message, f"{'✅' if ok else '❌'} input: {msg}")
        log_event("input", user_id=uid, user_name=uname, detail=spec, extra={"ok": ok, "msg": msg})
        return True

    if token.startswith("__MOUSE__"):
        spec = token.split(":", 1)[1] if ":" in token else ""
        ok, msg = await asyncio.to_thread(simulate_mouse, spec)
        await _safe_reply(message, f"{'✅' if ok else '❌'} mouse: {msg}")
        log_event("mouse", user_id=uid, user_name=uname, detail=spec, extra={"ok": ok, "msg": msg})
        return True

    if token == "__LUKS_UNLOCK__":
        ok, msg = await asyncio.to_thread(unlock_luks)
        await _safe_reply(message, f"{'✅' if ok else '❌'} LUKS: {msg}")
        log_event("luks", user_id=uid, user_name=uname, detail=msg, extra={"ok": ok})
        await _maybe_audit(f"LUKS unlock by {uname}: {'ok' if ok else 'fail'}")
        return True

    if token == "__EXPORT_LOG__":
        path = await asyncio.to_thread(export_recent)
        if path and path.exists():
            try:
                await message.reply("Recent logs:", file=discord.File(str(path)))
            except discord.HTTPException as e:
                await _safe_reply(message, f"Log export ready but upload failed: {e}")
        else:
            await _safe_reply(message, "No log files found.")
        return True

    return False


# ---------------------------------------------------------------------------
# Shell / alias execution path
# ---------------------------------------------------------------------------


async def _execute_shell(message: discord.Message, command: str) -> None:
    uid = message.author.id
    uname = str(message.author)

    ok, reason = command_allowed_by_policy(command)
    if not ok:
        await _safe_reply(message, f"Blocked by policy: {reason}")
        log_event("denied_policy", user_id=uid, user_name=uname, detail=command)
        return

    if _needs_approval(command):
        approved = await request_approval(message, command, client)
        if not approved:
            log_event("denied_approval", user_id=uid, user_name=uname, detail=command)
            return

    await _safe_reply(message, f"Executing `{safe_inline(command, 120)}` …")
    rc, stdout, stderr = await asyncio.to_thread(run_command, command)
    history.record(uid, uname, command, rc)
    log_event(
        "executed",
        user_id=uid,
        user_name=uname,
        detail=command,
        extra={"returncode": rc, "stdout": stdout[:2000], "stderr": stderr[:1000]},
    )
    await _maybe_audit(f"EXEC by {uname}: `{safe_inline(command, 100)}` rc={rc}")

    replies = format_exec_replies(
        rc, stdout, stderr, max_output_chars(), max_output_chunks()
    )
    await _send_chunks(message.channel, replies)


# ---------------------------------------------------------------------------
# DM password handlers (unlock / sudomode)
# ---------------------------------------------------------------------------


async def _handle_dm(message: discord.Message) -> None:
    content = message.content.strip()
    low = content.lower()
    uid = message.author.id
    uname = str(message.author)

    if low.startswith("unlock "):
        password = content[7:].strip()
        if check_lock_password(password):
            set_locked(False)
            set_alarm(False)
            await message.channel.send("🔓 Unlocked. Alarm cleared.")
            log_event("unlock_ok", user_id=uid, user_name=uname)
            await _maybe_audit(f"UNLOCK by {uname} ({uid})")
        else:
            await message.channel.send("Wrong password.")
            log_event(
                "unlock_fail",
                user_id=uid,
                user_name=uname,
                extra={"password_len": len(password)},
            )
        return

    if low.startswith("sudomode ") or low.startswith("sudo "):
        password = content.split(None, 1)[1].strip() if " " in content else ""
        if check_lock_password(password):
            set_sudomode(True, user_id=uid)
            rem = sudomode_remaining()
            await message.channel.send(f"Sudomode **on** for {rem}s (skips ✅ approval).")
            log_event("sudomode_on", user_id=uid, user_name=uname)
        else:
            await message.channel.send("Wrong password.")
            log_event(
                "sudomode_fail",
                user_id=uid,
                user_name=uname,
                extra={"password_len": len(password)},
            )
        return


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------


async def _dispatch_command(message: discord.Message, token: str, raw_body: str) -> None:
    uid = message.author.id
    uname = str(message.author)

    # Resolve Member for permission checks
    member = message.author
    if not isinstance(member, discord.Member) and message.guild:
        member = message.guild.get_member(uid) or member

    # Permission gate (Chronos-specific)
    needed = _perm_for_token(token, raw_body)
    if needed and not has_permission(member, needed):
        # Allow pure informational builtins even without a rank
        if token not in (
            "__HELP__",
            "__PING__",
            "__STATUS__",
            "__LIST_ALIASES__",
            "__ALARM_STATUS__",
            "__UNLOCK__",
        ):
            await _safe_reply(
                message,
                f"No permission for `{needed}`. "
                f"(Ask an owner to map your Discord role in `permissions.yml` or `!perm give`.)",
            )
            log_event("denied", user_id=uid, user_name=uname, detail=f"missing perm={needed}")
            return

    # Builtins first
    if token.startswith("__") and await _handle_builtin(message, token):
        return

    # Everything else is treated as a shell/alias command
    blocked, why = commands_blocked()
    if blocked:
        await _safe_reply(message, why)
        log_event(
            "blocked_lock" if is_locked() else "blocked_alarm",
            user_id=uid,
            user_name=uname,
            detail=token,
        )
        return

    ok_rl, rl_msg, retry = check_rate_limit(uid)
    if not ok_rl:
        await _safe_reply(
            message,
            f"Rate limited. Try again in ~{retry}s." + (f" ({rl_msg})" if rl_msg else ""),
        )
        log_event("rate_limited", user_id=uid, user_name=uname, detail=rl_msg)
        return

    await _execute_shell(message, token)


# ---------------------------------------------------------------------------
# Discord events
# ---------------------------------------------------------------------------


@client.event
async def on_ready():
    print(f"[Daemon] Logged in as {client.user} (ID: {client.user.id})")
    print(f"[Daemon] Watching channel ID: {COMMAND_CHANNEL_ID}")
    load_config()
    load_aliases()
    load_permissions()
    if not whitelist_enabled():
        print(
            "[Daemon] ⚠️  SECURITY WARNING: whitelist is OFF. "
            "Anyone who can post in the command channel can propose shell commands."
        )
    print("[Daemon] Ready.")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # DMs → unlock / sudomode only
    if isinstance(message.channel, discord.DMChannel):
        try:
            await _handle_dm(message)
        except Exception as e:
            log_event("error", user_id=message.author.id, detail=f"dm handler: {e}")
        return

    if message.channel.id != COMMAND_CHANNEL_ID:
        return

    if not _is_whitelisted(message.author.id):
        return

    try:
        token = parse_command(message.content)
        if token is None:
            return

        from shared.config import command_prefix

        prefix = command_prefix()
        raw_body = message.content.strip()
        if raw_body.startswith(prefix):
            raw_body = raw_body[len(prefix):].strip()

        await _dispatch_command(message, token, raw_body)
    except Exception as e:
        log_event(
            "error",
            user_id=message.author.id,
            user_name=str(message.author),
            detail=str(e),
        )
        try:
            await message.reply("Internal error — check daemon logs.", mention_author=False)
        except discord.HTTPException:
            pass


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _shutdown(*_args):
        print("[Daemon] Shutting down…")
        loop.create_task(client.close())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass

    try:
        client.run(DISCORD_TOKEN)
    finally:
        print("[Daemon] Stopped.")


if __name__ == "__main__":
    main()
