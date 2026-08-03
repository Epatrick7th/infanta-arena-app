# Analytics functions
from db import get_connection, NOT_DELETED, _today
from datetime import datetime, timedelta

def get_daily_pl(boss_id: int, date: str = None):
    """Get daily profit & loss for a specific date."""
    if date is None:
        date = _today()
    
    conn = get_connection()
    try:
        # Revenue
        revenue = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) as total FROM event_revenue WHERE boss_id = ? AND date = ? AND {NOT_DELETED}",
            (boss_id, date)
        ).fetchone()['total']
        
        # Expenses
        expenses = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE boss_id = ? AND date = ? AND {NOT_DELETED}",
            (boss_id, date)
        ).fetchone()['total']
        
        net = revenue - expenses
        margin = (net / revenue * 100) if revenue > 0 else 0
        
        return {
            'date': date,
            'revenue': round(revenue, 2),
            'expenses': round(expenses, 2),
            'net_profit': round(net, 2),
            'profit_margin': round(margin, 1)
        }
    finally:
        conn.close()

def get_weekly_pl(boss_id: int, date: str = None):
    """Get weekly P&L."""
    if date is None:
        date = _today()
    
    current_date = datetime.fromisoformat(date)
    week_start = current_date - timedelta(days=current_date.weekday())
    week_end = week_start + timedelta(days=6)
    
    start_str = week_start.date().isoformat()
    end_str = week_end.date().isoformat()
    
    conn = get_connection()
    try:
        revenue = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) as total FROM event_revenue WHERE boss_id = ? AND date >= ? AND date <= ? AND {NOT_DELETED}",
            (boss_id, start_str, end_str)
        ).fetchone()['total']
        
        expenses = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE boss_id = ? AND date >= ? AND date <= ? AND {NOT_DELETED}",
            (boss_id, start_str, end_str)
        ).fetchone()['total']
        
        net = revenue - expenses
        margin = (net / revenue * 100) if revenue > 0 else 0
        
        return {
            'period': f"{start_str} to {end_str}",
            'revenue': round(revenue, 2),
            'expenses': round(expenses, 2),
            'net_profit': round(net, 2),
            'profit_margin': round(margin, 1)
        }
    finally:
        conn.close()

def get_monthly_pl(boss_id: int, date: str = None):
    """Get monthly P&L."""
    if date is None:
        date = _today()
    
    current_date = datetime.fromisoformat(date)
    month_start = current_date.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    start_str = month_start.date().isoformat()
    end_str = month_end.date().isoformat()
    
    conn = get_connection()
    try:
        revenue = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) as total FROM event_revenue WHERE boss_id = ? AND date >= ? AND date <= ? AND {NOT_DELETED}",
            (boss_id, start_str, end_str)
        ).fetchone()['total']
        
        expenses = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE boss_id = ? AND date >= ? AND date <= ? AND {NOT_DELETED}",
            (boss_id, start_str, end_str)
        ).fetchone()['total']
        
        net = revenue - expenses
        margin = (net / revenue * 100) if revenue > 0 else 0
        
        return {
            'period': month_start.strftime('%B %Y'),
            'revenue': round(revenue, 2),
            'expenses': round(expenses, 2),
            'net_profit': round(net, 2),
            'profit_margin': round(margin, 1)
        }
    finally:
        conn.close()

def get_daily_trend(boss_id: int, days: int = 7, end_date: str = None):
    """Get revenue trend for last N days."""
    if end_date is None:
        end_date = _today()
    
    end_dt = datetime.fromisoformat(end_date)
    start_dt = end_dt - timedelta(days=days-1)
    
    conn = get_connection()
    try:
        # Get daily data
        rows = conn.execute(
            f"""SELECT date, 
                       COALESCE(SUM(CASE WHEN type='revenue' THEN amount ELSE 0 END), 0) as revenue,
                       COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) as expenses
                FROM (
                    SELECT date, 'revenue' as type, amount FROM event_revenue WHERE boss_id = ? AND {NOT_DELETED}
                    UNION ALL
                    SELECT date, 'expense' as type, amount FROM expenses WHERE boss_id = ? AND {NOT_DELETED}
                ) 
                WHERE date >= ? AND date <= ?
                GROUP BY date
                ORDER BY date DESC""",
            (boss_id, boss_id, start_dt.date().isoformat(), end_dt.date().isoformat())
        ).fetchall()
        
        trend = []
        for row in rows:
            date = row['date']
            revenue = row['revenue']
            expenses = row['expenses']
            net = revenue - expenses
            trend.append({
                'date': date,
                'revenue': round(revenue, 2),
                'expenses': round(expenses, 2),
                'net': round(net, 2)
            })
        
        return list(reversed(trend))  # Reverse to chronological order
    finally:
        conn.close()

def get_expense_breakdown(boss_id: int, date: str = None):
    """Get expenses by category."""
    if date is None:
        date = _today()
    
    current_date = datetime.fromisoformat(date)
    month_start = current_date.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    start_str = month_start.date().isoformat()
    end_str = month_end.date().isoformat()
    
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT category, COALESCE(SUM(amount), 0) as total FROM expenses WHERE boss_id = ? AND date >= ? AND date <= ? AND {NOT_DELETED} GROUP BY category ORDER BY total DESC",
            (boss_id, start_str, end_str)
        ).fetchall()
        
        return [{'category': r['category'] or 'Other', 'amount': round(r['total'], 2)} for r in rows]
    finally:
        conn.close()

def get_revenue_breakdown(boss_id: int, date: str = None):
    """Get revenue by source."""
    if date is None:
        date = _today()
    
    current_date = datetime.fromisoformat(date)
    month_start = current_date.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    start_str = month_start.date().isoformat()
    end_str = month_end.date().isoformat()
    
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT source, COALESCE(SUM(amount), 0) as total FROM event_revenue WHERE boss_id = ? AND date >= ? AND date <= ? AND {NOT_DELETED} GROUP BY source ORDER BY total DESC",
            (boss_id, start_str, end_str)
        ).fetchall()
        
        return [{'source': r['source'] or 'Other', 'amount': round(r['total'], 2)} for r in rows]
    finally:
        conn.close()
