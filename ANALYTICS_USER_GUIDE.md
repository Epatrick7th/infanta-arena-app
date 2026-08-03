# Analytics Dashboard - Quick Start Guide

## How to Access

1. **Login as Boss**
   - URL: `http://localhost:5000/login`
   - Username: `boss_infanta` (or any of the 6 arena bosses)
   - Password: check `setup_bosses.py` for the password you set

2. **Go to Executive Dashboard**
   - URL: `http://localhost:5000/dashboard`
   - You'll see 4 large KPI cards + quick action buttons

3. **Click "Analytics" Button** (Green button at top right)
   - URL: `http://localhost:5000/analytics`
   - This opens the financial analytics dashboard

---

## What You'll See

### Tab 1: DAILY
```
┌─────────────────────────────────────────────────────────────────┐
│                     Financial Analytics                         │
│                  Infanta Arena - Daily Report                   │
│                                                                 │
│  Today's Revenue    Today's Expenses    Net Profit   Margin %   │
│  ₱26,000            ₱6,100              ₱19,900      76.5%      │
└─────────────────────────────────────────────────────────────────┘
```

### Tab 2: WEEKLY
Same 4 metrics but summed for the entire week

### Tab 3: MONTHLY  
Same 4 metrics but summed for the entire month

### Tab 4: TRENDS
```
Date         Revenue      Expenses      Net Profit
2026-08-03   26,000       6,100         19,900
2026-08-02   27,500       6,100         21,400
2026-08-01   29,000       6,100         22,900
...
```

### Revenue by Source
```
Plasada:     48,000 (58%)  ████████████████████
Gate:        25,500 (31%)  ███████████
Concession:   9,000 (11%)  ███
```

### Expenses by Category
```
Payroll:      15,000 (82%)  ████████████████████
Utilities:     2,400 (13%)  ███
Supplies:        900 ( 5%)  █
```

---

## Real-World Usage Scenarios

### Scenario 1: Daily Check-In (Morning)
- Boss logs in at 8am
- Clicks Analytics
- Sees: "Revenue is 26,000, expenses 6,100, profit 19,900"
- Knows the arena is healthy today
- Moves on

### Scenario 2: Weekly Review (Friday)
- Switches to WEEKLY tab
- Sees week total revenue and trends
- Compares to previous weeks mentally
- Makes staffing decisions for next week

### Scenario 3: Monthly Performance Review
- Switches to MONTHLY tab
- Sees total monthly profit: 64,200 (77.8% margin)
- Clicks TRENDS to see which days were best/worst
- Shows data to owner/finance team

### Scenario 4: Spotting Problems
- Assistant entered high expense by mistake
- Switches to MONTHLY/TRENDS
- Sees one day has unusual expense spike
- Contacts assistant to verify
- Rejects the transaction if it was an error

---

## Data Behind The Scenes

The dashboard queries your database:
- Revenue table: plasada, gate, concession, pit_fee entries
- Expenses table: payroll, utilities, supplies, etc.
- Filtered by: boss_id (so no cross-arena data leaks)
- Filtered by: date range (daily/weekly/monthly)

All data is summed and calculated in real-time when you load the page.
No manual exports needed - everything is automatic.

---

## Testing

**Already Tested:**
- Daily P&L calculation ✓
- Weekly P&L calculation ✓
- Monthly P&L calculation ✓
- Revenue breakdown ✓
- Expense breakdown ✓
- 7-day trend ✓
- Data isolation (boss can only see own data) ✓

**To Test Yourself:**
1. Load the app: `python app.py`
2. Navigate to: `http://localhost:5000/dashboard`
3. Click green "Analytics" button
4. Switch between Daily/Weekly/Monthly tabs
5. Scroll down to see breakdown charts

---

## Database Performance Note

All queries use:
- Indexed columns (boss_id, date) for fast lookups
- COALESCE to handle zero rows gracefully
- Simple SUM operations (no complex joins)

Even with 100,000 transactions per arena, queries should run in <100ms.

---

**Ready to show to your bosses!**
