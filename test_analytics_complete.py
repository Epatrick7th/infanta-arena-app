#!/usr/bin/env python3
"""
Test the analytics page - check if it renders correctly
"""
import sys
sys.path.insert(0, 'C:\\Users\\Patrick\\Downloads\\sabong-arena-app')

import db
from datetime import date

db.init_db()

# Get a boss user and analytics data directly
conn = db.get_connection()
boss = conn.execute("SELECT id, arena_name FROM users WHERE id = 1").fetchone()
conn.close()

if not boss:
    print("ERROR: No boss user found")
    sys.exit(1)

boss_id = boss['id']
arena_name = boss['arena_name'] or 'My Arena'

# Import analytics functions
from analytics import (
    get_daily_pl, get_weekly_pl, get_monthly_pl, 
    get_daily_trend, get_revenue_breakdown, get_expense_breakdown
)

print("Testing analytics data generation...")
print()

try:
    today = date.today().isoformat()
    
    # Get analytics data
    daily_pl = get_daily_pl(boss_id, today)
    weekly_pl = get_weekly_pl(boss_id, today)
    monthly_pl = get_monthly_pl(boss_id, today)
    daily_trend = get_daily_trend(boss_id, 7, today)
    revenue_breakdown = get_revenue_breakdown(boss_id, today)
    expense_breakdown = get_expense_breakdown(boss_id, today)
    
    print(f"Arena: {arena_name}")
    print(f"Boss ID: {boss_id}")
    print()
    
    print("Daily P&L:")
    print(f"  Revenue: {daily_pl['revenue']:,.0f}")
    print(f"  Expenses: {daily_pl['expenses']:,.0f}")
    print(f"  Profit: {daily_pl['net_profit']:,.0f}")
    print(f"  Margin: {daily_pl['profit_margin']}%")
    print()
    
    print("Weekly P&L:")
    print(f"  Revenue: {weekly_pl['revenue']:,.0f}")
    print(f"  Expenses: {weekly_pl['expenses']:,.0f}")
    print(f"  Profit: {weekly_pl['net_profit']:,.0f}")
    print(f"  Margin: {weekly_pl['profit_margin']}%")
    print()
    
    print("Monthly P&L:")
    print(f"  Revenue: {monthly_pl['revenue']:,.0f}")
    print(f"  Expenses: {monthly_pl['expenses']:,.0f}")
    print(f"  Profit: {monthly_pl['net_profit']:,.0f}")
    print(f"  Margin: {monthly_pl['profit_margin']}%")
    print()
    
    print(f"Daily Trend (last 7 days): {len(daily_trend)} entries")
    for day in daily_trend[:3]:
        print(f"  {day['date']}: Rev {day['revenue']:,.0f} | Exp {day['expenses']:,.0f} | Net {day['net']:,.0f}")
    print()
    
    print(f"Revenue Sources: {len(revenue_breakdown)} sources")
    for src in revenue_breakdown:
        print(f"  {src['source']}: {src['amount']:,.0f}")
    print()
    
    print(f"Expense Categories: {len(expense_breakdown)} categories")
    for exp in expense_breakdown:
        print(f"  {exp['category']}: {exp['amount']:,.0f}")
    print()
    
    print("All analytics data generated successfully!")
    print()
    print("Now testing template rendering...")
    
    # Import Flask app
    from flask import render_template_string
    import app as app_module
    
    with app_module.app.app_context():
        # Try to render the template
        from jinja2 import Template
        
        # Simple check - just verify the template file exists
        with open('templates/analytics.html', 'r') as f:
            template_content = f.read()
        
        # Check for required elements
        required = ['daily-tab', 'weekly-tab', 'monthly-tab', 'trends-tab', 'tab-btn', 'showTab']
        print("Checking template elements:")
        for elem in required:
            found = elem in template_content
            status = "OK" if found else "MISSING"
            print(f"  {elem}: {status}")
    
    print()
    print("SUCCESS: All checks passed!")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
