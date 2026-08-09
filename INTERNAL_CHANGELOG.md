# Chronos – Internal AI Improvement Log

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
