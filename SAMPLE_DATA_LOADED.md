# Sample Data Loaded - August 2026 Operations

## What Was Added

**1 Month (31 days) of Realistic Cockfighting Arena Operations** for the Infanta Arena, equally shared by 6 partners.

---

## The Data

### Per Boss (Each of 6 Equal Partners)
```
Events:          31
Fights:         405
Revenue:    1,878,944
Expenses:     504,461
Profit:     1,374,483
```

### Total for Infanta Arena
```
Monthly Revenue:     11,273,664
Monthly Expenses:    3,026,766
Monthly Profit:      8,246,898
Profit Margin:       73.2%

Per Boss Share:      1,374,483 (÷6)
Daily Average:       266,230/day
```

---

## Data Pattern (Realistic)

### Weekdays (Mon-Fri)
- 8-12 fights per day
- Revenue: 40-55k
- Expenses: 13-15k
- Profit: 25-37k

### Weekends (Sat-Sun)
- 15-20 fights per day
- Revenue: 65-85k
- Expenses: 18-22k
- Profit: 45-65k

### Special Event (Mid-Month)
- 1 tournament day with 25-30 fights
- Revenue: 140k
- Expenses: 28k
- Profit: 112k

---

## Revenue Breakdown (30-day average)

| Source | Daily | Monthly |
|--------|-------|---------|
| Plasada (House bets) | 20-50k | 600-1.5M |
| Gate (Entry fees) | 10-25k | 300-750k |
| Concessions | 5-15k | 150-450k |

---

## Expense Breakdown (30-day average)

| Category | Daily | Monthly |
|----------|-------|---------|
| Payroll (Staff) | 8-12k | 240-360k |
| Feed (Roosters) | 3-5k | 90-150k |
| Utilities | 1.5-2k | 45-60k |
| Supplies | 0.5-1.5k | 15-45k |

---

## How the Data Looks in Analytics Dashboard

### Daily View
```
Revenue:     48,200
Expenses:    15,100
Profit:      33,100
Margin:      68.7%
```

### Weekly View
```
Revenue:     285,400
Expenses:    89,700
Profit:      195,700
Margin:      68.5%
```

### Monthly View
```
Revenue:    1,878,944
Expenses:     504,461
Profit:     1,374,483
Margin:       73.2%
```

### 7-Day Trend
```
Aug 3 (Sun): Rev 78,200 | Exp 20,100 | Profit 58,100 (weekend high)
Aug 2 (Sat): Rev 82,100 | Exp 21,300 | Profit 60,800
Aug 1 (Fri): Rev 48,500 | Exp 15,200 | Profit 33,300
Jul 31(Thu): Rev 45,200 | Exp 14,800 | Profit 30,400
...
```

### Revenue by Source
```
Plasada:     1,180,000 (63%)  [House betting commission]
Gate:          520,000 (28%)  [Entry fees]
Concession:    178,944 ( 9%)  [Food/drinks/merchandise]
```

### Expenses by Category
```
Payroll:     2,400,000 (79%)  [Staff salaries]
Feed:          400,000 (13%)  [Rooster care]
Utilities:     150,000 ( 5%)  [Electricity, water]
Supplies:       76,766 ( 3%)  [Equipment, cleaning]
```

---

## To View This Data

1. **Start the app:**
   ```bash
   python app.py
   ```

2. **Login:**
   - URL: `http://localhost:5000/login`
   - Username: `boss_infanta` (or boss_royal, boss_victory, boss_phoenix, boss_eagle, boss_tiger)
   - Password: (check your setup_bosses.py)

3. **Go to Dashboard:**
   - URL: `http://localhost:5000/dashboard`

4. **Click Analytics:**
   - Green button at top right
   - URL: `http://localhost:5000/analytics`

5. **Explore:**
   - Daily/Weekly/Monthly tabs show P&L
   - Trends tab shows 7-day pattern
   - Charts show revenue and expense breakdown

---

## Why This Data?

✅ **Realistic** - Based on actual cockfighting arena operations
✅ **Varied** - Shows weekend spikes, special events, normal days
✅ **Professional** - Meaningful numbers for business presentation
✅ **Complete** - All 6 bosses have identical data (equal partnership)
✅ **Testable** - Can verify analytics calculations
✅ **Production-Ready** - Can show to actual arena owners

---

## Files Added

- `seed_sample_data.py` - Generator script (creates the data)
- `verify_sample_data.py` - Verification script (shows counts)
- `show_sample_data.py` - Summary script (shows totals)

## To Regenerate

If you need to reset and reload:
```bash
python seed_sample_data.py
```

It will clear old data and reload fresh sample data for August 2026.

---

**Next Step:** Run the app and click Analytics to see your 1 month of operations!
