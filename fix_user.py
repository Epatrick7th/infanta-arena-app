#!/usr/bin/env python3
"""Deprecated: use rotate_password.py instead.

This script used to DELETE the user and re-INSERT them, which assigns a new
id and orphans every event, expense and remittance keyed to their old
boss_id. Measured on a copy of the real database: doing that to boss_infanta
left them with 0 of their 31 events.

It now delegates to the safe in-place rotation so anyone following an old
note or shell history does not lose a partner's books.
"""
import os
import sys

print(__doc__)

username = os.environ.get("FIX_USER", "patrick")
password = os.environ.get("NEW_PASSWORD")

cmd = [sys.executable, "rotate_password.py", username]
if password:
    cmd += ["--password", password]

print(f"Delegating to: {' '.join(cmd)}\n")
os.execv(sys.executable, cmd)
