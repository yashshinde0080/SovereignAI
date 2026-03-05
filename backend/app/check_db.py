import sqlite3
from pathlib import Path

db_path = Path(r"d:\SovereignAI\database\sovereign.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.execute("SELECT * FROM models;")
rows = cursor.fetchall()

print(f"Items in models: {len(rows)}")
for row in rows:
    print(dict(row))

conn.close()
