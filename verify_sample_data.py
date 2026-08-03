import db
db.init_db()
conn = db.get_connection()
events = conn.execute('SELECT COUNT(*) as cnt FROM events WHERE boss_id = 1').fetchone()['cnt']
fights = conn.execute('SELECT COUNT(*) as cnt FROM fights WHERE boss_id = 1').fetchone()['cnt']
revenue = conn.execute('SELECT COUNT(*) as cnt FROM event_revenue WHERE boss_id = 1').fetchone()['cnt']
expenses = conn.execute('SELECT COUNT(*) as cnt FROM expenses WHERE boss_id = 1').fetchone()['cnt']
total_rev = conn.execute('SELECT COALESCE(SUM(amount), 0) as total FROM event_revenue WHERE boss_id = 1').fetchone()['total']
total_exp = conn.execute('SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE boss_id = 1').fetchone()['total']
conn.close()

print("SAMPLE DATA VERIFICATION")
print("=" * 50)
print(f"Events:             {events}")
print(f"Fights:             {fights}")
print(f"Revenue entries:    {revenue}")
print(f"Expense entries:    {expenses}")
print(f"Total revenue:      {total_rev:,.0f}")
print(f"Total expenses:     {total_exp:,.0f}")
print(f"Net profit:         {int(total_rev - total_exp):,.0f}")
print(f"Profit margin:      {((total_rev - total_exp) / total_rev * 100):.1f}%")
print("=" * 50)
