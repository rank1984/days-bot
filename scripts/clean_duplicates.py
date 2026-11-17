import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")

if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ספירה לפני
count_before = cur.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
print(f"Total outcomes BEFORE cleanup: {count_before}")

# מחיקת כפילויות (משאיר רק את הרשומה הראשונה לכל snapshot_id + outcome_horizon)
cur.execute("""
    DELETE FROM outcomes
    WHERE outcome_id NOT IN (
        SELECT MIN(outcome_id)
        FROM outcomes
        GROUP BY snapshot_id, outcome_horizon
    )
""")
conn.commit()

# ספירה אחרי
count_after = cur.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
print(f"Total outcomes AFTER cleanup: {count_after}")
print(f"Deleted duplicates: {count_before - count_after}")

conn.close()
print("Cleanup complete.")
