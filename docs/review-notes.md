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
- Rate-limit state is in-memory (resets on daemon restart)
- `shell=True` is powerful; rely on approval + whitelist
- LUKS is for secondary volumes after boot only
- String password wipe in Python is best-effort (immutable strs)
- Screenshots need `grim` / spectacle / scrot installed

## Optional later polish

- Escape backticks in command text before putting in Discord markdown
- Persist rate-limit hits to disk if you care across restarts
- Polkit/sudo rule template for cryptsetup
