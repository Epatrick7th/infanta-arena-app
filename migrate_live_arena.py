"""Migration: add the live-arena columns and table to an existing database.

schema.sql already declares `fights.status` / `started_at` / `finished_at`
and the whole `fight_bets` table, but a database created before the
live-arena feature landed has none of them, because SQLite only applies
CREATE TABLE IF NOT EXISTS to tables that are missing entirely, never to
new columns on an existing table.

The result: /live-arena and every /api/live-fight/* route raised
"no such column: status" -> HTTP 500.

This migration is idempotent; running it twice is harmless.

Existing fights are marked 'finished' rather than 'pending', since they are
historical records with a winner already recorded. Leaving them 'pending'
would make the live dashboard offer a month-old fight as "up next".
"""
import sqlite3
import sys

DB = "data/sabong.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row


def columns(table):
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def tables():
    return {r[0] for r in con.execute(
        "select name from sqlite_master where type='table'")}


print("--- live-arena migration ---")
changed = False

# 1. fights.status / started_at / finished_at
cols = columns("fights")
if "status" not in cols:
    # SQLite cannot add a CHECK constraint via ALTER, so the constraint lives
    # in schema.sql for fresh databases; here we add the column with the same
    # default and backfill.
    con.execute("ALTER TABLE fights ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
    print("  added fights.status")
    changed = True
else:
    print("  fights.status already present")

if "started_at" not in cols:
    con.execute("ALTER TABLE fights ADD COLUMN started_at TEXT")
    print("  added fights.started_at")
    changed = True
else:
    print("  fights.started_at already present")

if "finished_at" not in cols:
    con.execute("ALTER TABLE fights ADD COLUMN finished_at TEXT")
    print("  added fights.finished_at")
    changed = True
else:
    print("  fights.finished_at already present")

# 2. historical fights are finished, not queued
n = con.execute(
    "select count(*) n from fights where status='pending' and winner is not null"
).fetchone()["n"]
if n:
    con.execute(
        "UPDATE fights SET status='finished' WHERE status='pending' AND winner IS NOT NULL")
    print(f"  marked {n} historical fights (with a winner) as finished")
    changed = True

# 3. fight_bets table
if "fight_bets" not in tables():
    con.execute("""
        CREATE TABLE fight_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boss_id INTEGER NOT NULL REFERENCES users(id),
            fight_id INTEGER NOT NULL REFERENCES fights(id),
            side TEXT NOT NULL CHECK(side IN ('Meron','Wala')),
            amount REAL NOT NULL,
            bettor_name TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','won','lost','push')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_by TEXT,
            deleted_at TEXT
        )""")
    for idx, col in (("idx_fight_bets_boss_id", "boss_id"),
                     ("idx_fight_bets_fight_id", "fight_id"),
                     ("idx_fight_bets_side", "side"),
                     ("idx_fight_bets_date", "created_at")):
        con.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON fight_bets({col})")
    print("  created fight_bets table and indexes")
    changed = True
else:
    print("  fight_bets already present")

con.commit()

# --- verify ---
cols = columns("fights")
missing = {"status", "started_at", "finished_at"} - cols
ok = not missing and "fight_bets" in tables()
print("\nfights columns now:", sorted(cols))
print("fight_bets present:", "fight_bets" in tables())
by_status = {r["status"]: r["n"] for r in con.execute(
    "select status, count(*) n from fights group by status")}
print("fights by status:", by_status)
con.close()

print("\n" + ("MIGRATION OK" if ok else f"INCOMPLETE, missing {missing}"))
sys.exit(0 if ok else 1)
