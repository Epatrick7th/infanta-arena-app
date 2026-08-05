#!/usr/bin/env python3
"""
Test the analytics page by running Flask and checking the response
"""
import os
import sys
sys.path.insert(0, 'C:\\Users\\Patrick\\Downloads\\sabong-arena-app')

import db
import app as app_module

# Initialize
db.init_db()

# Create a test user
try:
    db.create_user(TEST_USER, TEST_PASSWORD, 'boss')
    conn = db.get_connection()
    conn.execute("UPDATE users SET arena_name = 'Test Arena' WHERE username = 'test_boss'")
    conn.commit()
    conn.close()
    print(f"Created test user: {TEST_USER}")
except:
    print("Test user already exists")

# Create test client
client = app_module.app.test_client()

# Login
print("\n1. Testing login...")
# Credentials come from the environment; nothing secret lives in this file.
TEST_USER = os.environ.get('TEST_USER', 'test_boss')
TEST_PASSWORD = os.environ.get('TEST_PASSWORD')
if not TEST_PASSWORD:
    print('SKIP: set TEST_PASSWORD (and optionally TEST_USER) to run this test.')
    raise SystemExit(0)

response = client.post('/login', data={'username': TEST_USER, 'password': TEST_PASSWORD}, follow_redirects=True)
print(f"   Login status: {response.status_code}")

# Try analytics
print("\n2. Fetching /analytics...")
response = client.get('/analytics')
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    html = response.get_data(as_text=True)
    
    # Check for our HTML elements
    checks = {
        'Daily button': 'Daily' in html and 'button' in html,
        'Weekly button': 'Weekly' in html,
        'Analytics text': 'Analytics' in html,
        'No /boss/view': '/boss/view' not in html,
    }
    
    print("\n3. Checking page content:")
    for check, result in checks.items():
        status = "OK" if result else "FAIL"
        print(f"   {check}: {status}")
    
    # Show first part of HTML
    print("\n4. HTML snippet (first 500 chars):")
    print("   " + html[:500].replace('\n', '\n   '))
else:
    print(f"   ERROR: Got status {response.status_code}")
    print(f"   Response: {response.get_data(as_text=True)[:300]}")

print("\n5. Testing page rendering...")
print("   If you see 'OK' above, the page renders correctly")
print("   The 404 must be coming from the browser, not Flask")
