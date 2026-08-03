#!/usr/bin/env python3
"""
Setup script: Create 6 boss accounts with isolated test data
"""
import sqlite3
from werkzeug.security import generate_password_hash
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sabong.db"

# Boss configurations
BOSSES = [
    {'username': 'boss_infanta', 'password': 'infanta123', 'arena': 'Infanta Arena'},
    {'username': 'boss_royal', 'password': 'royal123', 'arena': 'Royal Arena'},
    {'username': 'boss_champion', 'password': 'champion123', 'arena': 'Champion Arena'},
    {'username': 'boss_phoenix', 'password': 'phoenix123', 'arena': 'Phoenix Arena'},
    {'username': 'boss_golden', 'password': 'golden123', 'arena': 'Golden Arena'},
    {'username': 'boss_elite', 'password': 'elite123', 'arena': 'Elite Arena'},
]

def setup_bosses():
    """Create 6 boss accounts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        print("Creating 6 boss accounts...\n")
        
        for boss_config in BOSSES:
            username = boss_config['username']
            password = boss_config['password']
            arena = boss_config['arena']
            
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
        print("\nLogin instructions:")
        print("=" * 70)
        for boss_config in BOSSES:
            print(f"  Username: {boss_config['username']:20} Password: {boss_config['password']}")
        print("=" * 70)
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    setup_bosses()
