#!/usr/bin/env python3
"""
Migration: Add approval workflow to transactions
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sabong.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("Adding approval workflow columns...\n")
        
        tables = {
            'events': 'Events',
            'event_revenue': 'Revenue',
            'expenses': 'Expenses',
            'cash_remittances': 'Remittances'
        }
        
        for table, label in tables.items():
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN approval_status TEXT DEFAULT 'pending' CHECK(approval_status IN ('pending', 'approved', 'rejected'))")
                print(f"  [OK] {label:15} - Added approval_status")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e):
                    print(f"  [-] {label:15} - approval_status already exists")
                else:
                    raise
            
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN approved_by TEXT")
                print(f"  [OK] {label:15} - Added approved_by")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e):
                    print(f"  [-] {label:15} - approved_by already exists")
                else:
                    raise
            
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN approved_at TEXT")
                print(f"  [OK] {label:15} - Added approved_at")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e):
                    print(f"  [-] {label:15} - approved_at already exists")
                else:
                    raise
        
        conn.commit()
        print("\n[DONE] Approval workflow added!\n")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
