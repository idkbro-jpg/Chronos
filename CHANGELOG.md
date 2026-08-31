# Chronos changelog

## 2026-08-31 – restore truncated daemon + apply output cap / shared DM cooldown

### Critical
- **`daemon/main.py` was truncated** after several “restore” commits (101 lines, no `on_message` / `main()`). The last complete copy (`89bc88c`, 605 lines) is restored so the daemon can start and handle commands again.

### Robustness (intended 2026-08-30 work, now actually in the restored file)
- Command replies use `format_exec_replies` (`execution.max_output_chunks`, default 6) instead of unbounded local chunking.
- Local `_chunk_text` / `_safe_code_block` removed (non-positive limit could loop forever).
- Unlock and sudomode failed password guesses share one 15s cooldown; expired entries are pruned; a success clears that user’s cooldown.
- `!history` / `!last` truncate long lines and hard-cap the Discord message so a huge history cannot fail to send.

### Notes
- Approval, allowlist, lock/alarm semantics, whitelist defaults, and password logging are unchanged.
- Restart the daemon after pull: `systemctl --user restart chronos-daemon.service`.

## 2026-08-30 – actually apply output-chunk cap, history length, sudomode cooldown

See git history for earlier entries; this file keeps the full prior changelog below.

