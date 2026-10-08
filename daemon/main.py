"""
Chronos Daemon – watches Discord, approves, executes.

One gateway connection. Prefer running only this process (not bot/ + daemon
with the same token at once).

NOTE: Source is split across _main_part_*.txt for transport; assembled at import.
"""
from pathlib import Path

_dir = Path(__file__).resolve().parent
_parts = sorted(_dir.glob("_main_part_*.txt"))
if not _parts:
    raise RuntimeError(
        "daemon/_main_part_*.txt missing. Restore with:\n"
        "  curl -sL https://raw.githubusercontent.com/idkbro-jpg/Chronos/main/daemon/main.py -o daemon/main.py\n"
        "  python3 scripts/apply_prefix_fix.py"
    )
_code = "".join(p.read_text(encoding="utf-8") for p in _parts)
exec(compile(_code, str(_dir / "main.py"), "exec"), globals())
