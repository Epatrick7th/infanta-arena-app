import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sabong.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get events table info
cursor.execute("PRAGMA table_info(events)")
columns = cursor.fetchall()

print("Events table columns:")
for col in columns:
    print(f"  {col[1]:20} {col[2]}")

conn.close()
