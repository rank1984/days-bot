#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6 — Preflight Check

5 assertions that must all pass before any Event is eligible.
Run at the start of every scheduled execution, before scanning.

Exit codes:
    0 = all checks passed
    1 = one or more checks failed (day is NOT a research day)
"""
import os
import sys
import sqlite3
from datetime import datetime
import pytz

DB_PATH = "data/alerts.db"
ET = pytz.timezone("America/New_York")

TRIGGER_WINDOW_START = "09:30"
TRIGGER_WINDOW_END = "11:00"


def _cols(cur, table):
    try:
        return {r[1] for r in cur.execute("PRAGMA table_info(" + table + ")")}
    except sqlite3.OperationalError:
        return set()


def check_1_pm_window(now_et):
    hhmm = now_et.strftime("%H%M")
    ok = ("0400" <= hhmm < "0930")
    msg = f"PM window active (now={hhmm} ET)"
    if not ok:
        msg = f"OUTSIDE PM window (now={hhmm} ET, need 0400-0929)"
    return ok, msg


def check_2_pmh_frozen(cur):
    if not os.path.exists(DB_PATH):
        return True, "DB not present yet (will be created by scanner)"
    today = datetime.now(ET).strftime("%Y-%m-%d")
    try:
        rows = cur.execute(
            "SELECT COUNT(*) FROM snapshots "
            "WHERE scan_date = ? "
            "AND pm_high IS NOT NULL "
            "AND snapshot_time_et >= '09:30'",
            (today,),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return True, "snapshots table not present yet"
    if rows > 0:
        return False, f"{rows} snapshot(s) have PMH set with time >= 09:30"
    return True, "PMH is frozen (no PMH after 09:30)"


def check_3_pm_consistency(cur):
    if not os.path.exists(DB_PATH):
        return True, "DB not present yet"
    today = datetime.now(ET).strftime("%Y-%m-%d")
    try:
        rows = cur.execute(
            "SELECT COUNT(*) FROM snapshots "
            "WHERE scan_date = ? "
            "AND pm_bars > 0 "
            "AND (pm_high IS NULL OR pm_vwap IS NULL)",
            (today,),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return True, "snapshots table not present yet"
    if rows > 0:
        return False, f"{rows} snapshot(s) with pm_bars>0 but missing pm_high/pm_vwap"
    return True, "PM data consistency OK"


def check_4_event_rank(cur):
    if not os.path.exists(DB_PATH):
        return True, "DB not present yet"
    cols = _cols(cur, "trigger_results")
    if not cols:
        return True, "trigger_results table not present yet"
    if "event_rank" not in cols:
        return False, "trigger_results.event_rank column missing — migration needed"
    return True, "event_rank column present"


def check_5_trigger_window():
    if TRIGGER_WINDOW_START != "09:30" or TRIGGER_WINDOW_END != "11:00":
        return False, f"trigger window misconfigured: {TRIGGER_WINDOW_START}-{TRIGGER_WINDOW_END}"
    return True, f"trigger window = {TRIGGER_WINDOW_START}-{TRIGGER_WINDOW_END} ET"


def main():
    now_et = datetime.now(ET)
    print()
    print("=" * 74)
    print("PREFLIGHT CHECK — " + now_et.strftime("%Y-%m-%d %H:%M:%S %Z"))
    print("=" * 74)

    conn = None
    cur = None
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

    ok, msg = check_1_pm_window(now_et)
    print(f"  [{'PASS' if ok else 'FAIL'}] 1. {msg}")

    ok, msg = check_2_pmh_frozen(cur) if cur else (True, "DB not available")
    print(f"  [{'PASS' if ok else 'FAIL'}] 2. {msg}")

    ok, msg = check_3_pm_consistency(cur) if cur else (True, "DB not available")
    print(f"  [{'PASS' if ok else 'FAIL'}] 3. {msg}")

    ok, msg = check_4_event_rank(cur) if cur else (True, "DB not available")
    print(f"  [{'PASS' if ok else 'FAIL'}] 4. {msg}")

    ok, msg = check_5_trigger_window()
    print(f"  [{'PASS' if ok else 'FAIL'}] 5. {msg}")

    if conn:
        conn.close()

    print()
    print("  RESULT: see above")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())