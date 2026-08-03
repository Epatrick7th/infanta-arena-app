#!/usr/bin/env python3
"""
Setup: Create Boss + Assistant pairs for each arena
Boss: View/Approve only
Assistant: Input/Data Entry
"""
import sqlite3
from werkzeug.security import generate_password_hash
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sabong.db"

# Boss & Assistant pairs
ARENAS = [
    {'boss': 'boss_infanta', 'boss_pwd': 'infanta123', 'asst': 'asst_infanta', 'asst_pwd': 'infanta_asst', 'arena': 'Infanta Arena'},
    {'boss': 'boss_royal', 'boss_pwd': 'royal123', 'asst': 'asst_royal', 'asst_pwd': 'royal_asst', 'arena': 'Royal Arena'},
    {'boss': 'boss_champion', 'boss_pwd': 'champion123', 'asst': 'asst_champion', 'asst_pwd': 'champion_asst', 'arena': 'Champion Arena'},
    {'boss': 'boss_phoenix', 'boss_pwd': 'phoenix123', 'asst': 'asst_phoenix', 'asst_pwd': 'phoenix_asst', 'arena': 'Phoenix Arena'},
    {'boss': 'boss_golden', 'boss_pwd': 'golden123', 'asst': 'asst_golden', 'asst_pwd': 'golden_asst', 'arena': 'Golden Arena'},
    {'boss': 'boss_elite', 'boss_pwd': 'elite123', 'asst': 'asst_elite', 'asst_pwd': 'elite_asst', 'arena': 'Elite Arena'},
]

def setup():
    """Create assistant accounts for each arena."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        print("\nCreating Boss + Assistant pairs for each arena...\n")
        print("="*90)
        
        for arena_config in ARENAS:
            boss_user = arena_config['boss']
            asst_user = arena_config['asst']
            asst_pwd = arena_config['asst_pwd']
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
            print(f"  BOSS       | Username: {boss_user:20} | Password: {arena_config['boss_pwd']}")
            print(f"  ASSISTANT  | Username: {asst_user:20} | Password: {asst_pwd}")
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
