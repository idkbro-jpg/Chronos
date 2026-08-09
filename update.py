#!/usr/bin/env python3
"""
Chronos updater – run from the project root:

    python update.py
    ./update.py

Steps:
  1) git fetch + pull (refuses if local uncommitted changes would be overwritten)
  2) pip install -r requirements.txt (venv if present)
  3) systemctl --user restart chronos-daemon.service (if unit exists)

Flags:
  --no-restart   skip systemd restart
  --force        git reset --hard origin/<branch> (DESTROYS local commits on that branch)
  --stash        git stash before pull, stash pop after
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], *, check: bool = True, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check)


def have(cmd: str) -> bool:
    from shutil import which

    return which(cmd) is not None


def python_for_pip() -> list[str]:
    venv_py = ROOT / "venv" / "bin" / "python"
    if venv_py.is_file():
        return [str(venv_py)]
    return [sys.executable]


def git_dirty() -> bool:
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return bool(r.stdout.strip())


def current_branch() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout.strip()


def unit_exists(name: str = "chronos-daemon.service") -> bool:
    r = subprocess.run(
        ["systemctl", "--user", "cat", name],
        capture_output=True,
    )
    return r.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Chronos from git + restart daemon")
    parser.add_argument("--no-restart", action="store_true", help="Do not restart systemd unit")
    parser.add_argument(
        "--force",
        action="store_true",
        help="git reset --hard to origin/branch (discards local commits/changes on this branch)",
    )
    parser.add_argument(
        "--stash",
        action="store_true",
        help="git stash -u before pull, stash pop after",
    )
    args = parser.parse_args()

    os.chdir(ROOT)
    print(f"[update] root: {ROOT}")

    if not (ROOT / ".git").is_dir():
        print("[update] Not a git repo. Abort.")
        return 1

    if not have("git"):
        print("[update] git not found.")
        return 1

    branch = current_branch()
    print(f"[update] branch: {branch}")

    stashed = False
    if args.stash and git_dirty():
        run(["git", "stash", "push", "-u", "-m", "chronos-update-auto"])
        stashed = True
    elif git_dirty() and not args.force:
        print("[update] Local changes detected:")
        run(["git", "status", "--short"], check=False)
        print("[update] Commit/stash them, or re-run with --stash or --force.")
        return 1

    run(["git", "fetch", "origin"])

    if args.force:
        run(["git", "reset", "--hard", f"origin/{branch}"])
    else:
        # Prefer merge pull so local commits are kept when possible
        r = subprocess.run(
            ["git", "pull", "--ff-only", "origin", branch],
            cwd=ROOT,
        )
        if r.returncode != 0:
            print("[update] ff-only pull failed; trying normal pull…")
            run(["git", "pull", "origin", branch])

    if stashed:
        pop = subprocess.run(["git", "stash", "pop"], cwd=ROOT)
        if pop.returncode != 0:
            print("[update] stash pop had conflicts — resolve manually.")

    py = python_for_pip()
    req = ROOT / "requirements.txt"
    if req.is_file():
        print("[update] installing requirements…")
        run([*py, "-m", "pip", "install", "-r", str(req)])
    else:
        print("[update] no requirements.txt — skip pip")

    if args.no_restart:
        print("[update] skip restart (--no-restart)")
    elif have("systemctl") and unit_exists():
        print("[update] restarting chronos-daemon.service…")
        run(["systemctl", "--user", "daemon-reload"], check=False)
        run(["systemctl", "--user", "restart", "chronos-daemon.service"])
        run(["systemctl", "--user", "--no-pager", "status", "chronos-daemon.service"], check=False)
    else:
        print("[update] no user unit chronos-daemon.service — restart the daemon yourself.")

    print("[update] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
