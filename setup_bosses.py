#!/usr/bin/env python3
"""
Setup script: Create 6 boss accounts with isolated test data
"""
import os
import secrets
import sqlite3
import string
from werkzeug.security import generate_password_hash
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sabong.db"

# Boss configurations. Passwords are NOT stored here: this file is committed
# to a public repository, so anything written in it is public. Each account
# gets a fresh random password, printed once on creation. Set BOSS_PASSWORD
# to use a specific one instead (useful for scripted setup).
BOSSES = [
    {'username': 'boss_infanta', 'arena': 'Infanta Arena'},
    {'username': 'boss_royal', 'arena': 'Royal Arena'},
    {'username': 'boss_champion', 'arena': 'Champion Arena'},
    {'username': 'boss_phoenix', 'arena': 'Phoenix Arena'},
    {'username': 'boss_golden', 'arena': 'Golden Arena'},
    {'username': 'boss_elite', 'arena': 'Elite Arena'},
]

ALPHABET = string.ascii_letters + string.digits


def make_password(env_var="BOSS_PASSWORD", length=16):
    """A password from the environment, else a fresh random one."""
    supplied = os.environ.get(env_var)
    if supplied:
        return supplied
    return "".join(secrets.choice(ALPHABET) for _ in range(length))

def _abort_if_populated(conn, usernames):
    """Refuse to re-create users who already own records.

    Deleting and re-inserting a user gives them a new id, orphaning every
    event/expense/remittance keyed to the old boss_id. To change a password
    on a live database use rotate_password.py, which updates it in place.
    """
    import os
    if os.environ.get("SETUP_FORCE", "").lower() in ("1", "true", "yes"):
        return
    blocked = []
    for name in usernames:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (name,)).fetchone()
        if not row:
            continue
        owned = 0
        for table in ("events", "expenses", "cash_remittances", "fights"):
            try:
                owned += conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE boss_id = ?",
                    (row[0],)).fetchone()[0]
            except Exception:
                pass
        if owned:
            blocked.append((name, owned))
    if blocked:
        print("\nREFUSING TO RUN: these accounts already own records.\n")
        for name, n in blocked:
            print(f"  {name:20} {n} records would be orphaned")
        print("\nRe-creating them assigns new ids and strands that data.")
        print("To change a password on a live database, use:")
        print("    python rotate_password.py <username>")
        print("\nIf you really mean to wipe and re-create, set SETUP_FORCE=1.\n")
        raise SystemExit(1)


def setup_bosses():
    """Create 6 boss accounts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _abort_if_populated(conn, [b['username'] for b in BOSSES])
    
    try:
        print("Creating 6 boss accounts...\n")
        
        created = []
        for boss_config in BOSSES:
            username = boss_config['username']
            password = make_password()
            arena = boss_config['arena']
            created.append((username, password))
            
            # Delete if exists
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
            
            # Create boss user
            pass_hash = generate_password_hash(password, method='pbkdf2')
            cursor = conn.execute(
                """INSERT INTO users (username, password_hash, role, arena_name)
                   VALUES (?, ?, ?, ?)""",
                (username, pass_hash, 'boss', arena)
            )
            boss_id = cursor.lastrowid
            
            print(f"[OK] {username:20} | Password: {password:20} | Arena: {arena}")
        
        conn.commit()
        print("\n[DONE] All 6 boss accounts created!")
        print("\nSave these now. They are not stored anywhere and cannot be")
        print("recovered; re-run this script to issue new ones.")
        print("=" * 70)
        for username, password in created:
            print(f"  Username: {username:20} Password: {password}")
        print("=" * 70)
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    setup_bosses()
