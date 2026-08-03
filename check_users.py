import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sabong.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Get all users
users = conn.execute("SELECT id, username, role, arena_name FROM users ORDER BY username").fetchall()

print("\nAll Users in System:")
print("="*80)
for u in users:
    print(f"  ID: {u['id']:2} | Role: {u['role']:12} | Username: {u['username']:20} | Arena: {u['arena_name']}")

print("\n\nBoss Accounts Only:")
print("="*80)
bosses = conn.execute("SELECT * FROM users WHERE role = 'boss' ORDER BY username").fetchall()
for b in bosses:
    print(f"  Username: {b['username']:20} | Arena: {b['arena_name']:20} | ID: {b['id']}")

conn.close()
