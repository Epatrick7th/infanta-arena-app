from werkzeug.security import generate_password_hash
import sqlite3

conn = sqlite3.connect('data/sabong.db')
# Delete old user
conn.execute("DELETE FROM users WHERE username = 'patrick'")
# Create new with pbkdf2
new_hash = generate_password_hash('password123', method='pbkdf2')
conn.execute(
    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
    ('patrick', new_hash, 'super_admin')
)
conn.commit()
conn.close()
print("User recreated with pbkdf2 hash")
