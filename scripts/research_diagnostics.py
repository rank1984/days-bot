#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6 — Research Diagnostics
Runs after scanner. Prints separated counters, PM integrity check, stale data.
Writes JSON evidence files. Always exits 0 (evidence, not failure).
"""
import os
import sys
import json
import sqlite3
from datetime import datetime
import pytz

DB_PATH = "data/alerts.db"
SCAN_DATE = os.environ.get("TODAY_ET") or os.environ.get("SCAN_DATE", "")
EVENT = os.environ.get("GITHUB_EVENT_NAME", "")
RUN_NUMBER = os.environ.get("GITHUB_RUN_NUMBER", "")
GIT_SHA = os.environ.get("GITHUB_SHA", "")


def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def check_pm_integrity(cur):
    result = {
        "scan_date": SCAN_DATE,
        "checked_at_utc": datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "violations": [],
        "status": "PASS",
    }

    rows = cur.execute(
        "SELECT snapshot_id, ticker, snapshot_time_et, "
        "pm_bars, pm_volume, pm_volume_status, "
        "pm_high, pm_low, pm_vwap, pm_source, pm_data_quality "
        "FROM snapshots "
        "WHERE scan_date = ? "
        "AND (pm_bars IS NULL OR pm_bars = 0) "
        "AND (pm_volume IS NOT NULL "
        "     OR pm_high IS NOT NULL "
        "     OR pm_low IS NOT NULL "
        "     OR pm_vwap IS NOT NULL) "
        "ORDER BY snapshot_id DESC",
        (SCAN_DATE,),
    ).fetchall()

    print()
    print("=" * 74)
    print("PM DATA INTEGRITY INVESTIGATION - " + SCAN_DATE)
    print("=" * 74)

    if rows:
        result["status"] = "VIOLATION"
        print("  WARN: " + str(len(rows)) + " PM INTEGRITY VIOLATION(S)")
        for r in rows:
            result["violations"].append({
                "snapshot_id": r[0], "ticker": r[1], "snapshot_time_et": r[2],
                "pm_bars": r[3], "pm_volume": r[4], "pm_volume_status": r[5],
                "pm_high": r[6], "pm_low": r[7], "pm_vwap": r[8],
                "pm_source": r[9], "pm_data_quality": r[10],
            })
            print("  [snap_id=" + str(r[0]) + "] " + str(r[1]) +
                  " | bars=" + str(r[3]) + " vol=" + str(r[4]) +
                  " high=" + str(r[6]) + " src=" + str(r[9]))
        print("  NOTE: EVIDENCE ONLY. Investigate root cause.")
    else:
        print("  PASS: No violations for " + SCAN_DATE)

    print("=" * 74)
    write_json("data/pm_integrity.json", result)
    return result


def check_stale_data(cur):
    result = {
        "scan_date": SCAN_DATE,
        "checked_at_utc": datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "suspects": [],
        "status": "OK",
    }

    print()
    print("=" * 74)
    print("STALE DATA DIAGNOSTIC - " + SCAN_DATE)
    print("=" * 74)

    rows = cur.execute(
        "SELECT scan_date, COUNT(*), MIN(snapshot_time_et), MAX(snapshot_time_et) "
        "FROM snapshots GROUP BY scan_date ORDER BY scan_date DESC LIMIT 5"
    ).fetchall()

    for r in rows:
        print("  " + str(r[0]) + " | n=" + str(r[1]) +
              " | " + str(r[2]) + " -> " + str(r[3]))
    print()

    dupes = cur.execute(
        "SELECT ticker, price, prev_close, "
        "GROUP_CONCAT(scan_date, ', '), COUNT(DISTINCT scan_date) "
        "FROM snapshots WHERE scan_date >= date('now', '-5 days') "
        "GROUP BY ticker, price, prev_close "
        "HAVING COUNT(DISTINCT scan_date) > 1 "
        "ORDER BY COUNT(DISTINCT scan_date) DESC LIMIT 10"
    ).fetchall()

    if dupes:
        result["status"] = "WARN"
        print("  WARN: " + str(len(dupes)) + " stale-data suspect(s):")
        for d in dupes:
            print("  " + str(d[0]) + " | price=" + str(d[1]) +
                  " | prev=" + str(d[2]) + " | days=" + str(d[4]))
            result["suspects"].append({
                "ticker": d[0], "price": d[1], "prev_close": d[2],
                "n_days": d[4], "scan_dates": d[3],
            })
    else:
        print("  OK: No stale-data suspects")

    print("=" * 74)
    write_json("data/stale_data.json", result)
    return result


def print_counters(cur):
    n_snapshots = cur.execute(
        "SELECT COUNT(*) FROM snapshots WHERE scan_date = ?", (SCAN_DATE,)
    ).fetchone()[0]

    n_pm_ok = cur.execute(
        "SELECT COUNT(*) FROM snapshots WHERE scan_date = ? AND pm_bars > 0",
        (SCAN_DATE,),
    ).fetchone()[0]
    n_pm_zero = n_snapshots - n_pm_ok

    n_pm_vol = cur.execute(
        "SELECT COUNT(*) FROM snapshots "
        "WHERE scan_date = ? AND pm_volume IS NOT NULL AND pm_volume > 0",
        (SCAN_DATE,),
    ).fetchone()[0]

    n_float_pass = cur.execute(
        "SELECT COUNT(*) FROM snapshots "
        "WHERE scan_date = ? AND float IS NOT NULL AND float <= 20000000",
        (SCAN_DATE,),
    ).fetchone()[0]

    n_liq_pass = cur.execute(
        "SELECT COUNT(*) FROM snapshots "
        "WHERE scan_date = ? AND float_gate_passed = 1",
        (SCAN_DATE,),
    ).fetchone()[0]

    n_scored = cur.execute(
        "SELECT COUNT(*) FROM snapshots "
        "WHERE scan_date = ? AND composite_score IS NOT NULL",
        (SCAN_DATE,),
    ).fetchone()[0]

    n_triggers = cur.execute(
        "SELECT COUNT(*) FROM trigger_results "
        "WHERE snapshot_id IN (SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
        (SCAN_DATE,),
    ).fetchone()[0]

    n_hits = cur.execute(
        "SELECT COUNT(*) FROM trigger_results WHERE hit = 1 "
        "AND snapshot_id IN (SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
        (SCAN_DATE,),
    ).fetchone()[0]

    n_outcomes = cur.execute(
        "SELECT COUNT(*) FROM outcomes "
        "WHERE snapshot_id IN (SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
        (SCAN_DATE,),
    ).fetchone()[0]

    n_valid = cur.execute(
        "SELECT COUNT(*) FROM outcomes WHERE net_r_status = 'VALID' "
        "AND snapshot_id IN (SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
        (SCAN_DATE,),
    ).fetchone()[0]

    n_nonexec = cur.execute(
        "SELECT COUNT(*) FROM outcomes WHERE net_r_status = 'NON_EXECUTABLE' "
        "AND snapshot_id IN (SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
        (SCAN_DATE,),
    ).fetchone()[0]

    print()
    print("=" * 74)
    print("V5.0.6 RESEARCH COUNTERS (SEPARATED)")
    print("=" * 74)
    print("  Scan date:                " + SCAN_DATE)
    print("  Event:                    " + EVENT)
    print("  Run number:               " + RUN_NUMBER)
    print("  Git SHA:                  " + GIT_SHA[:12])
    print()
    print("  -- Stage 1: Snapshots --")
    print("  Snapshots (raw):          " + str(n_snapshots))
    print()
    print("  -- Stage 2: PM Data --")
    print("  PM bars > 0:              " + str(n_pm_ok))
    print("  PM bars = 0:              " + str(n_pm_zero))
    print("  PM volume > 0:            " + str(n_pm_vol))
    print()
    print("  -- Stage 3: Gates --")
    print("  Float <= 20M:             " + str(n_float_pass))
    print("  Float Gate PASS:          " + str(n_liq_pass))
    print("  Scored (composite):       " + str(n_scored))
    print()
    print("  -- Stage 4: Triggers --")
    print("  Triggers total:           " + str(n_triggers))
    print("  Trigger hits:             " + str(n_hits))
    print()
    print("  -- Stage 5: Outcomes --")
    print("  Outcomes total:           " + str(n_outcomes))
    print("  Outcomes VALID:           " + str(n_valid))
    print("  Outcomes NON_EXECUTABLE:  " + str(n_nonexec))
    print("=" * 74)


def main():
    if not os.path.exists(DB_PATH):
        print("DB not found at " + DB_PATH)
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    check_pm_integrity(cur)
    check_stale_data(cur)
    print_counters(cur)

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())