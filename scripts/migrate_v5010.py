import sqlite3, os
DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Add new columns (idempotent)
cols = [
    ("snapshots", "data_date", "TEXT"),
    ("snapshots", "data_is_final", "INTEGER DEFAULT 0"),
    ("snapshots", "market_session", "TEXT"),
    ("snapshots", "macro_checked_at", "TEXT"),
    ("snapshots", "macro_gate_passed", "INTEGER DEFAULT 0"),
    ("snapshots", "spy_price_at_scan", "REAL"),
    ("snapshots", "sma20_at_scan", "REAL"),
    ("outcomes", "performance_bucket", "TEXT"),
    ("outcomes", "evaluation_type", "TEXT DEFAULT 'LIVE'"),
    ("outcomes", "ambiguous_bar", "INTEGER DEFAULT 0"),
    ("outcomes", "entry_date", "TEXT"),
]

for table, col, typ in cols:
    cur.execute(f"PRAGMA table_info({table})")
    existing = {r[1] for r in cur.fetchall()}
    if col not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        print(f"✅ Added {table}.{col}")

# Unique index
cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_outcomes_unique
    ON outcomes(snapshot_id, outcome_horizon, exit_rules_version)
""")
print("✅ Created unique index")

# Mark existing outcomes as LEGACY
cur.execute("UPDATE outcomes SET evaluation_type = 'LEGACY' WHERE evaluation_type IS NULL")
print(f"✅ Marked {cur.rowcount} legacy outcomes")

conn.commit()
conn.close()
print("Migration complete.")
