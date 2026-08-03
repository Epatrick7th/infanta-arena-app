#!/usr/bin/env python3
"""
Test the analytics page by fetching it and checking for issues
"""
import sys
sys.path.insert(0, 'C:\\Users\\Patrick\\Downloads\\sabong-arena-app')

import db
import app as app_module
from datetime import date

db.init_db()

# Create test client
client = app_module.app.test_client()

# First login to set session
print("1. Attempting login...")
response = client.post('/login', data={'username': 'boss_infanta', 'password': 'boss123'}, follow_redirects=True)
print(f"   Login response: {response.status_code}")

# Now try to access analytics
print("\n2. Accessing /analytics...")
response = client.get('/analytics')
print(f"   Response code: {response.status_code}")

if response.status_code == 200:
    html = response.get_data(as_text=True)
    
    # Check for key elements
    checks = [
        ('Daily tab', 'id="daily-tab"' in html),
        ('Weekly tab', 'id="weekly-tab"' in html),
        ('Monthly tab', 'id="monthly-tab"' in html),
        ('Trends tab', 'id="trends-tab"' in html),
        ('Tab buttons', 'tab-btn' in html),
        ('showTab function', 'function showTab' in html),
        ('Data attributes', 'data-tab=' in html),
    ]
    
    print("\n3. Checking page content:")
    for check_name, result in checks:
        status = "OK" if result else "MISSING"
        print(f"   {check_name}: {status}")
    
    # Show first few lines
    print("\n4. HTML head section:")
    lines = html.split('\n')[:20]
    for line in lines:
        if line.strip():
            print(f"   {line[:100]}")
else:
    print(f"   ERROR: Got status {response.status_code}")
    print(f"   Response:\n{response.get_data(as_text=True)[:500]}")
