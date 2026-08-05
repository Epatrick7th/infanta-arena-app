#!/usr/bin/env python3
"""
Comprehensive app functionality test
"""
import os
import requests
import json
import time

BASE_URL = "http://127.0.0.1:5001"
session = requests.Session()

print("=" * 60)
print("INFANTA ARENA APP - COMPREHENSIVE FUNCTIONALITY TEST")
print("=" * 60)

# Test 1: Login
print("\n[TEST 1] Login")
try:
    resp = session.post(f"{BASE_URL}/login", data={
        'username': 'patrick',
        'password': os.environ.get('TEST_PASSWORD', '')
    }, allow_redirects=True)
    if "Welcome" in resp.text or "dashboard" in resp.url:
        print("✓ Login successful")
    else:
        print("✗ Login failed - unexpected response")
        print(f"  Status: {resp.status_code}, URL: {resp.url}")
except Exception as e:
    print(f"✗ Login error: {e}")

# Test 2: Dashboard
print("\n[TEST 2] Dashboard Page")
try:
    resp = session.get(f"{BASE_URL}/dashboard")
    if resp.status_code == 200 and ("Events" in resp.text or "dashboard" in resp.text):
        print("✓ Dashboard loads")
    else:
        print(f"✗ Dashboard failed - {resp.status_code}")
except Exception as e:
    print(f"✗ Dashboard error: {e}")

# Test 3: Events Page
print("\n[TEST 3] Events Page")
try:
    resp = session.get(f"{BASE_URL}/events")
    if resp.status_code == 200 and "Events" in resp.text:
        print("✓ Events page loads")
    else:
        print(f"✗ Events page failed - {resp.status_code}")
except Exception as e:
    print(f"✗ Events error: {e}")

# Test 4: New Event Form (GET)
print("\n[TEST 4] New Event Form")
try:
    resp = session.get(f"{BASE_URL}/events/new")
    if resp.status_code == 200 and "event" in resp.text.lower():
        print("✓ New event form loads")
    else:
        print(f"✗ New event form failed - {resp.status_code}")
except Exception as e:
    print(f"✗ New event form error: {e}")

# Test 5: Create Event (POST)
print("\n[TEST 5] Create Event")
try:
    resp = session.post(f"{BASE_URL}/events/new", data={
        'name': 'Test Event 1',
        'event_date': '2026-08-05',
        'location': 'Main Arena',
        'notes': 'Test event'
    }, allow_redirects=True)
    if resp.status_code == 200:
        print("✓ Event created successfully")
    else:
        print(f"✗ Event creation failed - {resp.status_code}")
except Exception as e:
    print(f"✗ Event creation error: {e}")

# Test 6: Remittances Page
print("\n[TEST 6] Remittances Page")
try:
    resp = session.get(f"{BASE_URL}/remittances")
    if resp.status_code == 200 and "Remittance" in resp.text:
        print("✓ Remittances page loads")
    else:
        print(f"✗ Remittances page failed - {resp.status_code}")
except Exception as e:
    print(f"✗ Remittances error: {e}")

# Test 7: New Remittance Form
print("\n[TEST 7] New Remittance Form")
try:
    resp = session.get(f"{BASE_URL}/remittances/new")
    if resp.status_code == 200 and "remittance" in resp.text.lower():
        print("✓ New remittance form loads")
    else:
        print(f"✗ New remittance form failed - {resp.status_code}")
except Exception as e:
    print(f"✗ New remittance form error: {e}")

# Test 8: Personnel Page
print("\n[TEST 8] Personnel Page")
try:
    resp = session.get(f"{BASE_URL}/personnel")
    if resp.status_code == 200 and "Personnel" in resp.text:
        print("✓ Personnel page loads")
    else:
        print(f"✗ Personnel page failed - {resp.status_code}")
except Exception as e:
    print(f"✗ Personnel error: {e}")

# Test 9: New Personnel Form
print("\n[TEST 9] New Personnel Form")
try:
    resp = session.get(f"{BASE_URL}/personnel/new")
    if resp.status_code == 200:
        print("✓ New personnel form loads")
    else:
        print(f"✗ New personnel form failed - {resp.status_code}")
except Exception as e:
    print(f"✗ New personnel form error: {e}")

# Test 10: Admin/Users Page
print("\n[TEST 10] Admin Users Page")
try:
    resp = session.get(f"{BASE_URL}/users")
    if resp.status_code == 200:
        print("✓ Users admin page loads")
    else:
        print(f"✗ Users admin page failed - {resp.status_code}")
except Exception as e:
    print(f"✗ Users admin error: {e}")

# Test 11: Logout
print("\n[TEST 11] Logout")
try:
    resp = session.get(f"{BASE_URL}/logout", allow_redirects=True)
    if resp.status_code == 200 or "login" in resp.url.lower():
        print("✓ Logout successful")
    else:
        print(f"✗ Logout failed - {resp.status_code}")
except Exception as e:
    print(f"✗ Logout error: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
