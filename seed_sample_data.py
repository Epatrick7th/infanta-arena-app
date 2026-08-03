#!/usr/bin/env python3
"""
Seed 1 month (August 2026) of realistic cockfighting arena operations data.
Single Infanta Arena with equal partnership split 6 ways.

Data Pattern:
- Weekdays (Mon-Fri): 8-12 fights, ₱40-55k revenue, ₱13-15k expenses
- Weekends (Sat-Sun): 15-20 fights, ₱65-85k revenue, ₱18-22k expenses
- 1 Special tournament mid-month: ₱140k revenue, ₱28k expenses
"""

import sys
sys.path.insert(0, 'C:\\Users\\Patrick\\Downloads\\sabong-arena-app')

import db
from datetime import datetime, timedelta
import random

# Initialize DB
db.init_db()

print("=" * 70)
print("SEEDING 1 MONTH OF REALISTIC COCKFIGHTING ARENA DATA")
print("=" * 70)

# August 2026 dates
start_date = datetime(2026, 8, 1)
end_date = datetime(2026, 8, 31)

# All 6 boss IDs (equal partners)
BOSS_IDS = [1, 2, 3, 4, 5, 6]
BOSS_NAMES = ['Infanta', 'Royal', 'Victory', 'Phoenix', 'Eagle', 'Tiger']

conn = db.get_connection()

# Clear old data
print("\nClearing old sample data...")
conn.execute("DELETE FROM event_revenue WHERE boss_id IN (1,2,3,4,5,6)")
conn.execute("DELETE FROM expenses WHERE boss_id IN (1,2,3,4,5,6)")
conn.execute("DELETE FROM cash_remittances WHERE boss_id IN (1,2,3,4,5,6)")
conn.execute("DELETE FROM fights WHERE boss_id IN (1,2,3,4,5,6)")
conn.execute("DELETE FROM events WHERE boss_id IN (1,2,3,4,5,6)")
conn.commit()

print("[OK] Old data cleared\n")

# Track stats
stats = {
    'events': 0,
    'fights': 0,
    'revenue_entries': 0,
    'expense_entries': 0,
    'remittances': 0,
    'total_revenue': 0,
    'total_expenses': 0,
}

# Generate 30 days of operations
current_date = start_date
day_count = 0

while current_date <= end_date:
    day_count += 1
    date_str = current_date.date().isoformat()
    day_name = current_date.strftime('%A')
    is_weekend = current_date.weekday() >= 5  # Saturday=5, Sunday=6
    
    # Determine if special tournament day (around mid-month)
    is_tournament = current_date.day == 15
    
    # ===== DETERMINE DAILY METRICS =====
    if is_tournament:
        # Special tournament day
        num_fights = random.randint(25, 30)
        plasada = random.randint(130000, 150000)
        gate = random.randint(5000, 10000)
        concession = random.randint(3000, 5000)
        payroll = random.randint(14000, 16000)  # Extra staff
        feed = random.randint(6000, 8000)
        utilities = random.randint(1500, 2000)
        supplies = random.randint(1500, 2000)
        
    elif is_weekend:
        # Weekend - high volume
        num_fights = random.randint(15, 20)
        plasada = random.randint(40000, 50000)
        gate = random.randint(15000, 25000)
        concession = random.randint(10000, 15000)
        payroll = random.randint(11000, 13000)
        feed = random.randint(4000, 5000)
        utilities = random.randint(1500, 2000)
        supplies = random.randint(1000, 1500)
        
    else:
        # Weekday - normal volume
        num_fights = random.randint(8, 12)
        plasada = random.randint(25000, 35000)
        gate = random.randint(10000, 15000)
        concession = random.randint(5000, 8000)
        payroll = random.randint(8000, 10000)
        feed = random.randint(3000, 4000)
        utilities = random.randint(1000, 1500)
        supplies = random.randint(500, 1000)
    
    daily_revenue = plasada + gate + concession
    daily_expenses = payroll + feed + utilities + supplies
    daily_profit = daily_revenue - daily_expenses
    
    stats['total_revenue'] += daily_revenue
    stats['total_expenses'] += daily_expenses
    
    # ===== CREATE EVENT =====
    event_name = "Special Tournament" if is_tournament else f"{day_name} Derby"
    event_type = "tournament" if is_tournament else "derby"
    
    for boss_id in BOSS_IDS:
        cursor = conn.execute(
            """INSERT INTO events (boss_id, arena_id, date, name, event_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (boss_id, 'infanta', date_str, event_name, event_type, datetime.now().isoformat())
        )
        event_id = cursor.lastrowid
        stats['events'] += 1
        
        # ===== CREATE FIGHTS =====
        rooster_names = ['Hawk', 'Tiger', 'Dragon', 'Phoenix', 'Eagle', 'Falcon', 
                        'Warrior', 'Champion', 'Storm', 'Thunder', 'Blaze', 'Inferno',
                        'Shadow', 'Ghost', 'Spirit', 'Demon', 'Beast', 'Monster']
        
        for fight_num in range(1, num_fights + 1):
            meron_owner = random.choice(['Owner A', 'Owner B', 'Owner C', 'Owner D', 'Owner E'])
            wala_owner = random.choice(['Owner F', 'Owner G', 'Owner H', 'Owner I', 'Owner J'])
            winner = random.choice(['Meron', 'Wala', 'Draw'])
            pit_fee = random.randint(500, 2000)
            
            conn.execute(
                """INSERT INTO fights (boss_id, event_id, fight_number, date, meron_owner, wala_owner, 
                                       winner, pit_fee, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (boss_id, event_id, fight_num, date_str, meron_owner, wala_owner, winner, pit_fee, 
                 datetime.now().isoformat())
            )
            stats['fights'] += 1
        
        # ===== RECORD REVENUE =====
        # Plasada (house betting commission)
        conn.execute(
            """INSERT INTO event_revenue (boss_id, event_id, date, source, amount, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (boss_id, event_id, date_str, 'plasada', plasada, 
             f'{num_fights} fights - house commission', datetime.now().isoformat())
        )
        stats['revenue_entries'] += 1
        
        # Gate revenue
        conn.execute(
            """INSERT INTO event_revenue (boss_id, event_id, date, source, amount, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (boss_id, event_id, date_str, 'gate', gate, 
             f'Entry fees - {random.randint(50, 150)} spectators', datetime.now().isoformat())
        )
        stats['revenue_entries'] += 1
        
        # Concessions
        conn.execute(
            """INSERT INTO event_revenue (boss_id, event_id, date, source, amount, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (boss_id, event_id, date_str, 'concession', concession, 
             'Food, drinks, merchandise sales', datetime.now().isoformat())
        )
        stats['revenue_entries'] += 1
        
        # ===== RECORD EXPENSES =====
        # Payroll
        conn.execute(
            """INSERT INTO expenses (boss_id, date, amount, category, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (boss_id, date_str, payroll, 'payroll', 
             f'Staff salaries - {random.randint(6, 10)} personnel', datetime.now().isoformat())
        )
        stats['expense_entries'] += 1
        
        # Feed
        conn.execute(
            """INSERT INTO expenses (boss_id, date, amount, category, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (boss_id, date_str, feed, 'feed', 
             f'Rooster feed and care for {num_fights} fights', datetime.now().isoformat())
        )
        stats['expense_entries'] += 1
        
        # Utilities
        conn.execute(
            """INSERT INTO expenses (boss_id, date, amount, category, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (boss_id, date_str, utilities, 'utilities', 
             'Electricity, water, maintenance', datetime.now().isoformat())
        )
        stats['expense_entries'] += 1
        
        # Supplies
        conn.execute(
            """INSERT INTO expenses (boss_id, date, amount, category, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (boss_id, date_str, supplies, 'supplies', 
             'Cleaning, equipment, miscellaneous', datetime.now().isoformat())
        )
        stats['expense_entries'] += 1
    
    # Print progress
    print(f"Day {day_count:2d} - {date_str} ({day_name:9s}) | "
          f"Fights: {num_fights:2d} | Revenue: {daily_revenue:,} | "
          f"Expenses: {daily_expenses:,} | Profit: {daily_profit:,}")
    
    current_date += timedelta(days=1)

# ===== ADD REMITTANCES =====
print("\n" + "=" * 70)
print("ADDING REMITTANCES (Twice per month)")
print("=" * 70 + "\n")

remittance_dates = [
    datetime(2026, 8, 7),   # Week 1
    datetime(2026, 8, 14),  # Mid-month
    datetime(2026, 8, 21),  # Week 3
    datetime(2026, 8, 28),  # Week 4
]

# Calculate average weekly revenue to make remittances realistic
avg_weekly_revenue = stats['total_revenue'] / 4

for remit_date in remittance_dates:
    date_str = remit_date.date().isoformat()
    # Remittance is roughly 50% of weekly revenue (the other 50% goes to operations)
    remit_amount = int(avg_weekly_revenue * 0.5 * random.uniform(0.9, 1.1))
    
    for boss_id in BOSS_IDS:
        conn.execute(
            """INSERT INTO cash_remittances (boss_id, date, amount, note, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (boss_id, date_str, remit_amount, 
             f'Weekly remittance to owners - {remit_date.strftime("%B %d")}',
             datetime.now().isoformat())
        )
        stats['remittances'] += 1
        
        print(f"Boss {boss_id} ({BOSS_NAMES[boss_id-1]:8s}) - {date_str}: {remit_amount:,}")

conn.commit()
conn.close()

# ===== PRINT SUMMARY =====
print("\n" + "=" * 70)
print("SAMPLE DATA SUMMARY - AUGUST 2026")
print("=" * 70)

monthly_profit = stats['total_revenue'] - stats['total_expenses']
monthly_margin = (monthly_profit / stats['total_revenue'] * 100) if stats['total_revenue'] > 0 else 0

summary = f"""
INFANTA ARENA (1 Month)
  Events Created:        {stats['events']:,}
  Fights Recorded:       {stats['fights']:,}
  Revenue Entries:       {stats['revenue_entries']:,}
  Expense Entries:       {stats['expense_entries']:,}
  Remittances Recorded:  {stats['remittances']:,}

FINANCIALS
  Total Revenue:         {stats['total_revenue']:,}
  Total Expenses:        {stats['total_expenses']:,}
  Net Profit:            {monthly_profit:,}
  Profit Margin:         {monthly_margin:.1f}%
  Profit Per Boss:       {monthly_profit // 6:,}

DAILY AVERAGES (÷30 days)
  Revenue:               {stats['total_revenue'] // 30:,}/day
  Expenses:              {stats['total_expenses'] // 30:,}/day
  Profit:                {monthly_profit // 30:,}/day
"""

print(summary)

print("=" * 70)
print("[OK] Sample data loaded successfully!")
print("=" * 70)
print("\nNow login as any boss and go to /analytics to see the data!")
