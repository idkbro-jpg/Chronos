# Chronos changelog

## 2026-08-09 – security + UX hardening

### Security
- **Whitelist-OFF warning**: loud message on config load, daemon start, `!status`, README, and help text. Default remains off for compatibility, but operators are told clearly that anyone in the channel can propose shell commands (and, with empty approval list, anyone can approve them).
- **Optional `execution.mode: allowlist`** with `allowed_patterns` (substring, glob, or `re:` regex).
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
