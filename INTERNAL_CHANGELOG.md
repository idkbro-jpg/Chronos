# Chronos – Internal AI Improvement Log (local only, not pushed unless asked)

All times UTC.

## 2026-08-08 23:58 – Session start
- Full permission granted by owner to improve Chronos.
- Goal: high-value, low-risk improvements only. Fact-check every change against existing code.
- Strategy: read → plan → edit → verify → document here. No force-push. Prefer local commits first.

### Planned improvements (priority order)
1. Markdown escaping for Discord (approval + output) – prevents broken messages when commands contain backticks.
2. Add `!help` builtin.
3. Richer `!status`.
4. Safer / cleaner screenshot handling (limit retention).
5. Light config validation on reload.
6. Optional persistence for rate-limit hits (simple JSON in state/).
7. Small robustness polish in executor / approval.

---

## 2026-08-09 00:05 – Implemented improvements

### 1. Markdown safety
- Added `shared/discord_utils.py` with `escape_backticks` / `safe_inline`.
- `daemon/approval.py` now escapes backticks in the approval prompt so commands containing `` ` `` cannot break Discord formatting.
- `daemon/main.py` `_send_output` sanitises triple-backticks inside stdout/stderr so nested code fences no longer close early.

### 2. Help command
- New builtins `!help` / `!commands` → `__HELP__`.
- `format_help()` in `shared/protocol.py`.
- Handled in `daemon/main.py` (before rate-limit, same as status).

### 3. Richer status
- `!status` now also shows rate-limit settings and (when LUKS enabled) device → mapper.

### 4. Screenshot retention
- `daemon/screenshot.py` keeps only the newest 10 `shot-*.png` files under `state/screenshots/`.

### 5. Rate-limit persistence
- Hits are now lightly persisted to `state/rate_limit.json`.
- Survives daemon restarts within the configured window.
- Failures to read/write the file never block commands.

### 6. Soft config validation
- On load / `!reload`, warns if whitelist is enabled with empty list, or LUKS is enabled with placeholder device.

All changes compile cleanly. No behaviour removed; only additive safety + UX.
