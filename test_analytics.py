#!/usr/bin/env python3
"""Test analytics dashboard functions."""
import sys
sys.path.insert(0, 'C:\\Users\\Patrick\\Downloads\\sabong-arena-app')

import db
import analytics
from datetime import datetime, timedelta

# Initialize DB
db.init_db()

# Create sample data for boss_infanta (id=1)
print("Creating sample data for testing...")
conn = db.get_connection()

# Clear old test data
conn.execute("DELETE FROM event_revenue WHERE boss_id = 1")
conn.execute("DELETE FROM expenses WHERE boss_id = 1")
conn.execute("DELETE FROM events WHERE boss_id = 1")

# Insert sample revenue data for past 7 days
today = datetime.now()
for i in range(7):
    date = (today - timedelta(days=i)).date().isoformat()
    
    # Create event first
    conn.execute(
        """INSERT INTO events (boss_id, arena_id, date, name, event_type, created_at) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (1, 'infanta', date, f'Event {date}', 'derby', datetime.now().isoformat())
    )
    event = conn.execute("SELECT id FROM events WHERE boss_id = ? ORDER BY id DESC LIMIT 1", (1,)).fetchone()
    event_id = event['id']
    
    # Plasada (house betting)
    conn.execute(
        """INSERT INTO event_revenue (boss_id, event_id, source, amount, date, created_at) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (1, event_id, 'plasada', 15000 + i*1000, date, datetime.now().isoformat())
    )
    
    # Gate revenue
    conn.execute(
        """INSERT INTO event_revenue (boss_id, event_id, source, amount, date, created_at) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (1, event_id, 'gate', 8000 + i*500, date, datetime.now().isoformat())
    )
    
    # Concessions
    conn.execute(
        """INSERT INTO event_revenue (boss_id, event_id, source, amount, date, created_at) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (1, event_id, 'concession', 3000, date, datetime.now().isoformat())
    )
    
    # Expenses
    conn.execute(
        """INSERT INTO expenses (boss_id, category, amount, date, created_at) 
           VALUES (?, ?, ?, ?, ?)""",
        (1, 'payroll', 5000, date, datetime.now().isoformat())
    )
    
    conn.execute(
        """INSERT INTO expenses (boss_id, category, amount, date, created_at) 
           VALUES (?, ?, ?, ?, ?)""",
        (1, 'utilities', 800, date, datetime.now().isoformat())
    )
    
    conn.execute(
        """INSERT INTO expenses (boss_id, category, amount, date, created_at) 
           VALUES (?, ?, ?, ?, ?)""",
        (1, 'supplies', 300, date, datetime.now().isoformat())
    )

conn.commit()
conn.close()

print("\n=== TESTING ANALYTICS FUNCTIONS ===\n")

# Test daily P&L
print("1. Daily P&L")
daily_pl = analytics.get_daily_pl(1)
print(f"   Date: {daily_pl['date']}")
print(f"   Revenue: {daily_pl['revenue']:,.2f}")
print(f"   Expenses: {daily_pl['expenses']:,.2f}")
print(f"   Net Profit: {daily_pl['net_profit']:,.2f}")
print(f"   Profit Margin: {daily_pl['profit_margin']}%")

# Test weekly P&L
print("\n2. Weekly P&L")
weekly_pl = analytics.get_weekly_pl(1)
print(f"   Period: {weekly_pl['period']}")
print(f"   Revenue: {weekly_pl['revenue']:,.2f}")
print(f"   Expenses: {weekly_pl['expenses']:,.2f}")
print(f"   Net Profit: {weekly_pl['net_profit']:,.2f}")
print(f"   Profit Margin: {weekly_pl['profit_margin']}%")

# Test monthly P&L
print("\n3. Monthly P&L")
monthly_pl = analytics.get_monthly_pl(1)
print(f"   Period: {monthly_pl['period']}")
print(f"   Revenue: {monthly_pl['revenue']:,.2f}")
print(f"   Expenses: {monthly_pl['expenses']:,.2f}")
print(f"   Net Profit: {monthly_pl['net_profit']:,.2f}")
print(f"   Profit Margin: {monthly_pl['profit_margin']}%")

# Test daily trend
print("\n4. 7-Day Trend")
trend = analytics.get_daily_trend(1, 7)
for day in trend:
    print(f"   {day['date']}: Rev {day['revenue']:,.0f} | Exp {day['expenses']:,.0f} | Net {day['net']:,.0f}")

# Test revenue breakdown
print("\n5. Revenue by Source (This Month)")
rev_breakdown = analytics.get_revenue_breakdown(1)
for item in rev_breakdown:
    print(f"   {item['source'].capitalize()}: {item['amount']:,.2f}")

# Test expense breakdown
print("\n6. Expenses by Category (This Month)")
exp_breakdown = analytics.get_expense_breakdown(1)
for item in exp_breakdown:
    print(f"   {item['category'].capitalize()}: {item['amount']:,.2f}")

print("\nAll analytics functions working!")
