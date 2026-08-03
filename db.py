import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from werkzeug.security import check_password_hash, generate_password_hash

# Data directory for persistent DB
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))
DB_PATH = DATA_DIR / "sabong.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def _today() -> str:
    return date.today().isoformat()

NOT_DELETED = "deleted_at IS NULL"
ROLES = ["viewer", "staff", "admin", "super_admin"]
ROLE_RANK = {r: i for i, r in enumerate(ROLES)}
ROLE_LABELS = {"super_admin": "Super Admin", "admin": "Admin", "staff": "Staff", "viewer": "Viewer"}
DEFAULT_ROLE = "staff"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _paginate(conn, select_cols: str, from_where_sql: str, params: list, order_by: str, limit: int, offset: int) -> dict:
    """Paginate query results."""
    total = conn.execute(f"SELECT COUNT(*) {from_where_sql}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT {select_cols} {from_where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return {"rows": [dict(r) for r in rows], "total": total}

def init_db():
    """Initialize database and run migrations."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    
    try:
        # Check if users table exists to see if DB is initialized
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        if not cursor.fetchone():
            # Fresh DB - load schema
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            
            # Seed 3 shift types
            conn.executemany(
                "INSERT INTO shift_types (name, start_time, end_time) VALUES (?, ?, ?)",
                [("Morning", "06:00", "14:00"), ("Evening", "14:00", "22:00"), ("Night", "22:00", "06:00")],
            )
            conn.commit()
            
            # Seed penalty defaults (use fresh connection)
            conn2 = get_connection()
            conn2.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("personnel_late_penalty_default", "200"),
            )
            conn2.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("personnel_absence_penalty_default", "500"),
            )
            conn2.commit()
            conn2.close()
        
        conn.commit()
    finally:
        conn.close()

# --- Users ---

def create_user(username: str, password: str, role: str = DEFAULT_ROLE) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), role),
    )
    conn.commit()
    conn.close()

def verify_user(username: str, password: str):
    """Returns user row on correct password, else None."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row and check_password_hash(row["password_hash"], password):
        return dict(row)
    return None

def list_users(limit=None, offset=0):
    conn = get_connection()
    if limit is not None:
        result = _paginate(conn, "id, username, role, created_at", "FROM users", [], "username COLLATE NOCASE", limit, offset)
        conn.close()
        return result
    rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY username COLLATE NOCASE").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_user_role(username: str, role: str) -> bool:
    conn = get_connection()
    cur = conn.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated

def delete_user(username: str) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted

# --- Events & Fights ---

def insert_event(date_str: str, name: str, event_type: str, note: str = None, created_by: str = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO events (date, name, event_type, note, created_by) VALUES (?, ?, ?, ?, ?)",
        (date_str, name, event_type, note, created_by),
    )
    conn.commit()
    event_id = cur.lastrowid
    conn.close()
    return event_id

def get_event(event_id: int):
    conn = get_connection()
    row = conn.execute(f"SELECT * FROM events WHERE id = ? AND {NOT_DELETED}", (event_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def list_events(date_from=None, date_to=None, limit=None, offset=0):
    conn = get_connection()
    where = [NOT_DELETED]
    params = []
    if date_from:
        where.append("date >= ?")
        params.append(date_from)
    if date_to:
        where.append("date <= ?")
        params.append(date_to)
    from_where = f"FROM events WHERE {' AND '.join(where)}"
    
    if limit is not None:
        result = _paginate(conn, "*", from_where, params, "date DESC, id DESC", limit, offset)
        conn.close()
        return result
    rows = conn.execute(f"SELECT * {from_where} ORDER BY date DESC, id DESC", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_event(event_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute(f"UPDATE events SET deleted_at = datetime('now') WHERE id = ? AND {NOT_DELETED}", (event_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted

# Fights

def insert_fight(event_id: int, fight_number: int, date_str: str, meron: str, wala: str, winner: str = None, plasada: float = None, pit_fee: float = None, notes: str = None, created_by: str = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO fights (event_id, fight_number, date, meron_owner, wala_owner, winner, plasada_amount, pit_fee, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, fight_number, date_str, meron, wala, winner, plasada, pit_fee, notes, created_by),
    )
    conn.commit()
    fight_id = cur.lastrowid
    conn.close()
    return fight_id

def get_fight(fight_id: int):
    conn = get_connection()
    row = conn.execute(f"SELECT * FROM fights WHERE id = ? AND {NOT_DELETED}", (fight_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def list_fights_for_event(event_id: int):
    conn = get_connection()
    rows = conn.execute(f"SELECT * FROM fights WHERE event_id = ? AND {NOT_DELETED} ORDER BY fight_number ASC", (event_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_fight(fight_id: int, winner: str = None, plasada: float = None, pit_fee: float = None, notes: str = None) -> bool:
    conn = get_connection()
    cols = []
    params = []
    if winner is not None:
        cols.append("winner = ?")
        params.append(winner)
    if plasada is not None:
        cols.append("plasada_amount = ?")
        params.append(plasada)
    if pit_fee is not None:
        cols.append("pit_fee = ?")
        params.append(pit_fee)
    if notes is not None:
        cols.append("notes = ?")
        params.append(notes)
    if not cols:
        conn.close()
        return False
    params.append(fight_id)
    cur = conn.execute(f"UPDATE fights SET {', '.join(cols)} WHERE id = ? AND {NOT_DELETED}", params)
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated

def delete_fight(fight_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute(f"UPDATE fights SET deleted_at = datetime('now') WHERE id = ? AND {NOT_DELETED}", (fight_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted

# --- Event Revenue ---

def insert_event_revenue(event_id: int, date_str: str, source: str, amount: float, description: str = None, created_by: str = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO event_revenue (event_id, date, source, amount, description, created_by) VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, date_str, source, amount, description, created_by),
    )
    conn.commit()
    revenue_id = cur.lastrowid
    conn.close()
    return revenue_id

def list_event_revenue(event_id: int):
    conn = get_connection()
    rows = conn.execute(f"SELECT * FROM event_revenue WHERE event_id = ? AND {NOT_DELETED} ORDER BY date DESC, id DESC", (event_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_event_summary(event_id: int) -> dict:
    """Total revenue and fight count for an event."""
    conn = get_connection()
    revenue_row = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) AS total FROM event_revenue WHERE event_id = ? AND {NOT_DELETED}",
        (event_id,)
    ).fetchone()
    fight_row = conn.execute(
        f"SELECT COUNT(*) AS count FROM fights WHERE event_id = ? AND {NOT_DELETED}",
        (event_id,)
    ).fetchone()
    conn.close()
    return {
        "total_revenue": revenue_row["total"] or 0,
        "fight_count": fight_row["count"] or 0,
    }

# --- Expenses ---

def insert_expense(date_str: str, amount: float, description: str = None, category: str = None, note: str = None, created_by: str = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO expenses (date, amount, description, category, note, created_by) VALUES (?, ?, ?, ?, ?, ?)",
        (date_str, amount, description, category, note, created_by),
    )
    conn.commit()
    expense_id = cur.lastrowid
    conn.close()
    return expense_id

def list_expenses(date_from=None, date_to=None, category=None, limit=None, offset=0):
    conn = get_connection()
    where = [NOT_DELETED]
    params = []
    if date_from:
        where.append("date >= ?")
        params.append(date_from)
    if date_to:
        where.append("date <= ?")
        params.append(date_to)
    if category:
        where.append("category = ?")
        params.append(category)
    from_where = f"FROM expenses WHERE {' AND '.join(where)}"
    
    if limit is not None:
        result = _paginate(conn, "*", from_where, params, "date DESC, id DESC", limit, offset)
        conn.close()
        return result
    rows = conn.execute(f"SELECT * {from_where} ORDER BY date DESC, id DESC", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_expense(expense_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute(f"UPDATE expenses SET deleted_at = datetime('now') WHERE id = ? AND {NOT_DELETED}", (expense_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted

# --- Cash Remittances ---

def insert_cash_remittance(date_str: str, amount: float, note: str = None, created_by: str = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO cash_remittances (date, amount, note, created_by) VALUES (?, ?, ?, ?)",
        (date_str, amount, note, created_by),
    )
    conn.commit()
    remittance_id = cur.lastrowid
    conn.commit()
    conn.close()
    return remittance_id

def list_cash_remittances(date_from=None, date_to=None, limit=None, offset=0):
    conn = get_connection()
    where = [NOT_DELETED]
    params = []
    if date_from:
        where.append("date >= ?")
        params.append(date_from)
    if date_to:
        where.append("date <= ?")
        params.append(date_to)
    from_where = f"FROM cash_remittances WHERE {' AND '.join(where)}"
    
    if limit is not None:
        result = _paginate(conn, "*", from_where, params, "date DESC, id DESC", limit, offset)
        conn.close()
        return result
    rows = conn.execute(f"SELECT * {from_where} ORDER BY date DESC, id DESC", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_cash_remittance(remittance_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute(f"UPDATE cash_remittances SET deleted_at = datetime('now') WHERE id = ? AND {NOT_DELETED}", (remittance_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted

# --- Settings ---

def get_setting(key: str, default=None):
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value):
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()

# --- Personnel ---

def insert_personnel(name: str, position: str, contact: str = None, date_hired: str = None, status: str = "Active", rate: float = None, created_by: str = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO personnel (name, position, contact_number, date_hired, status, rate_per_shift, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, position, contact, date_hired, status, rate, created_by),
    )
    conn.commit()
    personnel_id = cur.lastrowid
    conn.close()
    return personnel_id

def list_personnel(status=None, position=None, limit=None, offset=0):
    conn = get_connection()
    where = [NOT_DELETED]
    params = []
    if status:
        where.append("status = ?")
        params.append(status)
    if position:
        where.append("position = ?")
        params.append(position)
    from_where = f"FROM personnel WHERE {' AND '.join(where)}"
    
    if limit is not None:
        result = _paginate(conn, "*", from_where, params, "name COLLATE NOCASE", limit, offset)
        conn.close()
        return result
    rows = conn.execute(f"SELECT * {from_where} ORDER BY name COLLATE NOCASE", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_personnel(personnel_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute(f"UPDATE personnel SET deleted_at = datetime('now') WHERE id = ? AND {NOT_DELETED}", (personnel_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted

# --- Shifts ---

def list_shift_types():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM shift_types ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_shift_roster(date_str: str):
    conn = get_connection()
    rows = conn.execute(
        f"SELECT sr.*, p.name AS personnel_name, st.name AS shift_name "
        f"FROM shift_roster sr "
        f"JOIN personnel p ON p.id = sr.personnel_id "
        f"JOIN shift_types st ON st.id = sr.shift_type_id "
        f"WHERE sr.date = ? AND sr.{NOT_DELETED} "
        f"ORDER BY sr.shift_type_id, p.name COLLATE NOCASE",
        (date_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_shift_roster_entry(date_str: str, shift_type_id: int, personnel_id: int, status: str, created_by: str) -> int:
    conn = get_connection()
    # Check for duplicate
    already = conn.execute(
        f"SELECT 1 FROM shift_roster WHERE date = ? AND shift_type_id = ? AND personnel_id = ? AND {NOT_DELETED}",
        (date_str, shift_type_id, personnel_id),
    ).fetchone()
    if already:
        conn.close()
        raise ValueError("Already assigned to this shift on this date.")
    
    cur = conn.execute(
        "INSERT INTO shift_roster (date, shift_type_id, personnel_id, status, created_by) VALUES (?, ?, ?, ?, ?)",
        (date_str, shift_type_id, personnel_id, status, created_by),
    )
    conn.commit()
    roster_id = cur.lastrowid
    conn.close()
    return roster_id

def update_shift_roster_status(roster_id: int, status: str, updated_by: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE shift_roster SET status = ?, updated_at = datetime('now'), updated_by = ? WHERE id = ?",
        (status, updated_by, roster_id),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated

def remove_shift_roster_entry(roster_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute(f"UPDATE shift_roster SET deleted_at = datetime('now') WHERE id = ? AND {NOT_DELETED}", (roster_id,))
    conn.commit()
    removed = cur.rowcount > 0
    conn.close()
    return removed

# --- Penalties & Payroll ---

def get_penalty_defaults() -> dict:
    return {
        "late_amount": float(get_setting("personnel_late_penalty_default", 200)),
        "absence_amount": float(get_setting("personnel_absence_penalty_default", 500)),
    }

def set_penalty_defaults(late_amount: float, absence_amount: float):
    set_setting("personnel_late_penalty_default", late_amount)
    set_setting("personnel_absence_penalty_default", absence_amount)

def insert_personnel_penalty(personnel_id: int, date_str: str, type_: str, amount: float, description: str = None, category: str = "penalty", created_by: str = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO personnel_penalties (personnel_id, date, type, category, description, amount, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (personnel_id, date_str, type_, category, description, amount, created_by),
    )
    conn.commit()
    penalty_id = cur.lastrowid
    conn.close()
    return penalty_id

def list_personnel_penalties(personnel_id: int, date_from=None, date_to=None, limit=None, offset=0):
    conn = get_connection()
    where = [NOT_DELETED, "personnel_id = ?"]
    params = [personnel_id]
    if date_from:
        where.append("date >= ?")
        params.append(date_from)
    if date_to:
        where.append("date <= ?")
        params.append(date_to)
    from_where = f"FROM personnel_penalties WHERE {' AND '.join(where)}"
    
    if limit is not None:
        result = _paginate(conn, "*", from_where, params, "date DESC, id DESC", limit, offset)
        conn.close()
        return result
    rows = conn.execute(f"SELECT * {from_where} ORDER BY date DESC, id DESC", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def compute_personnel_salary(personnel_id: int, date_from: str, date_to: str):
    """Calculate salary for a period: (shifts attended * rate) - penalties - deductions."""
    conn = get_connection()
    person = conn.execute(f"SELECT * FROM personnel WHERE id = ? AND {NOT_DELETED}", (personnel_id,)).fetchone()
    if not person:
        conn.close()
        return None
    
    rate = person["rate_per_shift"]
    shifts_attended = conn.execute(
        f"SELECT COUNT(*) FROM shift_roster WHERE personnel_id = ? AND date >= ? AND date <= ? AND status IN ('Present', 'Late') AND {NOT_DELETED}",
        (personnel_id, date_from, date_to),
    ).fetchone()[0]
    
    penalties = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM personnel_penalties WHERE personnel_id = ? AND date >= ? AND date <= ? AND category = 'penalty' AND {NOT_DELETED}",
        (personnel_id, date_from, date_to),
    ).fetchone()[0]
    
    deductions = conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM personnel_penalties WHERE personnel_id = ? AND date >= ? AND date <= ? AND category = 'deduction' AND {NOT_DELETED}",
        (personnel_id, date_from, date_to),
    ).fetchone()[0]
    
    conn.close()
    
    if rate is None:
        return {
            "rate": None, "shifts_attended": shifts_attended, "gross": None,
            "penalties": round(penalties, 2), "deductions": round(deductions, 2), "net": None,
        }
    
    gross = round(shifts_attended * rate, 2)
    net = round(gross - penalties - deductions, 2)
    return {
        "rate": rate, "shifts_attended": shifts_attended, "gross": gross,
        "penalties": round(penalties, 2), "deductions": round(deductions, 2), "net": net,
    }
