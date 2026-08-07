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
    "reload": "__RELOAD__",
    "reloadaliases": "__RELOAD__",
    "reloadconfig": "__RELOAD__",
    "luksunlock": "__LUKS_UNLOCK__",
    "luks_unlock": "__LUKS_UNLOCK__",
    "luks-unlock": "__LUKS_UNLOCK__",
    "unlockluks": "__LUKS_UNLOCK__",
    "lock": "__LOCK__",
    "unlock": "__UNLOCK__",
    "alarm": "__ALARM_STATUS__",
    "status": "__STATUS__",
    "screenshot": "__SCREENSHOT__",
    "ss": "__SCREENSHOT__",
    "exportlog": "__EXPORT_LOG__",
    "logs": "__EXPORT_LOG__",
}

# Built-ins that take a payload: return "__TOKEN__:payload"
BUILTINS_WITH_ARGS = {
    "input": "__INPUT__",
    "type": "__INPUT__",
    "key": "__INPUT__",
    "keys": "__INPUT__",
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
            lines.append(f"{name:12} → {display}")
    else:
        lines.append("(none)")
    lines.append("```")
    lines.append(
        "_Built-ins: `!aliases` `!reload` `!lock` `!unlock` `!status` "
        "`!screenshot` `!exportlog` `!input` `!luksunlock`_"
    )
    return "\n".join(lines)
