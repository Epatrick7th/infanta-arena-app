# Boss-specific database functions
from db import get_connection, NOT_DELETED, _today
from datetime import datetime, timedelta

def get_boss_dashboard_summary(boss_id: int, date: str = None):
    """Get executive dashboard KPIs for a boss."""
    if date is None:
        date = _today()
    
    conn = get_connection()
    
    try:
        revenue = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM event_revenue WHERE boss_id = ? AND date = ? AND {NOT_DELETED}",
            (boss_id, date)
        ).fetchone()[0]
        
        sources = conn.execute(
            f"SELECT source, COALESCE(SUM(amount), 0) as total FROM event_revenue WHERE boss_id = ? AND date = ? AND {NOT_DELETED} GROUP BY source",
            (boss_id, date)
        ).fetchall()
        revenue_by_source = {s["source"]: s["total"] for s in sources}
        
        expenses = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE boss_id = ? AND date = ? AND {NOT_DELETED}",
            (boss_id, date)
        ).fetchone()[0]
        
        events_today = conn.execute(
            f"SELECT COUNT(*) FROM events WHERE boss_id = ? AND date = ? AND {NOT_DELETED}",
            (boss_id, date)
        ).fetchone()[0]
        
        fights_today = conn.execute(
            f"SELECT COUNT(*) FROM fights WHERE boss_id = ? AND date = ? AND {NOT_DELETED}",
            (boss_id, date)
        ).fetchone()[0]
        
        net_profit = round(revenue - expenses, 2)
        
        return {
            'cash_in_hand': round(revenue - expenses, 2),
            'today_revenue': round(revenue, 2),
            'today_by_source': {k: round(v, 2) for k, v in revenue_by_source.items()},
            'pending_remittance': 0,
            'payroll_due_week': 0,
            'total_expenses_today': round(expenses, 2),
            'net_profit_today': net_profit,
            'events_today': events_today,
            'fights_today': fights_today
        }
    finally:
        conn.close()

def get_financial_summary(boss_id: int, period: str = 'day', date: str = None):
    """Get financial summary for boss."""
    if date is None:
        date = _today()
    
    conn = get_connection()
    
    try:
        revenue = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM event_revenue WHERE boss_id = ? AND date = ? AND {NOT_DELETED}",
            (boss_id, date)
        ).fetchone()[0]
        
        expenses = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE boss_id = ? AND date = ? AND {NOT_DELETED}",
            (boss_id, date)
        ).fetchone()[0]
        
        net_profit = round(revenue - expenses, 2)
        
        return {
            'total_revenue': round(revenue, 2),
            'total_expenses': round(expenses, 2),
            'net_profit': net_profit,
            'revenue_by_source': {},
            'remittances': []
        }
    finally:
        conn.close()
