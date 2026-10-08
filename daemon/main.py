"""
Chronos Daemon – temporarily broken on this branch due to upload limits.

RESTORE (run from repo root on this branch):

  curl -sL https://raw.githubusercontent.com/idkbro-jpg/Chronos/main/daemon/main.py -o daemon/main.py
  python3 scripts/apply_prefix_fix.py
  git add daemon/main.py
  git commit -m "fix: restore main.py with command_prefix() in !perm strings"

Then delete the leftover part files if present:

  git rm -f daemon/_main_part_*.txt 2>/dev/null || true

After that, restart the daemon as usual.
"""

raise SystemExit(
    "daemon/main.py is not restored yet.\n"
    "Run:\n"
    "  curl -sL https://raw.githubusercontent.com/idkbro-jpg/Chronos/main/daemon/main.py -o daemon/main.py\n"
    "  python3 scripts/apply_prefix_fix.py\n"
)
