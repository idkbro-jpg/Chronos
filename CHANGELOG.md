# Chronos changelog

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
- **Positive numeric config**: `0` / negative values for approval timeout, exec timeout, max output, rate-limit max/window, and history max-entries now fall back to defaults. Prevents `max_commands: 0` from rate-limiting every command, and `max_entries: 0` from unbounded history writes.

### Tests
- `_parse_positive_int` vs `_parse_int(0)` (audit channel may still be `0`).

### Notes
- Valid positive integers behave identically.
- No change to approval flow, allowlist shell policy, lock/alarm/sudomode TTL, or password logging.

## 2026-08-27 – lock hygiene, parse clarity, empty prefix guard

### Robustness
- **Rate-limit alarm**: when the limit is exceeded, `set_alarm` runs *after* releasing `_rate_lock` (no nested rate+flag locks).
- **`parse_command`**: single `split(None, 1)` for the command body — clearer, same behaviour for normal input; multi-word `!input text:…` / `!cmd …` preserved.
- **Empty `command_prefix`**: falls back to `!` at runtime (empty prefix would treat every message as a command). Soft warning on load; also warns if prefix is `?` (Receiver collision).
- **`export_recent`**: holds the logger write lock while reading log files so concurrent appends cannot tear lines mid-export.

### Tests
- Extra protocol cases (`!cmd`, multi-word input, bare prefix).
- Empty / whitespace-only prefix → `!`.

### Notes
- No change to allowlist, approval, lock/alarm/sudomode semantics, shell execution, or password logging.
- Valid configs and normal prefixes behave identically.
