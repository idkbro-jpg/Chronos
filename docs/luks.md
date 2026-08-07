# LUKS unlock via Chronos

## What this is for

Unlock a **secondary** LUKS volume **after** the machine has already booted
and Chronos is running (e.g. extra disk, data partition).

## What this is NOT

It cannot unlock **root/home before the OS is up**.  
If the system is stuck at the early LUKS password prompt, no user-space
daemon (including Chronos) is running yet.

For that you need one of:

- Dropbear SSH in initramfs
- systemd systemd-cryptenroll + TPM/FIDO
- a tiny unencrypted rescue partition with network + unlock agent

A 2 MB unencrypted partition only helps if something on it starts **before**
the encrypted root is needed and has network access (initramfs territory).

## Setup

1. Install deps:

```bash
cd ~/Chronos
source venv/bin/activate
pip install -r requirements.txt
```

2. Store encrypted password (interactive, never typed in Discord):

```bash
python -m scripts.set_luks_password
```

Creates (gitignored):

- `secrets/machine.key` – random local secret
- `secrets/luks.enc` – LUKS passphrase encrypted with
  `SHA256(bot_token + machine_secret)` → Fernet

3. Edit `config.yml`:

```yaml
luks:
  enabled: true
  device: "/dev/disk/by-uuid/YOUR-UUID"   # prefer by-uuid
  mapper_name: "crypt_data"
  post_unlock_command: "mount /dev/mapper/crypt_data /mnt/data"  # optional
```

4. Restart daemon:

```bash
systemctl --user restart chronos-daemon.service
```

5. In Discord:

```text
!luksunlock
```

Approve with ✅.

## Security notes

- Passphrase never appears in Discord.
- Encrypted at rest; needs both bot token **and** `machine.key`.
- If the bot token leaks **and** someone copies `secrets/`, they can decrypt.
  Protect `secrets/` (permissions `700` / files `600`).
- Prefer `allowed_user_ids` in config so only you can trigger unlock.
- `cryptsetup` usually needs root → run daemon as user with proper
  polkit/sudo rule, or only unlock devices your user may open.

### Optional sudoers snippet (careful)

```
%wheel ALL=(root) NOPASSWD: /usr/sbin/cryptsetup luksOpen *
```

Better: narrow to exact device path.

## Commands

| Command | Action |
|---------|--------|
| `!luksunlock` | Decrypt stored passphrase → `cryptsetup luksOpen` |
