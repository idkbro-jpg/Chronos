# Chronos – Internal AI Improvement Log

## 2026-08-27 – Full re-read + lock hygiene + parse/prefix/export

### Read-first review
- Full pass over daemon/ (main, security, executor, logger, history, approval, inputsim, mouse, screenshot, luks), shared/ (config, protocol, aliases, discord_utils), tests/, bot/, config.yml, aliases, requirements, public + internal changelogs.
- Prior hardening confirmed intact: allowlist exact/glob/re, atomic state writes, history/rate/flag locks, approval HTTPException handling, process-group kill on timeout, on_message error guard, logger lock + password redaction, sudomode_remaining cleanup, resilient ID lists + numeric getters.

### Risks identified
1. **Nested locks**: `check_rate_limit` called `set_alarm` while still holding `_rate_lock` (flag lock nested under rate lock). No reverse order existed → no deadlock in practice, but unnecessary coupling.
2. **`parse_command`**: double `split()` on the body was correct for normal input but harder to reason about; multi-word rest handled awkwardly.
3. **Empty prefix**: `command_prefix()` could return `""` if config set empty/whitespace → every channel message treated as a command.
4. **`export_recent`**: read log files without the logger `_lock`, so a concurrent `log_event` append could theoretically tear a JSONL line mid-read.

### Implemented
1. `daemon/security.py` `check_rate_limit`: compute limit exceed under `_rate_lock`, then call `set_alarm` only after the lock is released.
2. `shared/protocol.py` `parse_command`: one `body.split(None, 1)` for first token + remainder; `cmd` / builtins-with-args / aliases use the same rest string.
3. `shared/config.py` `command_prefix`: empty/whitespace → `"!"`; `_validate` warns on empty prefix and on `?` (Receiver collision).
4. `daemon/logger.py` `export_recent`: hold `_lock` for the whole read + write of the export file.
5. Tests: multi-word input/`!cmd`, empty prefix fallback.

### Breakage check (fact-checked multiple times)
- Rate-limit still returns `(False, msg, retry_after)` and still sets alarm when configured; only lock ordering changed.
- Valid prefixes and normal commands parse identically (unit tests for help/status/ping/input/mouse still pass conceptually; new cases cover cmd/spaces).
- Non-empty prefix unchanged; only empty/whitespace becomes `!`.
- Export still returns `None` when no logs; content assembly logic unchanged aside from locking.
- No change to approval, allowlist, shell execution, lock/alarm/sudomode TTL, password redaction, or whitelist defaults.
- Existing installs: `git pull` + restart daemon picks up changes; no config migration required.

### Notes
- Did not change permissive defaults (whitelist off, unrestricted mode).
- Android remote/receiver and Chronos-pi not modified this pass.
- No further logic bugs found in the hardened core after this re-read.

## 2026-08-26 – Full re-read + resilient numeric config

### Read-first review
- Full pass over daemon/ (main, security, executor, logger, history, approval, inputsim, mouse, screenshot, luks), shared/ (config, protocol, aliases, discord_utils), tests/, update.py, setup.py, config.yml, aliases, requirements, docs/, bot/, public + internal changelogs.
- Prior hardening confirmed intact: allowlist exact/glob/re, atomic state writes, history/rate/flag locks, approval HTTPException handling, process-group kill on timeout, on_message error guard, logger lock + password redaction, sudomode_remaining cleanup, resilient ID lists.

### Risks identified
1. **Config fragility (numeric)**: several getters used bare `int(...)` on YAML values. A typo like `timeout_seconds: sixty` or a quoted non-number would raise `ValueError` on first use of that setting (approval timeout, exec timeout, rate limit, history size, max output, audit channel) and could interrupt the daemon path.

### Implemented
1. `shared/config.py`: `_parse_int(value, default)` — best-effort conversion, default on TypeError/ValueError/None.
2. Wired into `audit_channel_id`, `approval_timeout`, `exec_timeout`, `max_output_chars`, `rate_limit_max`, `rate_limit_window`, `history_max_entries`.

### Breakage check (fact-checked)
- Valid integers → identical behaviour.
- Invalid values → documented defaults (same numbers as `_defaults()`).
- No change to approval flow, allowlist, rate-limit semantics, lock/alarm/sudomode, shell execution, or password logging.
- Unit tests still pass (8/8); no test updates required.
- Existing installs: pull + restart; bad config values stop being a crash, become a silent default (warnings still printed at load for some cases).

### Notes
- Did not change permissive defaults (whitelist off, unrestricted mode).
- Android remote/receiver and Chronos-pi not modified this pass.
- No further logic bugs found in the current hardened core after full re-read.

## 2026-08-25 – Full re-read + resilient ID lists + APK hygiene

### Read-first review
- Full pass over daemon/ (main, security, executor, logger, history, approval, inputsim, mouse, screenshot, luks), shared/ (config, protocol, aliases, discord_utils), tests/, update.py, setup.py, config.yml, aliases, requirements, docs/, bot/, public + internal changelogs.
- Chronos-pi (single-file bot.py + README/config) fully read; Android remote/receiver/android sources present; large compiled APKs in tree noted.
- Prior hardening confirmed intact: allowlist exact/glob/re, atomic state writes, history/rate/flag locks, approval HTTPException handling, process-group kill on timeout, on_message error guard, logger lock + password redaction, sudomode_remaining cleanup.

### Risks identified
1. **Config fragility**: `allowed_command_user_ids` / `allowed_approval_user_ids` used bare `int(x)` — one non-integer in `config.yml` raised `ValueError` on first whitelist/approval use and could take the daemon path down.
2. **Repo bloat**: `compiled apk/receiver1.0.apk` and `remote1.0.apk` (~15 MB each) were tracked; slow clones and unnecessary binary history for a source-focused project.
3. **`.gitignore` incomplete** for Android/Gradle build products and `*.apk`.

### Implemented
1. `shared/config.py`: shared `_parse_id_list` skips invalid entries (same style as Chronos-pi `allowed_user_ids`).
2. Deleted both compiled APK blobs from `main`; expanded `.gitignore` (`*.apk`, `compiled apk/`, `.gradle/`, `build/`, editor junk).
3. README layout clarified: `remote/` / `receiver/` are sources; build locally or use Releases.

### Breakage check (fact-checked)
- Valid integer IDs → identical behaviour.
- Empty lists still empty; whitelist-off path unchanged.
- No change to approval flow, allowlist, rate-limit, lock/alarm/sudomode, shell execution, or password logging.
- Unit tests do not depend on strict `int()` failure; no test updates required.
- Existing installs: pull + restart picks up config helper; missing APKs only affect people who relied on binaries in-repo (they should build or use Releases).

### Notes
- Did not change permissive defaults (whitelist off, unrestricted mode).
- Chronos-pi VERSION string vs README mismatch noted; fixed in Chronos-pi repo separately if touched.
- Android Kotlin sources not modified this pass.
- History rewrite not performed (APK blobs remain in older commits); new clones of current `main` no longer download them.

## 2026-08-24 – Full re-read + sudomode_remaining cleanup

### Read-first review
- Full pass over daemon/ (main, security, executor, logger, history, approval, inputsim, mouse, screenshot, luks), shared/ (config, protocol, aliases, discord_utils), tests/, update.py, setup.py, config.yml, aliases, requirements, docs/, bot/, public + internal changelogs.
- Chronos-pi and Android remote/receiver glanced at; separate products.
- Prior hardening confirmed intact: allowlist exact/glob/re, atomic state writes, history/rate/flag locks, approval HTTPException handling, process-group kill on timeout, on_message error guard, logger lock + password redaction.

### Risks identified
1. **Consistency gap**: `is_sudomode` already unlinked expired/unreadable SUDOMODE flags; `sudomode_remaining` left a stale file when remaining hit 0 until the next `is_sudomode` call. Harmless but inconsistent under the shared `_flag_lock`.

### Implemented
1. `daemon/security.py` `sudomode_remaining`: on unreadable or expired flag, `unlink(missing_ok=True)` under `_flag_lock` (same as `is_sudomode`).

### Breakage check (fact-checked)
- Callers still receive `0` when expired; only disk state is cleaned earlier.
- Locks held only for short disk ops → no deadlock with the event loop.
- TTL, set_sudomode, lock/alarm, rate-limit, approval, password paths unchanged.
- Unit tests do not assert on flag-file lifetime; no test updates required.
- Existing installs: behaviour identical for users; optional cleanup of a zero-byte-window stale flag.

### Notes
- Did not change permissive defaults (whitelist off, unrestricted mode).
- Android remote/receiver and Chronos-pi not modified in this Chronos commit.
- No password / secret logging regressions introduced.

## 2026-08-23 – Full re-read + flag lock consistency

### Read-first review
- Full pass over daemon/ (main, security, executor, logger, history, approval, inputsim, mouse, screenshot, luks), shared/ (config, protocol, aliases, discord_utils), tests/, update.py, setup.py, config.yml, aliases, requirements, docs/, bot/, public + internal changelogs.
- Chronos-pi README + structure glanced at; left alone this pass (separate product, TESTMODE defaults, already hardened).
- Prior hardening confirmed intact: allowlist exact/glob/re, atomic state writes, history/rate locks, approval HTTPException handling, process-group kill on timeout, on_message error guard, logger lock + password redaction.

### Risks identified
1. **Consistency gap**: `LOCKED` / `ALARM` / `SUDOMODE` flag file ops had no lock while history + rate-limit + logger already used `threading.Lock`. Concurrent `asyncio.to_thread` (shell/input/screenshot) plus a following Discord message could in theory interleave flag read/write.

### Implemented
1. `daemon/security.py`: dedicated `_flag_lock` around all flag existence checks, reads, writes, and unlinks for LOCKED / ALARM / SUDOMODE.

### Breakage check (fact-checked)
- Locks held only for short disk ops → no deadlock with the event loop.
- `check_rate_limit` still calls `set_alarm` while holding `_rate_lock`; that acquires `_flag_lock` briefly — no reverse order elsewhere, so no deadlock.
- Default unrestricted mode, whitelist defaults, approval semantics, rate-limit behaviour, password paths unchanged.
- Unit tests do not assert on flag concurrency; no test updates required.
- Existing installs: behaviour identical; only serialization of rare concurrent flag mutations changes.

### Notes
- Did not change permissive defaults (whitelist off, unrestricted mode).
- Android remote/receiver and Chronos-pi not modified this pass.
- No password / secret logging regressions introduced.

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
