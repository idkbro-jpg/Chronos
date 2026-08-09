# Code review notes (2026-08-07)

## Fixed in same commit

| Issue | Severity | Fix |
|-------|----------|-----|
| `intents.dm_messages = True` does not exist in discord.py → crash on start | **Critical** | Removed; DMs work with `message_content` |
| `whitelist_enabled: true` + empty `allowed_user_ids` allowed everyone | Medium | Empty list = deny all |
| `!lock` had no approval → anyone could lock you out | Medium | Requires ✅ approval |
| Unlock DM brute-force unlimited | Medium | 15s cooldown after failed attempt |
| Optional `bot/` + `daemon/` same token fight for gateway | Medium | Documented; prefer daemon only |
| `!status` counted toward rate limit under pressure | Low | Status checked before rate limit |

## Known limitations (not bugs)

- Discord exposes **user ids**, not client IPs → no IP/VPN ban on this path
- `shell=True` is powerful; rely on approval + whitelist
- LUKS is for secondary volumes after boot only
- String password wipe in Python is best-effort (immutable strs)
- Screenshots need `grim` / spectacle / scrot installed

## Polish applied 2026-08-09

| Item | Notes |
|------|-------|
| Escape backticks in approval + output | `shared/discord_utils.py` + `_safe_code_block` |
| Persist rate-limit hits | `state/rate_limit.json` (window-aware) |
| `!help` / `!commands` | Full command overview |
| Richer `!status` | Shows rate-limit + LUKS device/mapper |
| Screenshot retention | Keep newest 10 only |
| Soft config validation | Warn on empty whitelist / placeholder LUKS device |

## Optional later polish

- Polkit/sudo rule template for cryptsetup
- Optional command allowlist / safer default than unrestricted shell
- Mouse simulation alongside keyboard
