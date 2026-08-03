#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration script: Add boss_id and arena support to existing database
"""
import sqlite3
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "data/sabong.db"

if not os.path.exists(DB_PATH):
    print("No existing database. Will create fresh on app start.")
    exit(0)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    print("Starting migration...")
    
    # 1. Add columns to existing tables if they don't exist
    tables_to_migrate = {
        'events': 'boss_id',
        'fights': 'boss_id',
        'event_revenue': 'boss_id',
        'expenses': 'boss_id',
        'cash_remittances': 'boss_id',
        'personnel': 'boss_id',
        'shift_roster': 'boss_id',
        'personnel_penalties': 'boss_id'
    }
    
    for table, col in tables_to_migrate.items():
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER DEFAULT 1")
            print(f"  [OK] Added {col} to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e):
                print(f"  - {col} already exists in {table}")
            else:
                raise
    
    # 2. Add arena_id to events if not exists
    try:
        cursor.execute("ALTER TABLE events ADD COLUMN arena_id TEXT DEFAULT 'Infanta'")
        print("  [OK] Added arena_id to events")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("  - arena_id already exists in events")
        else:
            raise
    
    # 3. Add location to events if not exists
    try:
        cursor.execute("ALTER TABLE events ADD COLUMN location TEXT")
        print("  [OK] Added location to events")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("  - location already exists in events")
        else:
            raise
    
    # 4. Add role constraints to users if needed
    try:
        cursor.execute("PRAGMA table_info(users)")
        cols = cursor.fetchall()
        has_boss_id = any(c[1] == 'boss_id' for c in cols)
        if not has_boss_id:
            cursor.execute("ALTER TABLE users ADD COLUMN boss_id INTEGER")
            cursor.execute("ALTER TABLE users ADD COLUMN arena_name TEXT")
            print("  [OK] Added boss_id and arena_name to users")
        else:
            print("  - users already has boss_id")
    except Exception as e:
        print(f"  - users migration skipped: {e}")
    
    conn.commit()
    print("\n[DONE] Migration complete!")
    
except Exception as e:
    conn.rollback()
    print(f"\n[ERROR] Migration failed: {e}")
    exit(1)
finally:
    conn.close()
