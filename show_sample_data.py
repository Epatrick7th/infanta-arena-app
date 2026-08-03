import db

db.init_db()
conn = db.get_connection()

print("\n" + "="*70)
print("SAMPLE DATA LOADED - AUGUST 2026 OPERATIONS")
print("="*70 + "\n")

total_revenue_all = 0
total_expenses_all = 0

for boss_id in range(1, 7):
    boss = conn.execute('SELECT arena_name FROM users WHERE id = ?', (boss_id,)).fetchone()
    arena = (boss['arena_name'] if boss and boss['arena_name'] else f'Arena {boss_id}')
    
    events = conn.execute('SELECT COUNT(*) as cnt FROM events WHERE boss_id = ?', (boss_id,)).fetchone()['cnt']
    fights = conn.execute('SELECT COUNT(*) as cnt FROM fights WHERE boss_id = ?', (boss_id,)).fetchone()['cnt']
    revenue = conn.execute('SELECT COALESCE(SUM(amount), 0) as total FROM event_revenue WHERE boss_id = ?', (boss_id,)).fetchone()['total']
    expenses = conn.execute('SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE boss_id = ?', (boss_id,)).fetchone()['total']
    profit = revenue - expenses
    
    total_revenue_all += revenue
    total_expenses_all += expenses
    
    print(f"Boss {boss_id}: {arena:12s}")
    print(f"  Events:      {events:3d}")
    print(f"  Fights:      {fights:3d}")
    print(f"  Revenue:     {revenue:12,.0f}")
    print(f"  Expenses:    {expenses:12,.0f}")
    print(f"  Profit:      {profit:12,.0f}")
    print(f"  Your Share:  {profit//1:12,.0f}  (equal partnership = 100%)")
    print()

total_profit = total_revenue_all - total_expenses_all

print("="*70)
print("OVERALL INFANTA ARENA (Aug 2026)")
print("="*70)
print(f"Total Revenue:       {total_revenue_all:,.0f}")
print(f"Total Expenses:      {total_expenses_all:,.0f}")
print(f"Total Net Profit:    {total_profit:,.0f}")
print(f"Profit Margin:       {(total_profit/total_revenue_all*100):.1f}%")
print(f"Per Boss Share:      {total_profit//6:,.0f}  (÷6 owners)")
print("="*70)

print("\nTO VIEW ANALYTICS:")
print("1. Start app: python app.py")
print("2. Go to: http://localhost:5000/login")
print("3. Login as: boss_infanta (or boss_royal, boss_victory, etc.)")
print("4. Click: Analytics button")
print("5. See: Daily/Weekly/Monthly P&L analysis")

conn.close()
