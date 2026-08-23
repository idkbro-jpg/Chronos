# Chronos changelog

## 2026-08-23 – thread-safe lock / alarm / sudomode flags

### Robustness
- **Flag file ops serialized**: `LOCKED`, `ALARM`, and `SUDOMODE` reads/writes now use a dedicated `threading.Lock` (same idea as history + rate-limit). Concurrent `asyncio.to_thread` work cannot interleave flag mutations.

### Notes
- No change to default security posture, allowlist rules, approval flow, or command execution semantics.
- Locks are held only for short disk ops → no deadlock with the event loop.

## 2026-08-22 – never log unlock/sudomode password attempts

### Security
- **Failed unlock / sudomode DMs** no longer write the attempted password into JSONL logs or journalctl. Only `password_len` is recorded for diagnostics.
- **Logger defense-in-depth**: any `extra` key that looks like a password/secret is stripped (or reduced to length) before disk/stdout write.

### Notes
- No change to lock/alarm/sudomode behaviour, approval flow, or command execution.
- Existing log files from before this change may still contain historical attempts; rotate or delete if needed.

## 2026-08-21 – logger lock + timeout process-group kill + error guard

### Robustness
- **Thread-safe logger**: `threading.Lock` around append + flush so concurrent `asyncio.to_thread` work cannot interleave JSONL lines in daily log files.
- **Command timeout kills process group**: executor starts a new session (`start_new_session=True`) and on timeout sends SIGTERM (then SIGKILL) to the whole group. Prevents orphaned children from `shell=True` pipelines after a timeout.
- **Unhandled exception guard** in `on_message`: unexpected errors are logged (`kind=error`) and the user gets a short reply instead of a silent failure.

### Notes
- No change to default security posture, allowlist rules, or command semantics.
- Timeouts still return exit code 1 with a clear stderr message; partial stdout captured when available.

## 2026-08-19 – thread-safe state + approval robustness + !ping

### Robustness
- **Thread-safe history and rate-limit persistence**: `threading.Lock` around load/save so concurrent work from `asyncio.to_thread` cannot tear `state/history.json` or race hit counts in `state/rate_limit.json`.
- **Approval reactions**: if the bot cannot add ✅/❌ (missing *Add Reactions* / related perms), reply with a clear error and do **not** execute.
- **Logger flush** after each append so recent lines survive hard process kills.

### UX
- **`!ping`**: message lag + gateway latency, no approval, before rate limit (same class as `!status` / `!help`).

### Docs & tests
- Help / alias footer mention `!ping`.
- Unit test for `!ping` parse.

### Notes
- No change to default security posture or command semantics for shell execution.
- Existing installs keep working; locks only hold during short disk operations.

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
