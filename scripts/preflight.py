#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6 — Preflight Check (V5.0.6.3)

5 assertions that determine whether the current day counts as a
research day. This script does NOT block the workflow — it prints
results and exits with:
    0 = all pass
    1 = at least one fail

The workflow wrapper must read the exit code to decide whether the
day is eligible for Event counting. Do not print "PASSED" from the
wrapper unless preflight exited 0.
"""
import os
import sys
import json
import sqlite3
from datetime import datetime
import pytz

DB_PATH = "data/alerts.db"
ET = pytz.timezone("America/New_York")

TRIGGER_WINDOW_START = "09:30"
TRIGGER_WINDOW_END = "11:00"
PM_WINDOW_START = "04:00"
PM_WINDOW_END = "09:30"


def _cols(cur, table):
    try:
        return {r[1] for r in cur.execute("PRAGMA table_info(" + table + ")")}
    except sqlite3.OperationalError:
        return set()


# ---------------------------------------------------------------------------
# Check 1 — PM window active (current time)
# ---------------------------------------------------------------------------

def check_1_pm_window(now_et):
    hhmm = now_et.strftime("%H%M")
    ok = (PM_WINDOW_START.replace(":", "") <= hhmm < PM_WINDOW_END.replace(":", ""))
    if ok:
        return True, f"PM window active (now={hhmm} ET)"
    return False, f"outside PM window (now={hhmm} ET, need {PM_WINDOW_START}-{PM_WINDOW_END})"


# ---------------------------------------------------------------------------
# Check 2 — PMH consistency: pm_high matches max(high) of pm_bars_json
# ---------------------------------------------------------------------------

def check_2_pmh_consistency(cur):
    """
    For each snapshot with pm_bars > 0 and pm_bars_json present, verify
    that pm_high equals the max of pm_bars_json[*]['h'].

    This checks the invariant that PMH comes from PM bars and is not
    silently overwritten. It does NOT require snapshot_time_et < 09:30 —
    a snapshot taken later is fine as long as pm_high matches pm_bars.
    """
    if not os.path.exists(DB_PATH):
        return False, "DB not found"

    today = datetime.now(ET).strftime("%Y-%m-%d")
    try:
        rows = cur.execute(
            "SELECT snapshot_id, ticker, pm_high, pm_bars_json "
            "FROM snapshots "
            "WHERE scan_date = ? AND pm_bars > 0 AND pm_bars_json IS NOT NULL",
            (today,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        return False, f"DB error: {e}"

    mismatches = []
    for r in rows:
        try:
            bars = json.loads(r["pm_bars_json"])
        except Exception:
            continue
        if not isinstance(bars, list) or not bars:
            continue
        highs = [float(b["h"]) for b in bars if isinstance(b, dict) and b.get("h") is not None]
        if not highs:
            continue
        pm_high_db = float(r["pm_high"]) if r["pm_high"] is not None else None
        pm_high_calc = max(highs)
        if pm_high_db is None or abs(pm_high_db - pm_high_calc) > 0.01:
            mismatches.append((r["snapshot_id"], r["ticker"], pm_high_db, pm_high_calc))

    if mismatches:
        return False, f"{len(mismatches)} snapshot(s) with pm_high != max(pm_bars)"
    return True, "PMH consistent with pm_bars (pm_high = max of PM bars)"


# ---------------------------------------------------------------------------
# Check 3 — pm_bars > 0 requires pm_high (pm_vwap can be NULL)
# ---------------------------------------------------------------------------

def check_3_pm_high_required(cur):
    """
    Invariant: pm_bars > 0 => pm_high IS NOT NULL.
    pm_vwap can be NULL (yfinance provides bars without volume).
    If pm_vwap is NULL -> that Event cannot execute, but that is
    NOT a data integrity violation.
    """
    if not os.path.exists(DB_PATH):
        return False, "DB not found"

    today = datetime.now(ET).strftime("%Y-%m-%d")
    try:
        rows = cur.execute(
            "SELECT COUNT(*) FROM snapshots "
            "WHERE scan_date = ? AND pm_bars > 0 AND pm_high IS NULL",
            (today,),
        ).fetchone()[0]
    except sqlite3.OperationalError as e:
        return False, f"DB error: {e}"

    if rows > 0:
        return False, f"{rows} snapshot(s) with pm_bars>0 but pm_high IS NULL"
    return True, "pm_bars>0 implies pm_high present (pm_vwap may be NULL)"


# ---------------------------------------------------------------------------
# Check 4 — event_rank column present
# ---------------------------------------------------------------------------

def check_4_event_rank(cur):
    if not os.path.exists(DB_PATH):
        return False, "DB not found"
    cols = _cols(cur, "trigger_results")
    if "event_rank" not in cols:
        return False, "trigger_results.event_rank missing — run migrate_event_rank.py"
    return True, "event_rank column present"


# ---------------------------------------------------------------------------
# Check 5 — trigger window configured correctly
# ---------------------------------------------------------------------------

def check_5_trigger_window():
    if TRIGGER_WINDOW_START != "09:30" or TRIGGER_WINDOW_END != "11:00":
        return False, f"trigger window misconfigured: {TRIGGER_WINDOW_START}-{TRIGGER_WINDOW_END}"
    return True, f"trigger window = {TRIGGER_WINDOW_START}-{TRIGGER_WINDOW_END} ET"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    results = []

    ok, msg = check_1_pm_window(now_et)
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] 1. {msg}")

    ok, msg = check_2_pmh_consistency(cur) if cur else (False, "DB not available")
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] 2. {msg}")

    ok, msg = check_3_pm_high_required(cur) if cur else (False, "DB not available")
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] 3. {msg}")

    ok, msg = check_4_event_rank(cur) if cur else (False, "DB not available")
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] 4. {msg}")

    ok, msg = check_5_trigger_window()
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] 5. {msg}")

    if conn:
        conn.close()

    passed = sum(1 for r in results if r)
    total = len(results)

    print()
    print(f"  RESULT: {passed}/{total} passed")

    if passed == total:
        print("  PREFLIGHT PASSED — day eligible for Event counting.")
        print("=" * 74)
        return 0

    print("  PREFLIGHT FAILED — day NOT eligible for Event counting.")
    print("=" * 74)
    return 1


if __name__ == "__main__":
    sys.exit(main())
