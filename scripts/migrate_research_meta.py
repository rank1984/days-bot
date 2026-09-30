#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6.3 — Migration: research_run metadata columns

Adds 3 columns to snapshots:
  - is_scheduled     (1 if github.event_name == 'schedule')
  - in_pm_window     (1 if snapshot_time_et in [04:00, 09:30))
  - preflight_passed (1 if preflight.py exited 0)

research_run = is_scheduled AND in_pm_window AND preflight_passed

Idempotent — safe to run multiple times.
"""
import os
import sys
import sqlite3

DB_PATH = "data/alerts.db"


def _cols(cur, table):
    try:
        return {r[1] for r in cur.execute("PRAGMA table_info(" + table + ")")}
    except sqlite3.OperationalError:
        return set()


def main():
    if not os.path.exists(DB_PATH):
        print("DB not found at " + DB_PATH)
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print()
    print("=" * 74)
    print("MIGRATION — research_run metadata")
    print("=" * 74)

    cols = _cols(cur, "snapshots")
    if not cols:
        print("snapshots table not found — nothing to do")
        conn.close()
        return 0

    for col, decl in (
        ("is_scheduled", "INTEGER DEFAULT 0"),
        ("in_pm_window", "INTEGER DEFAULT 0"),
        ("preflight_passed", "INTEGER DEFAULT 0"),
    ):
        if col in cols:
            print(f"  {col} already present — skipping")
        else:
            cur.execute(f"ALTER TABLE snapshots ADD COLUMN {col} {decl}")
            conn.commit()
            print(f"  {col} added")

    # Best-effort backfill of in_pm_window from snapshot_time_et
    try:
        cur.execute("""
            UPDATE snapshots
            SET in_pm_window = 1
            WHERE snapshot_time_et IS NOT NULL
              AND CAST(SUBSTR(snapshot_time_et, 12, 2) AS INTEGER) >= 4
              AND CAST(SUBSTR(snapshot_time_et, 12, 2) AS INTEGER) < 9
        """)
        conn.commit()
        print("  backfill: in_pm_window=1 for snapshots in [04:00, 09:30)")
    except Exception as e:
        print(f"  backfill skipped: {e}")

    total = cur.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    pm = cur.execute("SELECT COUNT(*) FROM snapshots WHERE in_pm_window=1").fetchone()[0]
    sched = cur.execute("SELECT COUNT(*) FROM snapshots WHERE is_scheduled=1").fetchone()[0]
    pf = cur.execute("SELECT COUNT(*) FROM snapshots WHERE preflight_passed=1").fetchone()[0]

    print(f"  total snapshots:       {total}")
    print(f"  in_pm_window=1:        {pm}")
    print(f"  is_scheduled=1:        {sched}")
    print(f"  preflight_passed=1:    {pf}")
    print("=" * 74)
    print("MIGRATION COMPLETE")
    print("=" * 74)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
