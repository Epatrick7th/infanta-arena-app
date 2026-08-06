#!/usr/bin/env python3
"""Deprecated: use rotate_password.py instead.

This script used to DELETE the user and re-INSERT them, which assigns a new
id and orphans every event, expense and remittance keyed to their old
boss_id. Measured on a copy of the real database: doing that to boss_infanta
left them with 0 of their 31 events.

It now delegates to the safe in-place rotation so anyone following an old
note or shell history does not lose a partner's books.

    set FIX_USER=boss_infanta      (optional, defaults to patrick)
    set NEW_PASSWORD=...           (optional, one is generated otherwise)
    python fix_user.py
"""
import os
import subprocess
import sys

# Printed before delegating, and flushed: subprocess/exec would otherwise
# discard anything still sitting in this process's stdout buffer, which is
# how the deprecation notice went missing.
print(__doc__, flush=True)

username = os.environ.get("FIX_USER", "patrick")
password = os.environ.get("NEW_PASSWORD")

cmd = [sys.executable, "rotate_password.py", username]
if password:
    cmd += ["--password", password]

print(f"Delegating to: rotate_password.py {username}\n", flush=True)

# subprocess rather than execv so this process's output survives and the
# child's exit code is passed through faithfully
sys.exit(subprocess.run(cmd).returncode)
