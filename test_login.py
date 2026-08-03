from werkzeug.security import check_password_hash
import sqlite3

conn = sqlite3.connect('data/sabong.db')
conn.row_factory = sqlite3.Row
row = conn.execute('SELECT * FROM users WHERE username = ?', ('patrick',)).fetchone()
conn.close()

if row:
    print(f'User found: {row["username"]}')
    print(f'Stored hash: {row["password_hash"]}')
    test_pwd = 'password123'
    result = check_password_hash(row['password_hash'], test_pwd)
    print(f'Password check result: {result}')
else:
    print('User not found')
