#!/usr/bin/env python3
"""Apply command_prefix() fix to daemon/main.py. Run from repo root."""
from pathlib import Path

path = Path("daemon/main.py")
text = path.read_text(encoding="utf-8")

if "command_prefix," in text and "p = command_prefix()" in text:
    print("Already applied.")
    raise SystemExit(0)

# If file is broken placeholder
if text.strip() in ("PLACEHOLDER", "TEMP_RESTORE") or len(text) < 100:
    print("daemon/main.py looks broken; restore from main first:")
    print("  git checkout main -- daemon/main.py")
    print("  # or: curl -sL https://raw.githubusercontent.com/idkbro-jpg/Chronos/main/daemon/main.py -o daemon/main.py")
    print("Then re-run this script.")
    raise SystemExit(1)

old_import = """from shared.config import (
    allowed_command_user_ids,
    audit_channel_id,
    load_config,
    max_output_chars,
    max_output_chunks,
    whitelist_enabled,
)"""
new_import = """from shared.config import (
    allowed_command_user_ids,
    audit_channel_id,
    command_prefix,
    load_config,
    max_output_chars,
    max_output_chunks,
    whitelist_enabled,
)"""
if old_import not in text:
    print("Import block not found – file may already be patched or diverged.")
else:
    text = text.replace(old_import, new_import)

replacements = [
    (
        'await _safe_reply(message, "You need the `manage_permissions` permission to use `!perm`.")',
        'p = command_prefix()\n        await _safe_reply(message, f"You need the `manage_permissions` permission to use `{p}perm`.")',
    ),
    ('p = "!"  # display only', "p = command_prefix()"),
    ('f"**!perm usage**\\n"', 'f"**{p}perm usage**\\n"'),
    (
        'await _safe_reply(message, "Usage: `!perm check @user`")',
        'await _safe_reply(message, f"Usage: `{command_prefix()}perm check @user`")',
    ),
    (
        'f"Usage: `!perm {sub} @user permission|rank <name>`"',
        'f"Usage: `{command_prefix()}perm {sub} @user permission|rank <name>`"',
    ),
    (
        'await _safe_reply(message, f"Unknown subcommand `{sub}`. Try `!perm help`.")',
        'await _safe_reply(message, f"Unknown subcommand `{sub}`. Try `{command_prefix()}perm help`.")',
    ),
    (
        'f"(Ask an owner to map your Discord role in `permissions.yml` or `!perm give`.)"',
        'f"(Ask an owner to map your Discord role in `permissions.yml` or `{command_prefix()}perm give`.)"',
    ),
]
for a, b in replacements:
    n = text.count(a)
    text = text.replace(a, b)
    print(f"  {n}x {a[:50]!r}...")

path.write_text(text, encoding="utf-8")
print("Done. Restart the daemon.")
