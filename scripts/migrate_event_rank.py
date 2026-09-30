#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6 — Migration: add event_rank to trigger_results

Enforces the "one Event per ticker per day" rule (P12).

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
        print("(nothing to migrate — will run when DB exists)")
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print()
    print("=" * 74)
    print("MIGRATION — event_rank")
    print("=" * 74)

    cols = _cols(cur, "trigger_results")
    if not cols:
        print("trigger_results table not found — nothing to do")
        conn.close()
        return 0

    if "event_rank" in cols:
        print("  event_rank already present — skipping ADD COLUMN")
    else:
        cur.execute(
            "ALTER TABLE trigger_results "
            "ADD COLUMN event_rank INTEGER DEFAULT 1"
        )
        conn.commit()
        print("  event_rank column added")

    # Backfill: for each (ticker, date), the earliest trigger gets rank=1
    # All others get rank=2, 3, ...
    try:
        cur.execute("""
            UPDATE trigger_results
            SET event_rank = 1
            WHERE trigger_result_id IN (
                SELECT MIN(tr.trigger_result_id)
                FROM trigger_results tr
                JOIN snapshots s ON s.snapshot_id = tr.snapshot_id
                GROUP BY s.ticker, s.scan_date
            )
        """)
        conn.commit()
        print("  backfill: earliest trigger per (ticker, date) set to rank=1")

        cur.execute("""
            UPDATE trigger_results
            SET event_rank = 2
            WHERE trigger_result_id NOT IN (
                SELECT MIN(tr.trigger_result_id)
                FROM trigger_results tr
                JOIN snapshots s ON s.snapshot_id = tr.snapshot_id
                GROUP BY s.ticker, s.scan_date
            )
        """)
        conn.commit()
        print("  backfill: remaining triggers set to rank=2")
    except sqlite3.OperationalError as e:
        print(f"  backfill skipped: {e}")

    # Verify
    total = cur.execute("SELECT COUNT(*) FROM trigger_results").fetchone()[0]
    rank1 = cur.execute(
        "SELECT COUNT(*) FROM trigger_results WHERE event_rank = 1"
    ).fetchone()[0]
    print(f"  total trigger_results: {total}")
    print(f"  rank=1:                {rank1}")
    print("=" * 74)
    print("MIGRATION COMPLETE")
    print("=" * 74)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())