"""
Shared command parsing helpers.
"""

from shared.aliases import resolve_alias, list_aliases
from shared.config import command_prefix

# Built-in command tokens (no extra args)
BUILTINS = {
    "aliases": "__LIST_ALIASES__",
    "alias": "__LIST_ALIASES__",
    "listaliases": "__LIST_ALIASES__",
    "help": "__HELP__",
    "commands": "__HELP__",
    "reload": "__RELOAD__",
    "reloadaliases": "__RELOAD__",
    "reloadconfig": "__RELOAD__",
    "luksunlock": "__LUKS_UNLOCK__",
    "luks_unlock": "__LUKS_UNLOCK__",
    "luks-unlock": "__LUKS_UNLOCK__",
    "unlockluks": "__LUKS_UNLOCK__",
    "lock": "__LOCK__",
    "unlock": "__UNLOCK__",
    "sudomode": "__SUDOMODE__",
    "sudo": "__SUDOMODE__",
    "alarm": "__ALARM_STATUS__",
    "status": "__STATUS__",
    "ping": "__PING__",
    "screenshot": "__SCREENSHOT__",
    "ss": "__SCREENSHOT__",
    "exportlog": "__EXPORT_LOG__",
    "logs": "__EXPORT_LOG__",
    "history": "__HISTORY__",
    "hist": "__HISTORY__",
    "last": "__LAST__",
}

BUILTINS_WITH_ARGS = {
    "input": "__INPUT__",
    "type": "__INPUT__",
    "key": "__INPUT__",
    "keys": "__INPUT__",
    "mouse": "__MOUSE__",
    "click": "__MOUSE__",
}


def is_command(content: str) -> bool:
    prefix = command_prefix()
    return content.strip().startswith(prefix)


def parse_command(content: str) -> str | None:
    content = content.strip()
    prefix = command_prefix()

    if not content.startswith(prefix):
        return None

    body = content[len(prefix):].strip()
    if not body:
        return None

    lower = body.lower()
    first = lower.split()[0]
    rest = body[len(body.split()[0]):].strip()

    if first in BUILTINS_WITH_ARGS:
        return f"{BUILTINS_WITH_ARGS[first]}:{rest}"

    if first in BUILTINS:
        return BUILTINS[first]

    if lower.startswith("cmd "):
        return body[4:].strip() or None

    word = body.split()[0]
    rest2 = body[len(word):].strip()

    aliased = resolve_alias(word)
    if aliased is not None:
        if rest2:
            return f"{aliased} {rest2}"
        return aliased

    return body


def format_alias_list() -> str:
    aliases = list_aliases()
    lines = ["**Available aliases:**", "```"]
    if aliases:
        for name, cmd in sorted(aliases.items()):
            display = cmd if len(cmd) <= 80 else cmd[:77] + "..."
            lines.append(f"{name:12} \u2192 {display}")
    else:
        lines.append("(none)")
    lines.append("```")
    lines.append(
        "_Built-ins: `!help` `!ping` `!aliases` `!reload` `!lock` `!unlock` `!sudomode` "
        "`!status` `!screenshot` `!exportlog` `!input` `!mouse` `!history` `!last` `!luksunlock`_"
    )
    return "\n".join(lines)


def format_help() -> str:
    p = command_prefix()
    return (
        f"**Chronos help** (prefix `{p}`)\n"
        f"```\n"
        f"{p}help / {p}commands     this message\n"
        f"{p}ping                 latency / liveness check\n"
        f"{p}status               lock / alarm / sudomode / whitelist / luks\n"
        f"{p}aliases              list command shortcuts\n"
        f"{p}reload               reload config.yml + aliases.yml\n"
        f"{p}lock                 lock the machine (needs \u2705 unless sudomode)\n"
        f"{p}unlock               how to unlock (DM only)\n"
        f"{p}sudomode             status; enable via DM with lock password\n"
        f"{p}alarm                alarm status\n"
        f"{p}screenshot / {p}ss     capture screen\n"
        f"{p}exportlog / {p}logs    upload recent logs\n"
        f"{p}history / {p}hist      recent executed commands\n"
        f"{p}last                 show last executed command\n"
        f"{p}input <keys|text:\u2026>  simulate keyboard\n"
        f"{p}mouse <spec>         simulate mouse\n"
        f"{p}luksunlock           unlock configured LUKS volume\n"
        f"{p}<alias>              run an alias from aliases.yml\n"
        f"{p}cmd <shell>          run a raw shell command\n"
        f"{p}<any shell command>  same as cmd (after approval)\n"
        f"```\n"
        f"_Most powerful actions need \u2705 unless **sudomode** is on._\n"
        f"_Unlock / sudomode password: only in a **DM** to the bot._\n"
        f"_Logs: `journalctl --user -u chronos-daemon -f` and `logs/chronos-*.log`._"
    )
