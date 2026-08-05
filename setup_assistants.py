#!/usr/bin/env python3
"""
Setup: Create Boss + Assistant pairs for each arena
Boss: View/Approve only
Assistant: Input/Data Entry
"""
import os
import secrets
import sqlite3
import string
from werkzeug.security import generate_password_hash
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sabong.db"

# Boss & Assistant pairs
# Passwords are NOT stored here: this file is public. Each assistant gets a
# fresh random password, printed once. Set ASSISTANT_PASSWORD to choose one.
ARENAS = [
    {'boss': 'boss_infanta', 'asst': 'asst_infanta', 'arena': 'Infanta Arena'},
    {'boss': 'boss_royal', 'asst': 'asst_royal', 'arena': 'Royal Arena'},
    {'boss': 'boss_champion', 'asst': 'asst_champion', 'arena': 'Champion Arena'},
    {'boss': 'boss_phoenix', 'asst': 'asst_phoenix', 'arena': 'Phoenix Arena'},
    {'boss': 'boss_golden', 'asst': 'asst_golden', 'arena': 'Golden Arena'},
    {'boss': 'boss_elite', 'asst': 'asst_elite', 'arena': 'Elite Arena'},
]

ALPHABET = string.ascii_letters + string.digits


def make_password(env_var="ASSISTANT_PASSWORD", length=16):
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


def setup():
    """Create assistant accounts for each arena."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # assistants own no rows themselves, so check the boss of the same arena:
    # re-creating an assistant is only safe while that arena has no data
    _abort_if_populated(conn, [a['boss'] for a in ARENAS])
    
    try:
        print("\nCreating Boss + Assistant pairs for each arena...\n")
        print("="*90)
        
        for arena_config in ARENAS:
            boss_user = arena_config['boss']
            asst_user = arena_config['asst']
            asst_pwd = make_password()
            arena = arena_config['arena']
            
            # Delete if exists
            conn.execute("DELETE FROM users WHERE username = ?", (asst_user,))
            
            # Create assistant user
            pass_hash = generate_password_hash(asst_pwd, method='pbkdf2')
            cursor = conn.execute(
                """INSERT INTO users (username, password_hash, role, arena_name)
                   VALUES (?, ?, ?, ?)""",
                (asst_user, pass_hash, 'assistant', arena)
            )
            asst_id = cursor.lastrowid
            
            print(f"Arena: {arena}")
            print(f"  BOSS       | Username: {boss_user:20} | (unchanged)")
            print(f"  ASSISTANT  | Username: {asst_user:20} | Password: {asst_pwd}")
            print("  ^ save this now; it is not stored and cannot be recovered")
            print()
        
        conn.commit()
        
        print("="*90)
        print("\n[DONE] Boss + Assistant accounts created!\n")
        
        # Show all users
        users = conn.execute(
            "SELECT username, role, arena_name FROM users WHERE role IN ('boss', 'assistant') ORDER BY arena_name, role DESC"
        ).fetchall()
        
        print("All Boss + Assistant Accounts:")
        print("="*90)
        for u in users:
            role_str = "BOSS".ljust(11) if u['role'] == 'boss' else "ASSISTANT"
            print(f"  {role_str} | {u['username']:20} | {u['arena_name']}")
        print("="*90 + "\n")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    setup()
