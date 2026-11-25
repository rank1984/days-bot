#!/usr/bin/env python3
"""
Migration V5.0.10 - DIAGNOSTIC + MIGRATION
Prints DB state first, then migrates.
"""
import sqlite3, os

DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")

print("=" * 60)
print("DIAGNOSTIC — BEFORE MIGRATION")
print("=" * 60)
print(f"DB_PATH env var: {DB_PATH}")
print(f"File exists: {os.path.exists(DB_PATH)}")

if not os.path.exists(DB_PATH):
    print(f"FATAL: DB not found at {DB_PATH}. Aborting.")
    exit(1)

print(f"File size: {os.path.getsize(DB_PATH)} bytes")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables: {tables}")

# Check outcomes count
if 'outcomes' in tables:
    cur.execute("SELECT COUNT(*) FROM outcomes")
    total_outcomes = cur.fetchone()[0]
    print(f"Outcomes count: {total_outcomes}")

    cur.execute("SELECT evaluation_type, COUNT(*) FROM outcomes GROUP BY evaluation_type")
    print(f"evaluation_type breakdown: {cur.fetchall()}")

    cur.execute("""SELECT COUNT(*) FROM (
        SELECT snapshot_id, outcome_horizon, exit_rules_version, COUNT(*) AS c
        FROM outcomes
        GROUP BY snapshot_id, outcome_horizon, exit_rules_version
        HAVING c > 1
    )""")
    dup_count = cur.fetchone()[0]
    print(f"Duplicate groups: {dup_count}")
else:
    print("WARNING: outcomes table not found!")
    total_outcomes = 0

# Check snapshots count
if 'snapshots' in tables:
    cur.execute("SELECT COUNT(*) FROM snapshots")
    print(f"Snapshots count: {cur.fetchone()[0]}")

print("=" * 60)

# ============================================================================
# MIGRATION
# ============================================================================
print("\n>>> STARTING MIGRATION\n")

# STEP 1: Add columns
print("=== STEP 1: Adding columns ===")
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
    if table not in tables:
        print(f"  ⏭️  {table} does not exist, skipping {col}")
        continue
    cur.execute(f"PRAGMA table_info({table})")
    existing = {r[1] for r in cur.fetchall()}
    if col not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        print(f"  ✅ Added {table}.{col}")
    else:
        print(f"  ⏭️  {table}.{col} already exists")

conn.commit()

# STEP 2: Dedupe
print("\n=== STEP 2: Deduping outcomes ===")
if 'outcomes' in tables:
    cur.execute("SELECT COUNT(*) FROM outcomes")
    before = cur.fetchone()[0]
    print(f"  Outcomes BEFORE: {before}")

    cur.execute("""
        DELETE FROM outcomes
        WHERE outcome_id NOT IN (
            SELECT MIN(outcome_id)
            FROM outcomes
            GROUP BY snapshot_id, outcome_horizon, exit_rules_version
        )
    """)
    removed = cur.rowcount
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM outcomes")
    after = cur.fetchone()[0]
    print(f"  Outcomes AFTER: {after}")
    print(f"  ✅ Removed {removed} duplicates")
else:
    print(f"  ⏭️  outcomes table missing, skipping")

# STEP 3: Mark LEGACY
print("\n=== STEP 3: Marking existing outcomes as LEGACY ===")
if 'outcomes' in tables:
    cur.execute("""
        UPDATE outcomes SET evaluation_type = 'LEGACY'
        WHERE evaluation_type IS NULL OR evaluation_type = 'LIVE'
    """)
    marked = cur.rowcount
    conn.commit()
    print(f"  ✅ Marked {marked} rows as LEGACY")
else:
    print(f"  ⏭️  outcomes table missing, skipping")

# STEP 4: Create unique index
print("\n=== STEP 4: Creating unique index ===")
if 'outcomes' in tables:
    try:
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_outcomes_unique
            ON outcomes(snapshot_id, outcome_horizon, exit_rules_version)
        """)
        conn.commit()
        print(f"  ✅ Created idx_outcomes_unique")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        print(f"  ⚠️  Cannot create index — duplicates still exist?")
else:
    print(f"  ⏭️  outcomes table missing, skipping")

# Final summary
print("\n" + "=" * 60)
print("FINAL STATE — AFTER MIGRATION")
print("=" * 60)
if 'outcomes' in tables:
    cur.execute("SELECT COUNT(*) FROM outcomes")
    print(f"Outcomes count: {cur.fetchone()[0]}")
    cur.execute("SELECT evaluation_type, COUNT(*) FROM outcomes GROUP BY evaluation_type")
    print(f"evaluation_type breakdown: {cur.fetchall()}")

conn.close()
print("\n✅ Migration complete.")
