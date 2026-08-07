# `!input` – keyboard simulation

Not a keylogger. Only the Discord command you send is logged
(e.g. `!input alt p`), never continuous key capture.

## Examples

```text
!input alt p          → Alt+P
!input ctrl c         → Ctrl+C
!input ctrl shift t   → Ctrl+Shift+T
!input enter
!input super d
!input text:hello     → types the text
!input "hello world"  → same
```

Spaces separate keys. `alt+p` style is not required — use `alt p`.

## Setup (Bazzite / Wayland)

Recommended:

```bash
# ydotool – works on Wayland
# (exact install depends on your setup; often via distrobox or rpm)
```

Fallbacks tried in order: **ydotool** → **wtype** → **xdotool**.

`ydotool` may need its daemon (`ydotoold`) running and permission to
`/dev/uinput`.

## Security

Requires normal Chronos approval (✅). Same power as remote control of
the focused window — use whitelist + lock when away.
