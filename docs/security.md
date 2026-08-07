# Security features

## Important limitation (IPs)

Discord bots **do not receive the end-user's IP** for normal messages.
Traffic is Discord → your daemon. Therefore:

- We **cannot** ban "the IP that typed !ping"
- We **cannot** detect "VPN IP" on the Discord path
- We log and rate-limit by **Discord user id** instead

If you later expose a public HTTP endpoint, IP bans belong there — not here.

## Lock mode

```bash
python -m scripts.set_lock_password   # long Bitwarden password
```

```text
!lock
```

Everything blocked until you **DM the bot**:

```text
unlock dein-langes-passwort
```

Wrong password → alarm on.

Local clear (on the machine):

```bash
rm ~/Chronos/state/LOCKED ~/Chronos/state/ALARM
```

## Rate limit

In `config.yml`:

```yaml
rate_limit:
  enabled: true
  max_commands: 20
  window_seconds: 60
  trigger_alarm: true
```

Exceeding the limit logs the user id and can raise alarm.

## Whitelist

```yaml
discord:
  whitelist_enabled: true
  allowed_user_ids:
    - YOUR_DISCORD_USER_ID
```

## Logs

```text
logs/chronos-YYYY-MM-DD.log   # JSON lines
!exportlog                    # upload recent logs as file
```

You are logged too — intentional.

## Screenshot

```text
!screenshot
```

Needs `grim` (Wayland/Bazzite recommended), or spectacle/scrot.
