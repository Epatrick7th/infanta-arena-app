# Live arena fight dashboard functions
from db import get_connection, NOT_DELETED, _today
from datetime import datetime

def get_live_fight(boss_id: int, event_id: int = None):
    """Get the currently live or next pending fight."""
    conn = get_connection()
    
    try:
        # First try to find a live fight
        query = f"""
            SELECT * FROM fights 
            WHERE boss_id = ? AND status = 'live' AND {NOT_DELETED}
        """
        params = [boss_id]
        
        if event_id:
            query += " AND event_id = ?"
            params.append(event_id)
        
        fight = conn.execute(query + " ORDER BY fight_number DESC LIMIT 1", params).fetchone()
        
        if fight:
            return _format_fight(conn, dict(fight))
        
        # If no live fight, get the next pending one
        query = f"""
            SELECT * FROM fights 
            WHERE boss_id = ? AND status = 'pending' AND {NOT_DELETED}
        """
        params = [boss_id]
        
        if event_id:
            query += " AND event_id = ?"
            params.append(event_id)
        
        fight = conn.execute(query + " ORDER BY fight_number ASC LIMIT 1", params).fetchone()
        return _format_fight(conn, dict(fight)) if fight else None
        
    finally:
        conn.close()

def get_fight_bets(fight_id: int, side: str = None):
    """Get all bets for a fight, optionally filtered by side (Meron/Wala)."""
    conn = get_connection()
    
    try:
        query = f"SELECT * FROM fight_bets WHERE fight_id = ? AND {NOT_DELETED}"
        params = [fight_id]
        
        if side:
            query += " AND side = ?"
            params.append(side)
        
        bets = conn.execute(query + " ORDER BY created_at DESC", params).fetchall()
        return [dict(b) for b in bets]
    finally:
        conn.close()

def get_fight_bets_summary(fight_id: int):
    """Get total bets for meron vs wala."""
    conn = get_connection()
    
    try:
        meron = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM fight_bets WHERE fight_id = ? AND side = 'Meron' AND {NOT_DELETED}",
            (fight_id,)
        ).fetchone()[0]
        
        wala = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) FROM fight_bets WHERE fight_id = ? AND side = 'Wala' AND {NOT_DELETED}",
            (fight_id,)
        ).fetchone()[0]
        
        total = meron + wala
        
        return {
            'meron_total': round(meron, 2),
            'wala_total': round(wala, 2),
            'total_bets': round(total, 2),
            'meron_pct': round((meron / total * 100) if total > 0 else 0, 1),
            'wala_pct': round((wala / total * 100) if total > 0 else 0, 1),
            'meron_count': conn.execute(
                f"SELECT COUNT(*) FROM fight_bets WHERE fight_id = ? AND side = 'Meron' AND {NOT_DELETED}",
                (fight_id,)
            ).fetchone()[0],
            'wala_count': conn.execute(
                f"SELECT COUNT(*) FROM fight_bets WHERE fight_id = ? AND side = 'Wala' AND {NOT_DELETED}",
                (fight_id,)
            ).fetchone()[0]
        }
    finally:
        conn.close()

def add_bet(fight_id: int, boss_id: int, side: str, amount: float, bettor_name: str = None, created_by: str = None):
    """Add a new bet to a fight."""
    conn = get_connection()
    
    try:
        conn.execute(
            """INSERT INTO fight_bets (fight_id, boss_id, side, amount, bettor_name, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (fight_id, boss_id, side, amount, bettor_name, created_by)
        )
        conn.commit()
        return True
    finally:
        conn.close()

def start_fight(fight_id: int):
    """Mark a fight as live."""
    conn = get_connection()
    
    try:
        conn.execute(
            "UPDATE fights SET status = 'live', started_at = datetime('now') WHERE id = ?",
            (fight_id,)
        )
        conn.commit()
        return True
    finally:
        conn.close()

def finish_fight(fight_id: int, winner: str):
    """Mark a fight as finished with a winner."""
    conn = get_connection()
    
    try:
        conn.execute(
            """UPDATE fights SET status = 'finished', winner = ?, finished_at = datetime('now')
               WHERE id = ?""",
            (winner, fight_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()

def _format_fight(conn, fight_dict):
    """Format a fight with bet summary."""
    if not fight_dict:
        return None
    
    fight_id = fight_dict.get('id')
    bets_summary = get_fight_bets_summary(fight_id) if fight_id else {
        'meron_total': 0, 'wala_total': 0, 'total_bets': 0,
        'meron_pct': 0, 'wala_pct': 0, 'meron_count': 0, 'wala_count': 0
    }
    
    return {**fight_dict, **bets_summary}
