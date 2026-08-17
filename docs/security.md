# Security features

## Critical: whitelist

If `discord.whitelist_enabled` is **false**, anyone who can post in the
command channel can propose shell commands. With an empty
`approval.allowed_user_ids`, any non-bot reactor can approve them.

That combination can mean **remote shell access to the machine** for
anyone in the server/channel.

**Turn the whitelist on** unless the channel is strictly private and trusted:

```yaml
discord:
  whitelist_enabled: true
  allowed_user_ids:
    - YOUR_DISCORD_USER_ID
approval:
  allowed_user_ids:
    - YOUR_DISCORD_USER_ID
```

The daemon logs a clear warning on every start / `!reload` when whitelist is off.
`!status` also shows `OFF` with a warning in that case.

## Important limitation (IPs)

Discord bots **do not receive the end-user's IP** for normal messages.
We log and rate-limit by **Discord user id** instead.

## Lock mode

```bash
python -m scripts.set_lock_password
```

```text
!lock
```

Unlock only via **DM**: `unlock <password>`

## Rate limit / allowlist / audit

See `config.yml` for `rate_limit`, `execution.mode: allowlist`, and
`discord.audit_channel_id`.

Allowlist patterns (when `execution.mode: allowlist`):

- plain string without `*` / `?` → **exact** full command match
- glob with `*` / `?` → full-string glob
- `re:REGEX` → `re.search` on the command string

There is **no** loose substring match. A pattern of `uptime` does not
authorize `rm -rf /; uptime`. Prefer `uptime*` or `re:^uptime\b` when you
need prefixes.

## Logs

```text
logs/chronos-YYYY-MM-DD.log
!exportlog
!history
```
