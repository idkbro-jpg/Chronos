# Chronos – Internal AI Improvement Log

## 2026-08-22 – Full read-through + password log redaction

### Read-first review
- Full pass over daemon/, shared/, tests/, update.py, docs/, bot/, config, aliases, requirements, public + internal changelogs.
- Prior hardening (allowlist exact/glob/re, atomic state writes, history/rate locks, approval HTTPException handling, process-group kill on timeout, on_message error guard, logger lock) confirmed intact.
- Chronos-pi glanced at (separate single-file bot); left alone this pass.

### Risks identified
1. **Critical**: failed unlock / sudomode DMs logged `password_attempted` (raw string) into JSONL + journalctl human lines. Anyone with log access could recover near-miss passwords.
2. Logger had no defense-in-depth if a future caller passed secret-bearing keys in `extra`.

### Implemented
1. `daemon/main.py`: unlock_fail / sudomode_fail now pass only `password_len` (never the attempt string).
2. `daemon/logger.py`: `_sanitize_extra` strips keys in `{password_attempted, password, pass, secret, token}` and any key containing `password`; optional length retained. Human fail lines print `password_len` only.

### Breakage check (fact-checked)
- Unlock / alarm / sudomode success paths unchanged.
- Rate limit, approval, allowlist, shell execution, screenshot/input/mouse paths untouched.
- Unit tests do not assert on fail-log payload; no test updates required.
- Existing installs: behaviour identical; only log content for *failed* password attempts changes.
- Old log files may still contain historical plaintext attempts — operators should rotate if concerned.

### Notes
- Did not change permissive defaults (whitelist off, unrestricted mode) — warnings already push operators to harden.
- Android remote/receiver and Chronos-pi not modified this pass.

## 2026-08-21 – Full read-through + robustness

### Read-first review
- Complete pass over daemon/, shared/, tests/, update.py, docs/, bot/, android/, scripts/, config, aliases, requirements, changelogs.
- Also glanced at Chronos-pi (separate single-file bot) for consistency notes; no changes pushed there this pass.
- Confirmed prior hardening (allowlist exact/glob/re, atomic state writes, history/rate locks, approval HTTPException handling, whitelist warnings) is intact.

### Risks identified
1. Concurrent `log_event` from multiple `asyncio.to_thread` workers could interleave JSONL writes (no lock).
2. `subprocess.run(..., shell=True, timeout=…)` kills the shell but not always the whole process group → orphaned children after timeout.
3. Unexpected exceptions inside the long `on_message` chain left the user without a reply and only a console traceback.

### Implemented
1. `threading.Lock` in `daemon/logger.py` around open/write/flush.
2. `daemon/executor.py` rewritten to `Popen` + `start_new_session=True` + SIGTERM/SIGKILL process group on timeout; partial stdout still returned when available.
3. `on_message` parses then calls `_dispatch_command` under try/except; logs `kind=error` and replies with a short internal-error message.

### Breakage check (fact-checked)
- Locks held only for short disk ops → no deadlock with the event loop.
- Default `execution.mode: unrestricted`, whitelist defaults, approval semantics, rate-limit behaviour unchanged.
- Timeout path still returns `(1, stdout_partial, "Command timed out after Ns")` — same contract for callers.
- Existing unit tests still cover protocol/policy/history/password; no test changes required for these paths.
- Android self-message path and DM unlock path untouched.

### Notes
- Python string password wipe in LUKS remains best-effort (immutable strings) — documented limitation, not changed.
- Chronos-pi already has TESTMODE + allowlist-style patterns; left alone this pass to keep scope clear.

## 2026-08-19 – Thread safety + approval + ping

### Read-first review
- Full pass over daemon/, shared/, tests/, update.py, docs, bot/.
- Concurrent `asyncio.to_thread` (long shell / input / screenshot) can interleave with the next Discord message → history load-modify-save and rate-limit deque updates were racy.
- Missing reaction permissions caused unhandled HTTPException in approval flow.
- No lightweight liveness command (Chronos-pi already has ping).

### Implemented
1. `threading.Lock` in `daemon/history.py` and `daemon/security.py` for all load/save/check paths.
2. Approval: catch `discord.HTTPException` on `add_reaction`, edit prompt with guidance, return False.
3. `!ping` → message lag ms + gateway latency; handled before rate limit like status/help.
4. Logger `flush()` after each JSONL line.
5. Help/alias footer + unit test + public/internal changelogs.

### Breakage check
- Locks held only around short in-memory + disk ops (not across Discord awaits) → no deadlock with event loop.
- Default unrestricted mode and whitelist defaults unchanged.
- Atomic rename behaviour preserved; lock serializes concurrent renames.
- Existing commands and approval semantics unchanged when permissions are present.

## 2026-08-17 – Allowlist + atomic state

### Read-first review
- Full pass over daemon/, shared/, tests/, update.py, docs.
- Main risk found in allowlist: `if pat in cmd` substring fallback could authorize dangerous commands that merely contain an allowed token.
- State JSON writes were non-atomic (history + rate_limit).

### Implemented
1. Removed substring allowlist fallback; exact / glob fullmatch / `re:` only.
2. Atomic writes for history.json and rate_limit.json.
3. History display shows date when not today (UTC).
4. config.yml comment fix; expanded unit tests.
5. Public + internal changelog entries.

### Breakage check
- Default `execution.mode: unrestricted` → no behaviour change.
- Allowlist users who depended on substring must update patterns (documented).
- Atomic rename is same-dir → safe on typical Linux filesystems.

## 2026-08-09 – Full hardening pass

### Implemented and pushed
1. **Whitelist-OFF warning** (config validate, on_ready, !status, !help, README, docs/security.md).
2. **execution.mode allowlist** + patterns.
3. **Rate-limit retry_after** in Discord reply.
4. **History** `!history` / `!last` + `daemon/history.py`.
5. **Mouse** `daemon/mouse.py` + `!mouse`.
6. **Audit channel** optional.
7. **Graceful SIGTERM/SIGINT**.
8. Config soft type checks + approval empty note.
9. Unit tests `tests/test_core.py`.
10. Public `CHANGELOG.md`.

Defaults stay permissive so existing installs do not lock the owner out;
warnings push toward hardening.
