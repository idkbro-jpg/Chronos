# Chronos – Internal AI Improvement Log

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
