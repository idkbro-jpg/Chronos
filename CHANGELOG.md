# Chronos changelog

## 2026-08-30 – actually apply output-chunk cap, history length, sudomode cooldown

### Bugfix
- **Output flood cap was documented but not used.** `!cmd` replies now go through `format_exec_replies` in `shared/discord_utils.py`, which honours `execution.max_output_chunks` (default `6`) per stream and adds a short “omitted” note instead of posting every leftover chunk.

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
