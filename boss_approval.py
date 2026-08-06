# Boss approval functions
from db import get_connection, NOT_DELETED, _today
from datetime import datetime

def get_pending_approvals(boss_id: int):
    """Get all pending items waiting for boss approval."""
    conn = get_connection()
    
    try:
        pending_events = conn.execute(
            f"SELECT id, name, date, created_by, created_at FROM events WHERE boss_id = ? AND approval_status = 'pending' AND {NOT_DELETED} ORDER BY created_at DESC",
            (boss_id,)
        ).fetchall()
        
        pending_revenue = conn.execute(
            f"SELECT id, source, amount, description, event_id, created_by, created_at FROM event_revenue WHERE boss_id = ? AND approval_status = 'pending' AND {NOT_DELETED} ORDER BY created_at DESC",
            (boss_id,)
        ).fetchall()
        
        pending_expenses = conn.execute(
            f"SELECT id, amount, description, category, created_by, created_at FROM expenses WHERE boss_id = ? AND approval_status = 'pending' AND {NOT_DELETED} ORDER BY created_at DESC",
            (boss_id,)
        ).fetchall()
        
        pending_remittances = conn.execute(
            f"SELECT id, amount, note, created_by, created_at FROM cash_remittances WHERE boss_id = ? AND approval_status = 'pending' AND {NOT_DELETED} ORDER BY created_at DESC",
            (boss_id,)
        ).fetchall()
        
        return {
            'events': [dict(r) for r in pending_events],
            'revenue': [dict(r) for r in pending_revenue],
            'expenses': [dict(r) for r in pending_expenses],
            'remittances': [dict(r) for r in pending_remittances],
            'total_pending': len(pending_events) + len(pending_revenue) + len(pending_expenses) + len(pending_remittances)
        }
    finally:
        conn.close()

def approve_event(event_id: int, boss_id: int, approved_by: str):
    """Boss approves an event."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE events SET approval_status = 'approved', approved_by = ?, approved_at = datetime('now') WHERE id = ? AND boss_id = ?",
            (approved_by, event_id, boss_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def approve_revenue(revenue_id: int, boss_id: int, approved_by: str):
    """Boss approves revenue entry."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE event_revenue SET approval_status = 'approved', approved_by = ?, approved_at = datetime('now') WHERE id = ? AND boss_id = ?",
            (approved_by, revenue_id, boss_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def approve_expense(expense_id: int, boss_id: int, approved_by: str):
    """Boss approves expense."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE expenses SET approval_status = 'approved', approved_by = ?, approved_at = datetime('now') WHERE id = ? AND boss_id = ?",
            (approved_by, expense_id, boss_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def approve_remittance(remittance_id: int, boss_id: int, approved_by: str):
    """Boss approves remittance."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE cash_remittances SET approval_status = 'approved', approved_by = ?, approved_at = datetime('now') WHERE id = ? AND boss_id = ?",
            (approved_by, remittance_id, boss_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def reject_event(event_id: int, boss_id: int, approved_by: str):
    """Boss rejects an event."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE events SET approval_status = 'rejected', approved_by = ?, approved_at = datetime('now') WHERE id = ? AND boss_id = ?",
            (approved_by, event_id, boss_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
