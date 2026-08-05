#!/usr/bin/env python3
"""Rotate one user's password in place, without touching their data.

The published credentials must be changed, but the obvious ways to do it are
both unsafe:

  - re-running setup_bosses.py DELETEs and re-INSERTs the user, so they get a
    new id and every event/expense/remittance keyed to their old boss_id is
    orphaned. Verified: boss_infanta went from 31 visible events to 0.
  - fix_user.py had the same delete-and-recreate flaw.

This updates password_hash on the existing row, so the id, and therefore
every record they own, is untouched.

Usage:

    python rotate_password.py boss_infanta                 # generates one
    python rotate_password.py boss_infanta --password ...  # or choose it
    python rotate_password.py --all                        # every account

The new password is printed once. It is not stored anywhere.
"""
import argparse
import secrets
import sqlite3
import string
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent / "data" / "sabong.db"
ALPHABET = string.ascii_letters + string.digits


def make_password(length=20):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def rotate(conn, username, password=None):
    row = conn.execute(
        "SELECT id, role FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return None, f"no such user: {username}"

    password = password or make_password()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (generate_password_hash(password, method="pbkdf2"), username),
    )
    # the id must not change; that is the whole point
    after = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    assert after["id"] == row["id"], "id changed: data would be orphaned"
    return password, row["role"]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("username", nargs="?", help="account to rotate")
    p.add_argument("--password", help="use this password instead of a random one")
    p.add_argument("--all", action="store_true",
                   help="rotate every boss, assistant and admin account")
    args = p.parse_args()

    if not args.username and not args.all:
        p.error("give a username, or --all")
    if args.all and args.password:
        p.error("--password cannot be combined with --all")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.all:
        targets = [r["username"] for r in conn.execute(
            "SELECT username FROM users ORDER BY role, username")]
    else:
        targets = [args.username]

    results = []
    for name in targets:
        pwd, role = rotate(conn, name, args.password)
        if pwd is None:
            print(f"  !! {role}")
            conn.close()
            sys.exit(1)
        results.append((name, role, pwd))

    conn.commit()
    conn.close()

    print("\nRotated. Save these now: they are not stored and cannot be recovered.")
    print("Give each person their password out of band, not over the same channel")
    print("as this output.\n")
    print("=" * 68)
    for name, role, pwd in results:
        print(f"  {name:20} {role:12} {pwd}")
    print("=" * 68)
    print("\nRecord ids are unchanged, so all existing data stays attached.")


if __name__ == "__main__":
    main()
