# Permissions (new design)

## Quick mental model

Everything is **namespaced**:

| Namespace   | Meaning                                      |
|-------------|----------------------------------------------|
| `chronos:`  | Built-in Chronos commands (`screenshot`, `lock`, …) |
| `bash:`     | Shell commands                               |
| `alias:`    | Entries from `aliases.yml`                   |

Examples:
- `chronos:screenshot`
- `bash:ls`
- `bash:df*`
- `bash:*`          → unrestricted shell
- `alias:uptime`
- `chronos:*`       → all built-in commands

## File layout (`permissions.yml`)

```yaml
super_owner_id: "YOUR_DISCORD_ID"   # always has full rights + can write the file

presets:
  helper:
    needs_approval: true
    permissions: [chronos:history, chronos:screenshot, …]
  mod: …
  admin: …
  owner:
    needs_approval: false
    permissions: [chronos:*, alias:*, bash:*]

users:
  "1528851082288169061":
    rank: owner
    needs_approval: false

  "123456789012345678":
    rank: mod
    extra:          # can grant things the rank does not have
      - bash:ls
      - bash:uptime
    deny:           # can remove things the rank would give
      - chronos:lock
    needs_approval: true
```

## Evaluation order (the walls)

1. Is the user the `super_owner_id`? → full rights, no approval.
2. Is there a `users:` entry for this ID? → no → **deny**.
3. Take permissions from the rank/preset.
4. Add everything from `extra`.
5. Remove everything from `deny`.
6. Check the requested permission against the resulting set (exact + `namespace:*` + simple `bash:foo*` prefixes).
7. `needs_approval` is a **separate** boolean (user override → rank default → `true`).

## Safe-Mode

If `permissions.yml` is missing, unreadable, or the root is not a mapping:

- Only the hardcoded / env `CHRONOS_SUPER_OWNER_ID` (fallback) keeps rights.
- Everyone else is denied.
- A clear log line is printed.
- The next valid read leaves Safe-Mode automatically.

## Who may write the file

Only:

- the `super_owner_id`, and
- anyone who currently has `rank: owner`

All other write attempts are rejected.  
A short cooldown protects against concurrent writes.

## Always re-read

There is **no** long-lived in-memory cache.  
Every permission check opens the file again.  
For ≤ 100 users this is cheap and removes an entire class of bugs.

## Integration notes (for main.py later)

Public API in `shared.permissions`:

```python
from shared.permissions import (
    has_permission,
    needs_approval,
    can_write_permissions,
    get_effective_permissions,
    set_rank,
    give_permission,
    is_safe_mode,
    super_owner_id,
)

# examples
if not has_permission(message.author.id, "chronos:screenshot"):
    …

if needs_approval(message.author.id):
    # go through approval flow
    …

if can_write_permissions(message.author.id):
    ok, msg = set_rank(target_id, "mod", writer_id=message.author.id)
```

Map old bare names to the new namespace when you wire the checks, e.g.:

- old `"screenshot"` → `"chronos:screenshot"`
- old `"sudo"` / `"*"` → treat as `chronos:*` + `bash:*` (or just check the wildcards)
