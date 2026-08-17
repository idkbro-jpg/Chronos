# Chronos changelog

## 2026-08-17 – allowlist hardening + state write safety

### Security
- **Allowlist matching tightened**: plain patterns are exact full-string matches only; globs (`*`, `?`) are full-string; `re:` uses `re.search`. Removed the previous loose substring fallback so a pattern like `uptime` cannot authorize `rm …; uptime`.

### Robustness
- **Atomic JSON writes** for `state/history.json` and `state/rate_limit.json` (temp file + rename) to avoid torn files on crash.
- **`!history` timestamps**: include the calendar date when an entry is not from today (UTC).

### Docs & tests
- `config.yml` comments updated for the stricter allowlist rules.
- Extra unit tests: substring injection blocked; glob/regex allowlist cases.

### Notes
- Unrestricted mode (the default) is unchanged. Existing allowlist configs that relied on accidental substring matches should switch to globs (`uptime*`) or `re:` patterns.

## 2026-08-09 – security + UX hardening

### Security
- **Whitelist-OFF warning**: loud message on config load, daemon start, `!status`, README, and help text. Default remains off for compatibility, but operators are told clearly that anyone in the channel can propose shell commands (and, with empty approval list, anyone can approve them).
- **Optional `execution.mode: allowlist`** with `allowed_patterns` (exact/glob/`re:` regex; substring removed later on 2026-08-17).
- **Optional `discord.audit_channel_id`** mirrors exec / lock / unlock / LUKS events.
- Soft validation for approval list empty, invalid timeouts, allowlist with no patterns.

### UX / robustness
- Rate-limit replies include approximate **retry_after** seconds.
- `!history` / `!last` backed by `state/history.json`.
- `!mouse` for basic click / move (ydotool / xdotool).
- Graceful shutdown on SIGTERM / SIGINT.
- Richer `!status` (whitelist state, execution mode).

### Docs & tests
- README security banner; expanded `docs/security.md` (whitelist, allowlist, audit, polkit snippet).
- Basic unit tests in `tests/test_core.py`.

### Notes
- No intentional behaviour removed. Defaults stay permissive so existing installs keep working; warnings push toward hardening.
