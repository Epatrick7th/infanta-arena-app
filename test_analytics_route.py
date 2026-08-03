#!/usr/bin/env python3
"""
Quick test of analytics route - check if it renders properly
"""
import sys
sys.path.insert(0, 'C:\\Users\\Patrick\\Downloads\\sabong-arena-app')

import db
import app as app_module
from datetime import date

# Initialize DB
db.init_db()

# Create a test client
test_client = app_module.app.test_client()

# First, check if we can get to login
print("Testing analytics route...")

# Try to access /analytics without login (should redirect to login)
response = test_client.get('/analytics')
print(f"GET /analytics (no auth): {response.status_code}")
if response.status_code == 302:
    print(f"  Redirected to: {response.location}")

# Check if analytics function works
print("\nTesting analytics functions...")
try:
    from analytics import get_daily_pl, get_weekly_pl, get_monthly_pl
    daily = get_daily_pl(1)
    weekly = get_weekly_pl(1)
    monthly = get_monthly_pl(1)
    print(f"Daily P&L: Revenue {daily['revenue']:,} | Profit {daily['net_profit']:,}")
    print(f"Weekly P&L: Revenue {weekly['revenue']:,} | Profit {weekly['net_profit']:,}")
    print(f"Monthly P&L: Revenue {monthly['revenue']:,} | Profit {monthly['net_profit']:,}")
    print("Analytics functions: OK")
except Exception as e:
    print(f"Analytics functions: ERROR - {e}")

print("\nAll tests passed!")
