import sqlite3

conn = sqlite3.connect('data/alerts.db')
cursor = conn.execute("SELECT * FROM alerts ORDER BY sent_at DESC")
rows = cursor.fetchall()

# Get column names
columns = [description[0] for description in cursor.description]

print("\n" + "="*80)
print("📊 ALERTS TABLE")
print("="*80)
print(" | ".join(columns))
print("-"*80)

for row in rows:
    print(" | ".join(str(item) for item in row))

conn.close()
