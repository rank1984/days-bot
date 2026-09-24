#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6 - PM Forensics (read-only)
Classifies PM snapshot rows as LEGACY (pre-fix) vs POST-FIX violations.

The invariant we enforce:
    pm_bars == 0  =>  pm_volume IS NULL
                  AND pm_high IS NULL
                  AND pm_low IS NULL
                  AND pm_vwap IS NULL
                  AND pm_source IS NULL
                  AND (pm_bars_json IS NULL OR pm_bars_json = '[]')

Read-only. Does not modify the DB.
Always exits 0.
"""
import os
import sys
import sqlite3
import json
from datetime import datetime
import pytz

DB_PATH = "data/alerts.db"
SCAN_DATE = os.environ.get("TODAY_ET") or os.environ.get("SCAN_DATE", "")


def _cols(cur, table):
    try:
        return {r[1] for r in cur.execute("PRAGMA table_info(" + table + ")")}
    except sqlite3.OperationalError:
        return set()


def _fmt(v):
    return "NULL" if v is None else str(v)


def _print_header(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main():
    if not os.path.exists(DB_PATH):
        print("DB not found at " + DB_PATH)
        return 0

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    snap_cols = _cols(cur, "snapshots")
    if not snap_cols:
        print("snapshots table not found.")
        conn.close()
        return 0

    # Ensure all needed columns exist
    needed = {"snapshot_id", "ticker", "scan_date", "pm_bars",
              "pm_volume", "pm_high", "pm_low", "pm_vwap",
              "pm_source", "pm_bars_json"}
    missing = needed - snap_cols
    if missing:
        print("Missing columns: " + ", ".join(sorted(missing)))
        print("Cannot run full invariant check.")
        conn.close()
        return 0

    _print_header("PM FORENSICS - " + SCAN_DATE)
    print("  in_pm_window:      " + str(os.environ.get("IN_PM_WINDOW", "n/a")))
    print("  checked_at_utc:    " + datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))

    # -----------------------------------------------------------------
    # 1) Total / violation counts
    # -----------------------------------------------------------------
    invariant_violation = """
        (pm_bars IS NULL OR pm_bars = 0)
        AND (
              pm_volume IS NOT NULL
           OR pm_high IS NOT NULL
           OR pm_low IS NOT NULL
           OR pm_vwap IS NOT NULL
           OR pm_source IS NOT NULL
           OR (pm_bars_json IS NOT NULL AND pm_bars_json != '[]')
        )
    """

    total = cur.execute(
        "SELECT COUNT(*) FROM snapshots WHERE scan_date = ?",
        (SCAN_DATE,),
    ).fetchone()[0]

    viol_count = cur.execute(
        "SELECT COUNT(*) FROM snapshots "
        "WHERE scan_date = ? AND " + invariant_violation,
        (SCAN_DATE,),
    ).fetchone()[0]

    clean_count = total - viol_count

    print()
    print("  snapshots total:           " + str(total))
    print("  invariant violations:      " + str(viol_count))
    print("  clean (post-fix):          " + str(clean_count))

    # -----------------------------------------------------------------
    # 2) Full violation dump (all PM fields visible)
    # -----------------------------------------------------------------
    _print_header("VIOLATIONS - FULL DUMP (all PM fields)")
    rows = cur.execute(
        "SELECT snapshot_id, ticker, pm_bars, pm_volume, pm_high, "
        "pm_low, pm_vwap, pm_source, pm_bars_json "
        "FROM snapshots "
        "WHERE scan_date = ? AND " + invariant_violation + " "
        "ORDER BY snapshot_id ASC",
        (SCAN_DATE,),
    ).fetchall()

    if not rows:
        print("  (no violations)")
    else:
        print(
            "  {:<6} {:<8} {:<8} {:<10} {:<10} {:<8} {:<8} {:<10} {:<12}".format(
                "id", "ticker", "bars", "volume", "high",
                "low", "vwap", "source", "bars_json"
            )
        )
        print("  " + "-" * 74)
        for r in rows:
            bj = r["pm_bars_json"]
            bj_short = "(null)" if bj is None else (
                "[]" if bj == "[]" else (bj[:8] + "...")
            )
            print(
                "  {:<6} {:<8} {:<8} {:<10} {:<10} {:<8} {:<8} {:<10} {:<12}".format(
                    r["snapshot_id"],
                    str(r["ticker"])[:8],
                    _fmt(r["pm_bars"]),
                    _fmt(r["pm_volume"]),
                    _fmt(r["pm_high"]),
                    _fmt(r["pm_low"]),
                    _fmt(r["pm_vwap"]),
                    _fmt(r["pm_source"]),
                    bj_short,
                )
            )

    # -----------------------------------------------------------------
    # 3) Boundary: first snapshot_id that is CLEAN under full invariant
    # -----------------------------------------------------------------
    _print_header("BOUNDARY - first CLEAN snapshot (full invariant)")

    first_clean = cur.execute(
        "SELECT MIN(snapshot_id) FROM snapshots "
        "WHERE scan_date = ? AND NOT (" + invariant_violation + ")",
        (SCAN_DATE,),
    ).fetchone()[0]

    if first_clean is None:
        print("  first_clean:               NULL  (ALL rows violate)")
        print()
        print("  >>> CONCLUSION: fix NOT working. Do NOT clean DB.")
        print("  >>> The writer is still producing partial PM state.")
    else:
        print("  first_clean:               " + str(first_clean))

        # Look at rows on either side
        before = cur.execute(
            "SELECT COUNT(*) FROM snapshots "
            "WHERE scan_date = ? AND snapshot_id < ? AND " + invariant_violation,
            (SCAN_DATE, first_clean),
        ).fetchone()[0]

        after_viol = cur.execute(
            "SELECT COUNT(*) FROM snapshots "
            "WHERE scan_date = ? AND snapshot_id >= ? AND " + invariant_violation,
            (SCAN_DATE, first_clean),
        ).fetchone()[0]

        after_clean = cur.execute(
            "SELECT COUNT(*) FROM snapshots "
            "WHERE scan_date = ? AND snapshot_id >= ?",
            (SCAN_DATE, first_clean),
        ).fetchone()[0]

        print("  violations BEFORE clean:   " + str(before))
        print("  violations AFTER clean:    " + str(after_viol))
        print("  rows after clean (total):  " + str(after_clean))
        print()

        if after_viol == 0:
            print("  >>> CONCLUSION: FIX WORKS. Rows >= " + str(first_clean))
            print("  >>> are all clean. Legacy violations: " + str(before))
            print("  >>> Safe to run cleanup on snapshot_id < " + str(first_clean))
        else:
            print("  >>> CONCLUSION: PARTIAL FIX. " + str(after_viol))
            print("  >>> post-fix rows still violate invariant.")
            print("  >>> Do NOT clean DB. Fix writer first.")

    # -----------------------------------------------------------------
    # 4) Field-by-field breakdown of violations
    # -----------------------------------------------------------------
    _print_header("VIOLATION BREAKDOWN BY FIELD")

    fields = [
        ("pm_volume", "pm_volume IS NOT NULL"),
        ("pm_high", "pm_high IS NOT NULL"),
        ("pm_low", "pm_low IS NOT NULL"),
        ("pm_vwap", "pm_vwap IS NOT NULL"),
        ("pm_source", "pm_source IS NOT NULL"),
        ("pm_bars_json", "pm_bars_json IS NOT NULL AND pm_bars_json != '[]'"),
    ]

    for name, cond in fields:
        c = cur.execute(
            "SELECT COUNT(*) FROM snapshots "
            "WHERE scan_date = ? "
            "AND (pm_bars IS NULL OR pm_bars = 0) "
            "AND " + cond,
            (SCAN_DATE,),
        ).fetchone()[0]
        print("  {:<14} not-null in violations: {}".format(name + ":", c))

    # -----------------------------------------------------------------
    # 5) Latest 15 rows regardless of violation status
    # -----------------------------------------------------------------
    _print_header("LATEST 15 SNAPSHOTS (any status)")

    latest = cur.execute(
        "SELECT snapshot_id, ticker, pm_bars, pm_volume, pm_high, "
        "pm_low, pm_vwap, pm_source "
        "FROM snapshots WHERE scan_date = ? "
        "ORDER BY snapshot_id DESC LIMIT 15",
        (SCAN_DATE,),
    ).fetchall()

    print(
        "  {:<6} {:<8} {:<8} {:<10} {:<10} {:<8} {:<8} {:<10}".format(
            "id", "ticker", "bars", "volume", "high",
            "low", "vwap", "source"
        )
    )
    print("  " + "-" * 74)
    for r in latest:
        print(
            "  {:<6} {:<8} {:<8} {:<10} {:<10} {:<8} {:<8} {:<10}".format(
                r["snapshot_id"],
                str(r["ticker"])[:8],
                _fmt(r["pm_bars"]),
                _fmt(r["pm_volume"]),
                _fmt(r["pm_high"]),
                _fmt(r["pm_low"]),
                _fmt(r["pm_vwap"]),
                _fmt(r["pm_source"]),
            )
        )

    print()
    print("=" * 78)
    print("END PM FORENSICS")
    print("=" * 78)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())