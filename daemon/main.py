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
    can_write_permissions,
    get_effective_permissions,
    give_permission,
    has_permission,
    is_safe_mode,
    list_presets,
    list_users,
    needs_approval as user_needs_approval,
    set_rank,
    super_owner_id,
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


def _cmd_skips_approval_token(cmd_token: str) -> bool:
    """Built-ins that are informational never need the approval flow."""
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
        return True
    if is_sudomode():
        return True
    return False


def _perm_for_token(cmd_token: str, raw_body: str) -> str | None:
    """
    Map a parsed command token to a namespaced Chronos permission.
    Returns None when the command is unrestricted (help/ping/status etc.).
    """
    mapping = {
        "__LOCK__": "chronos:lock",
        "__UNLOCK__": "chronos:unlock",
        "__SUDOMODE__": "chronos:sudomode",
        "__SCREENSHOT__": "chronos:screenshot",
        "__INPUT__": "chronos:input",
        "__MOUSE__": "chronos:mouse",
        "__LUKS_UNLOCK__": "chronos:luksunlock",
        "__EXPORT_LOG__": "chronos:exportlog",
        "__HISTORY__": "chronos:history",
        "__LAST__": "chronos:history",
        "__RELOAD__": "chronos:reload",
        "__PERM__": "chronos:manage_permissions",
        "__SYSINFO__": "chronos:sysinfo",
    }
    # Informational builtins that anyone may use (still gated by whitelist)
    open_tokens = {
        "__HELP__",
        "__PING__",
        "__STATUS__",
        "__LIST_ALIASES__",
        "__ALARM_STATUS__",
        "__UNLOCK__",
    }
    if cmd_token in open_tokens:
        return None
    if cmd_token in mapping:
        return mapping[cmd_token]
    if cmd_token.startswith("__INPUT__"):
        return "chronos:input"
    if cmd_token.startswith("__MOUSE__"):
        return "chronos:mouse"
    if cmd_token.startswith("__PERM__"):
        return "chronos:manage_permissions"

    # Shell / alias / raw command → bash:<first-word>
    first = (raw_body or cmd_token).split(None, 1)[0].lower() if (raw_body or cmd_token) else ""
    # strip simple path prefixes so /usr/bin/ls → ls for matching bash:ls
    if "/" in first:
        first = first.rsplit("/", 1)[-1]
    if first:
        return f"bash:{first}"
    return "bash:*"


# ---------------------------------------------------------------------------
# !perm subcommand handler
# ---------------------------------------------------------------------------


async def _handle_perm(message: discord.Message, rest: str) -> None:
    """
    !perm check <id|@user>
    !perm give <id|@user> permission <namespaced>
    !perm give <id|@user> rank <rankname>
    !perm deny <id|@user> permission <namespaced>
    !perm setrank <id|@user> <rankname>
    !perm list
    !perm help

    Only super_owner_id and rank owner may change permissions.
    File is always re-read; writes go through shared.permissions helpers.
    """
    uid = message.author.id

    if not can_write_permissions(uid) and not (
        rest or ""
    ).strip().lower().startswith(("check", "list", "help", "?")):
        # read-only subcommands allowed for anyone with manage_permissions
        if not has_permission(uid, "chronos:manage_permissions"):
            await _safe_reply(
                message,
                "You need rank `owner` (or be super-owner) to change permissions.\n"
                "Anyone with `chronos:manage_permissions` may use `check` / `list`.",
            )
            return

    parts = (rest or "").strip().split()
    if not parts or parts[0].lower() in ("help", "?"):
        p = "!"
        await _safe_reply(
            message,
            f"**!perm usage** (namespaced)\n"
            f"```\n"
            f"{p}perm check <id|@user>\n"
            f"{p}perm list\n"
            f"{p}perm give <id|@user> permission chronos:screenshot\n"
            f"{p}perm give <id|@user> permission bash:ls\n"
            f"{p}perm give <id|@user> rank mod\n"
            f"{p}perm setrank <id|@user> owner\n"
            f"{p}perm deny <id|@user> permission chronos:lock\n"
            f"```\n"
            f"Namespaces: `chronos:…` · `bash:…` · `alias:…` · wildcards `chronos:*` `bash:*`\n"
            f"Safe-mode: **{'yes' if is_safe_mode() else 'no'}** · super-owner: `{super_owner_id()}`",
        )
        return

    sub = parts[0].lower()

    if sub == "list":
        presets = list_presets()
        users = list_users()
        lines = ["**Presets**"]
        for name, r in sorted(presets.items()):
            perms = ", ".join(r.get("permissions") or []) or "(none)"
            na = r.get("needs_approval", True)
            lines.append(f"• **{name}** (approval={'yes' if na else 'no'}): `{perms}`")
        lines.append(f"\n**Users** ({len(users)})")
        for uid_s, entry in sorted(users.items()):
            rank = entry.get("rank", "—")
            extra = entry.get("extra") or []
            deny = entry.get("deny") or []
            bits = [f"rank={rank}"]
            if extra:
                bits.append("extra=" + ",".join(str(x) for x in extra[:8]))
            if deny:
                bits.append("deny=" + ",".join(str(x) for x in deny[:8]))
            lines.append(f"• `{uid_s}`: " + " · ".join(bits))
        if is_safe_mode():
            lines.append("\n⚠️ **Safe-Mode active** — only super-owner has rights.")
        await _safe_reply(message, "\n".join(lines))
        return

    if sub == "check":
        target = _resolve_member(message, parts[1:])
        target_id = None
        if target is not None:
            target_id = target.id
            label = target.display_name
        else:
            # raw id
            for tok in parts[1:]:
                t = tok.strip("<@!>")
                if t.isdigit():
                    target_id = int(t)
                    label = t
                    break
        if target_id is None:
            await _safe_reply(message, "Usage: `!perm check @user` or `!perm check <id>`")
            return
        perms = sorted(get_effective_permissions(target_id))
        na = user_needs_approval(target_id)
        if not perms:
            await _safe_reply(
                message,
                f"**{label}** (`{target_id}`) has **no** Chronos permissions.\n"
                f"needs_approval: **{na}**",
            )
            return
        shown = ", ".join(f"`{p}`" for p in perms[:50])
        extra = f" (+{len(perms) - 50} more)" if len(perms) > 50 else ""
        await _safe_reply(
            message,
            f"**{label}** (`{target_id}`) effective permissions:\n{shown}{extra}\n"
            f"needs_approval: **{na}**",
        )
        return

    # ---- mutating subcommands ----
    if not can_write_permissions(uid):
        await _safe_reply(message, "Only super-owner / rank `owner` may change permissions.")
        return

    if sub in ("give", "add", "setrank", "deny", "remove", "revoke"):
        if len(parts) < 3:
            await _safe_reply(
                message,
                f"Usage: `!perm {sub} <id|@user> …`",
            )
            return

        target = _resolve_member(message, parts[1:])
        target_id = target.id if target else None
        label = target.display_name if target else None
        if target_id is None:
            for tok in parts[1:]:
                t = tok.strip("<@!>")
                if t.isdigit():
                    target_id = int(t)
                    label = t
                    break
        if target_id is None:
            await _safe_reply(message, "Could not resolve target user (mention or numeric ID).")
            return

        if sub == "setrank" or (sub in ("give", "add") and len(parts) >= 3 and parts[2].lower() == "rank"):
            # !perm setrank <id> <rank>  OR  !perm give <id> rank <rank>
            if sub == "setrank":
                rank = parts[2].lower()
            else:
                if len(parts) < 4:
                    await _safe_reply(message, "Usage: `!perm give <id> rank <rankname>`")
                    return
                rank = parts[3].lower()
            ok, msg = set_rank(target_id, rank, writer_id=uid)
            if ok:
                await _safe_reply(message, f"Set rank **{rank}** for **{label}** (`{target_id}`).")
                log_event("perm_change", user_id=uid, user_name=str(message.author),
                          detail=f"setrank {rank} → {target_id}")
            else:
                await _safe_reply(message, f"Failed: {msg}")
            return

        if sub in ("give", "add"):
            # !perm give <id> permission <name>
            type_idx = None
            for i, tok in enumerate(parts[1:], start=1):
                if tok.lower() in ("permission", "perm"):
                    type_idx = i
                    break
            if type_idx is None or type_idx + 1 >= len(parts):
                await _safe_reply(
                    message,
                    "Usage: `!perm give <id> permission chronos:screenshot` "
                    "or `!perm give <id> rank mod`",
                )
                return
            name = parts[type_idx + 1].strip()
            # auto-namespace bare names to chronos:
            if ":" not in name:
                name = f"chronos:{name}"
            ok, msg = give_permission(target_id, name, writer_id=uid)
            if ok:
                await _safe_reply(message, f"Granted `{name}` to **{label}** (`{target_id}`).")
                log_event("perm_change", user_id=uid, user_name=str(message.author),
                          detail=f"give {name} → {target_id}")
            else:
                await _safe_reply(message, f"Failed: {msg}")
            return

        if sub in ("deny", "remove", "revoke"):
            await _safe_reply(
                message,
                "To deny a permission, edit `permissions.yml` under the user's `deny:` list "
                "(or remove from `extra:`). Live deny-write will be added later if needed.",
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

    if token == "__SYSINFO__":
        info = await asyncio.to_thread(gather_sysinfo)
        await _safe_reply(message, info)
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
        await _safe_reply(
            message,
            "Reloaded `config.yml` and `aliases.yml`. "
            "`permissions.yml` is always re-read on each check.",
        )
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

    if not _cmd_skips_approval_token(command) and user_needs_approval(message.author.id):
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

    # Permission gate (namespaced, always re-reads permissions.yml)
    needed = _perm_for_token(token, raw_body)
    if needed and not has_permission(uid, needed):
        await _safe_reply(
            message,
            f"No permission for `{needed}`.\n"
            f"Ask an owner: `!perm give {uid} permission {needed}` "
            f"or set a rank in `permissions.yml`.",
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
    if is_safe_mode():
        print(
            f"[Daemon] ⚠️  permissions Safe-Mode active "
            f"(only super-owner {super_owner_id()} has rights)."
        )
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
