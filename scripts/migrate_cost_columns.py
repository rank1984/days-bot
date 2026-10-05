#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6.4 — Migration: cost logging columns

Adds 12 columns to outcomes for cost/tax decomposition.
These columns are LOG-ONLY. They never influence:
  - trigger decisions
  - Event inclusion
  - net_r_status
  - pre-registration logic

They exist so that after 50 Events we can compare:
  - RAW RESULT (net_r as-is)
  - COST-ADJUSTED RESULT (net_after_tax_pct, net_edge_score)

Idempotent — safe to run multiple times.
"""
import os
import sys
import sqlite3

DB_PATH = "data/alerts.db"

COST_COLUMNS = [
    # Spread at trigger (measured from snapshot/quote)
    ("spread_at_trigger_pct", "REAL"),
    # Spread at exit (usually unknown; conservative = same as trigger)
    ("spread_at_exit_pct", "REAL"),
    # Full round-trip = spread_at_trigger + spread_at_exit
    ("round_trip_spread_pct", "REAL"),
    # Estimated slippage (model: 0.5% normal, 1-2% for wide spreads)
    ("estimated_slippage_pct", "REAL"),
    # Position value in dollars
    ("position_value", "REAL"),
    # Blink fee (dollars and %)
    ("blink_fee_dollars", "REAL"),
    ("blink_fee_pct", "REAL"),
    # Tax decomposition
    ("gross_target_pct", "REAL"),
    ("net_before_tax_pct", "REAL"),
    ("net_after_tax_pct", "REAL"),
    # Composite score (0-100)
    ("net_edge_score", "REAL"),
    # Track which cost model version was used
    ("blink_cost_version", "TEXT"),
]


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
    print("MIGRATION — cost logging columns")
    print("=" * 74)

    cols = _cols(cur, "outcomes")
    if not cols:
        print("outcomes table not found")
        conn.close()
        return 0

    added = 0
    skipped = 0
    for col, decl in COST_COLUMNS:
        if col in cols:
            skipped += 1
            continue
        try:
            cur.execute(f"ALTER TABLE outcomes ADD COLUMN {col} {decl}")
            conn.commit()
            print(f"  + outcomes.{col}")
            added += 1
        except Exception as e:
            print(f"  ! outcomes.{col} failed: {e}")

    print()
    print(f"  added:   {added}")
    print(f"  skipped: {skipped} (already present)")
    print("=" * 74)
    print("MIGRATION COMPLETE")
    print("=" * 74)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())