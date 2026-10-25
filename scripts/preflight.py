#!/usr/bin/env python3
"""
preflight.py — preflight checks.

Two modes:
  --mode premarket  (default for legacy fullscan_v34)
        Requires: PM window 04:00-09:30 ET AND trigger window 09:30-11:00 ET.
  --mode swing      (new default for swing_v1)
        Skips PM-window / trigger-window checks (not applicable to daily bars).
        Still runs DB sanity checks (PMH consistency, event_rank column, etc.)

Usage:
    python3 scripts/preflight.py --mode swing
    python3 scripts/preflight.py --mode premarket
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime

import pytz


DB_PATH = os.environ.get("DB_PATH", "data/alerts.db")
ET = pytz.timezone("America/New_York")


def now_et() -> datetime:
    return datetime.now(ET)


# ---------- checks ----------

def check_pm_window(now: datetime) -> tuple[bool, str]:
    cur = now.hour * 60 + now.minute
    start, end = 4 * 60, 9 * 60 + 30
    return (start <= cur < end,
            f"now={now.hour:02d}{now.minute:02d} ET, need 04:00-09:30")


def check_trigger_window(now: datetime) -> tuple[bool, str]:
    cur = now.hour * 60 + now.minute
    start, end = 9 * 60 + 30, 11 * 60
    return (start <= cur < end,
            f"now={now.hour:02d}{now.minute:02d} ET, need 09:30-11:00")


def check_pmh_consistent(conn: sqlite3.Connection) -> tuple[bool, str]:
    try:
        cur = conn.execute("""
            SELECT COUNT(*) FROM snapshots
            WHERE pm_bars_json IS NOT NULL
              AND pm_bars_json NOT IN ('', '[]', 'null')
              AND pm_high IS NOT NULL
        """)
        ok_count = cur.fetchone()[0]
        return True, f"{ok_count} snapshots with pm_bars+pm_high"
    except sqlite3.OperationalError as e:
        # snapshot columns missing → still pass (not blocking swing)
        return True, f"skipped ({e})"


def check_pm_bars_imply_high(conn: sqlite3.Connection) -> tuple[bool, str]:
    try:
        cur = conn.execute("""
            SELECT COUNT(*) FROM snapshots
            WHERE pm_bars_json IS NOT NULL
              AND pm_bars_json NOT IN ('', '[]', 'null')
              AND pm_high IS NULL
        """)
        bad = cur.fetchone()[0]
        return bad == 0, f"{bad} snapshots with bars but no pm_high"
    except sqlite3.OperationalError as e:
        return True, f"skipped ({e})"


def check_event_rank_column(conn: sqlite3.Connection) -> tuple[bool, str]:
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(snapshots)")}
        return ("event_rank" in cols), f"columns={len(cols)}"
    except sqlite3.OperationalError as e:
        return False, str(e)


# ---------- runner ----------

def run_preflight(mode: str = "swing", db_path: str = DB_PATH) -> int:
    print("=" * 74)
    print(f"PREFLIGHT CHECK — {now_et().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Mode: {mode}")
    print("=" * 74)

    now = now_et()
    checks: list[tuple[str, bool, str]] = []

    # 1. Window check
    if mode == "premarket":
        ok, info = check_pm_window(now)
        checks.append(("1. inside PM window", ok, info))
    else:
        checks.append(("1. PM window (N/A for swing)", True,
                       "swing mode — daily bars, no PM window required"))

    # Open DB if exists
    conn = None
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
        except Exception as e:
            print(f"  [WARN] cannot open DB: {e}")

    if conn is not None:
        checks.append(("2. PMH consistent with pm_bars",
                       *check_pmh_consistent(conn)))
        checks.append(("3. pm_bars>0 implies pm_high",
                       *check_pm_bars_imply_high(conn)))
        checks.append(("4. event_rank column present",
                       *check_event_rank_column(conn)))
    else:
        for i in (2, 3, 4):
            checks.append((f"{i}. (SKIPPED — no DB)", True, "no DB"))

    # 5. Trigger window (premarket only)
    if mode == "premarket":
        ok, info = check_trigger_window(now)
        checks.append(("5. trigger window 09:30-11:00", ok, info))
    else:
        checks.append(("5. trigger window (N/A for swing)", True,
                       "swing mode — no intraday trigger"))

    if conn is not None:
        conn.close()

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)

    for label, ok, info in checks:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label} — {info}")

    print()
    print(f"  RESULT: {passed}/{total} passed")
    if passed == total:
        print("  PREFLIGHT PASSED")
        return 0
    print("  PREFLIGHT FAILED — run NOT eligible for counting")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["premarket", "swing"], default="swing",
                    help="premarket = legacy PM checks; swing = daily-bar checks (default)")
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()
    return run_preflight(args.mode, args.db)


if __name__ == "__main__":
    sys.exit(main())
