# Chronos changelog

## 2026-08-31 – restore truncated daemon + apply output cap / shared DM cooldown

### Critical
- **`daemon/main.py` was truncated** after several restore commits (101 lines, no `on_message` / `main()`). The last complete copy (`89bc88c`, 605 lines) is restored so the daemon can start and handle commands again.

### Robustness (intended 2026-08-30 work, now actually in the restored file)
- Command replies use `format_exec_replies` (`execution.max_output_chunks`, default 6) instead of unbounded local chunking.
- Local `_chunk_text` / `_safe_code_block` removed (non-positive limit could loop forever).
- Unlock and sudomode failed password guesses share one 15s cooldown; expired entries are pruned; a success clears that user’s cooldown.
- `!history` / `!last` truncate long lines and hard-cap the Discord message so a huge history cannot fail to send.

### Notes
- Approval, allowlist, lock/alarm semantics, whitelist defaults, and password logging are unchanged.
- Restart the daemon after pull: `systemctl --user restart chronos-daemon.service`.

## 2026-08-30 – actually apply output-chunk cap, history length, sudomode cooldown

### Bugfix
- **Output flood cap was documented but not used.** `!cmd` replies now go through `format_exec_replies` in `shared/discord_utils.py`, which honours `execution.max_output_chunks` (default `6`) per stream and adds a short omitted note instead of posting every leftover chunk.

### Robustness
- **`!history`**: each command line is truncated; the whole reply is capped under Discord’s 2000-character limit so a long history cannot fail to send.
- **Sudomode DM**: failed password guesses now share the same 15s cooldown as unlock (and a failed unlock also delays the next sudomode guess). Expired cooldown entries are pruned.
- Duplicate `_chunk_text` / `_safe_code_block` helpers in the daemon were replaced by the shared helpers so a non-positive char limit cannot infinite-loop.

### Tests
- `format_exec_replies` chunk cap + empty output + `fit_discord_message`.

### Notes
- Small command output is unchanged (still one exit-code message plus one stdout/stderr block when content fits).
- No change to approval, allowlist, lock/alarm semantics, whitelist defaults, or password logging.

## 2026-08-29 – output flood cap, timeout stderr, rate-limit prune

### Robustness
- **Discord output cap**: stdout and stderr are each limited to `execution.max_output_chunks` replies (default `6`). Extra chunks are omitted with a short note instead of flooding the command channel. `0` / invalid values fall back to `6`.
- **Command timeout**: if a process times out, any partial stderr already captured is kept under the timeout message (stdout partial was already returned).
- **Rate-limit memory**: expired hit timestamps are dropped from the in-memory map when saving `state/rate_limit.json`, so the dict does not grow forever across users.

### Tests
- `chunk_text` (including non-positive limit guard).
- Executor timeout returns exit `1` and a timeout message.

### Notes
- Commands with small output behave identically.
- No change to approval, allowlist, lock/alarm/sudomode, whitelist defaults, or password logging.

## 2026-08-28 – DM whitelist, alarm markdown, positive numeric guards

### Security / robustness
- **DM unlock / sudomode**: when `whitelist_enabled` is true, non-allowlisted users get `Not on whitelist.` and cannot trigger scrypt or the global ALARM with a guessed password. Whitelist-off behaviour is unchanged.
- **`!alarm` reply**: missing closing backtick on `reason=` is fixed.
- **Positive numeric config**: `0` / negative values for approval timeout, exec timeout, max output, rate-limit max/window, and history max-entries now fall back to defaults.

### Notes
- Valid positive integers behave identically.
- No change to approval flow, allowlist shell policy, lock/alarm/sudomode TTL, or password logging.

## 2026-08-27 – lock hygiene, parse clarity, empty prefix guard

### Robustness
- **Rate-limit alarm**: when the limit is exceeded, `set_alarm` runs *after* releasing `_rate_lock`.
- **`parse_command`**: single `split(None, 1)` for the command body.
- **Empty `command_prefix`**: falls back to `!` at runtime.
- **`export_recent`**: holds the logger write lock while reading log files.

## 2026-08-26 – resilient numeric config values

### Robustness
- Config numeric getters fall back to defaults instead of raising `ValueError`.

## 2026-08-25 – UX: clearer README, setup installs deps, config comments

See earlier commits for full detail of 2026-08-09 through 2026-08-24 hardening (whitelist warnings, allowlist, audit channel, history, mouse, graceful shutdown, password log redaction, process-group timeout kill).
