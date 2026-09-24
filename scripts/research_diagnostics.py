#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6 - Research Diagnostics
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


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def _cols(cur, table):
    """Return set of column names for a table, or empty set if table missing."""
    try:
        return {r[1] for r in cur.execute("PRAGMA table_info(" + table + ")")}
    except sqlite3.OperationalError:
        return set()


def _table_exists(cur, table):
    try:
        r = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return r is not None
    except sqlite3.OperationalError:
        return False


def _count(cur, sql, params=()):
    """Safe COUNT query. Returns int or None on error."""
    try:
        row = cur.execute(sql, params).fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError as e:
        print("  WARN: counter skipped (" + str(e) + ")")
        return None


def _fmt(v):
    return "n/a" if v is None else str(v)


# ---------------------------------------------------------------------------
# schema dump (helps debug missing columns)
# ---------------------------------------------------------------------------

def dump_schema(cur):
    print()
    print("=" * 74)
    print("SCHEMA SNAPSHOT")
    print("=" * 74)
    try:
        tables = [
            r[0]
            for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
    except sqlite3.OperationalError as e:
        print("  ERROR: " + str(e))
        return

    if not tables:
        print("  (no tables)")
    for t in tables:
        cols = sorted(_cols(cur, t))
        print("  " + t + ": " + ", ".join(cols))
    print("=" * 74)


# ---------------------------------------------------------------------------
# PM integrity check
# ---------------------------------------------------------------------------

def check_pm_integrity(cur):
    result = {
        "scan_date": SCAN_DATE,
        "checked_at_utc": datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "violations": [],
        "status": "PASS",
    }

    print()
    print("=" * 74)
    print("PM DATA INTEGRITY INVESTIGATION - " + SCAN_DATE)
    print("=" * 74)

    if not _table_exists(cur, "snapshots"):
        print("  SKIP: snapshots table not found")
        print("=" * 74)
        write_json("data/pm_integrity.json", result)
        return result

    snap_cols = _cols(cur, "snapshots")
    required = {
        "snapshot_id", "ticker", "scan_date",
        "pm_bars", "pm_volume", "pm_high", "pm_source",
    }
    missing = required - snap_cols
    if missing:
        print("  SKIP: snapshots missing columns: " + ", ".join(sorted(missing)))
        print("=" * 74)
        result["status"] = "SKIPPED"
        result["missing_columns"] = sorted(missing)
        write_json("data/pm_integrity.json", result)
        return result

    # Optional columns
    opt_time = "snapshot_time_et" if "snapshot_time_et" in snap_cols else "NULL"
    opt_volstat = "pm_volume_status" if "pm_volume_status" in snap_cols else "NULL"
    opt_low = "pm_low" if "pm_low" in snap_cols else "NULL"
    opt_vwap = "pm_vwap" if "pm_vwap" in snap_cols else "NULL"
    opt_dq = "pm_data_quality" if "pm_data_quality" in snap_cols else "NULL"

    sql = (
        "SELECT snapshot_id, ticker, " + opt_time + ", "
        "pm_bars, pm_volume, " + opt_volstat + ", "
        "pm_high, " + opt_low + ", " + opt_vwap + ", "
        "pm_source, " + opt_dq + " "
        "FROM snapshots "
        "WHERE scan_date = ? "
        "AND (pm_bars IS NULL OR pm_bars = 0) "
        "AND (pm_volume IS NOT NULL OR pm_high IS NOT NULL) "
        "ORDER BY snapshot_id DESC"
    )

    try:
        rows = cur.execute(sql, (SCAN_DATE,)).fetchall()
    except sqlite3.OperationalError as e:
        print("  ERROR: " + str(e))
        print("=" * 74)
        result["status"] = "ERROR"
        result["error"] = str(e)
        write_json("data/pm_integrity.json", result)
        return result

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
            print(
                "  [snap_id=" + str(r[0]) + "] " + str(r[1]) +
                " | bars=" + str(r[3]) +
                " vol=" + str(r[4]) +
                " high=" + str(r[6]) +
                " src=" + str(r[9])
            )
        print("  NOTE: EVIDENCE ONLY. Investigate root cause.")
    else:
        print("  PASS: No violations for " + SCAN_DATE)

    print("=" * 74)
    write_json("data/pm_integrity.json", result)
    return result


# ---------------------------------------------------------------------------
# stale data check
# ---------------------------------------------------------------------------

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

    if not _table_exists(cur, "snapshots"):
        print("  SKIP: snapshots table not found")
        print("=" * 74)
        write_json("data/stale_data.json", result)
        return result

    snap_cols = _cols(cur, "snapshots")

    # latest 5 scan dates
    try:
        rows = cur.execute(
            "SELECT scan_date, COUNT(*), "
            "MIN(snapshot_time_et), MAX(snapshot_time_et) "
            "FROM snapshots GROUP BY scan_date "
            "ORDER BY scan_date DESC LIMIT 5"
        ).fetchall()
        for r in rows:
            print(
                "  " + str(r[0]) + " | n=" + str(r[1]) +
                " | " + str(r[2]) + " -> " + str(r[3])
            )
    except sqlite3.OperationalError as e:
        print("  WARN: " + str(e))

    print()

    # duplicate price/prev_close across days
    if {"ticker", "price", "prev_close"} <= snap_cols:
        try:
            dupes = cur.execute(
                "SELECT ticker, price, prev_close, "
                "GROUP_CONCAT(scan_date, ', '), COUNT(DISTINCT scan_date) "
                "FROM snapshots "
                "WHERE scan_date >= date('now', '-5 days') "
                "GROUP BY ticker, price, prev_close "
                "HAVING COUNT(DISTINCT scan_date) > 1 "
                "ORDER BY COUNT(DISTINCT scan_date) DESC LIMIT 10"
            ).fetchall()

            if dupes:
                result["status"] = "WARN"
                print("  WARN: " + str(len(dupes)) + " stale-data suspect(s):")
                for d in dupes:
                    print(
                        "  " + str(d[0]) + " | price=" + str(d[1]) +
                        " | prev=" + str(d[2]) +
                        " | days=" + str(d[4])
                    )
                    result["suspects"].append({
                        "ticker": d[0], "price": d[1], "prev_close": d[2],
                        "n_days": d[4], "scan_dates": d[3],
                    })
            else:
                print("  OK: No stale-data suspects")
        except sqlite3.OperationalError as e:
            print("  WARN: " + str(e))
    else:
        print("  SKIP: ticker/price/prev_close columns missing")

    print("=" * 74)
    write_json("data/stale_data.json", result)
    return result


# ---------------------------------------------------------------------------
# separated counters
# ---------------------------------------------------------------------------

def print_counters(cur):
    snap_cols = _cols(cur, "snapshots")
    trig_cols = _cols(cur, "trigger_results")
    outc_cols = _cols(cur, "outcomes")

    n_snapshots = _count(
        cur,
        "SELECT COUNT(*) FROM snapshots WHERE scan_date = ?",
        (SCAN_DATE,),
    )

    # --- PM ---
    if "pm_bars" in snap_cols:
        n_pm_ok = _count(
            cur,
            "SELECT COUNT(*) FROM snapshots WHERE scan_date = ? AND pm_bars > 0",
            (SCAN_DATE,),
        )
        n_pm_zero = (
            n_snapshots - n_pm_ok
            if (n_snapshots is not None and n_pm_ok is not None)
            else None
        )
    else:
        n_pm_ok = None
        n_pm_zero = None

    if "pm_volume" in snap_cols:
        n_pm_vol = _count(
            cur,
            "SELECT COUNT(*) FROM snapshots "
            "WHERE scan_date = ? AND pm_volume IS NOT NULL AND pm_volume > 0",
            (SCAN_DATE,),
        )
    else:
        n_pm_vol = None

    # --- Gates ---
    # 'float' is quoted because it can be a type name; SQLite tolerates quotes.
    if "float" in snap_cols:
        n_float_pass = _count(
            cur,
            'SELECT COUNT(*) FROM snapshots '
            'WHERE scan_date = ? AND "float" IS NOT NULL AND "float" <= 20000000',
            (SCAN_DATE,),
        )
    else:
        n_float_pass = None

    # Float gate: try multiple candidate names
    n_liq_pass = None
    for cand in ("float_gate_passed", "passes_float_gate",
                 "float_gate", "float_gate_pass"):
        if cand in snap_cols:
            n_liq_pass = _count(
                cur,
                'SELECT COUNT(*) FROM snapshots '
                'WHERE scan_date = ? AND "' + cand + '" = 1',
                (SCAN_DATE,),
            )
            break
    if n_liq_pass is None and n_float_pass is not None:
        print("  NOTE: no float-gate column found - using float<=20M as proxy")
        n_liq_pass = n_float_pass

    if "composite_score" in snap_cols:
        n_scored = _count(
            cur,
            "SELECT COUNT(*) FROM snapshots "
            "WHERE scan_date = ? AND composite_score IS NOT NULL",
            (SCAN_DATE,),
        )
    else:
        n_scored = None

    # --- Triggers ---
    if _table_exists(cur, "trigger_results") and "snapshot_id" in trig_cols:
        n_triggers = _count(
            cur,
            "SELECT COUNT(*) FROM trigger_results "
            "WHERE snapshot_id IN "
            "(SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
            (SCAN_DATE,),
        )
        if "hit" in trig_cols:
            n_hits = _count(
                cur,
                "SELECT COUNT(*) FROM trigger_results WHERE hit = 1 "
                "AND snapshot_id IN "
                "(SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
                (SCAN_DATE,),
            )
        else:
            n_hits = None
    else:
        n_triggers = None
        n_hits = None

    # --- Outcomes ---
    if _table_exists(cur, "outcomes") and "snapshot_id" in outc_cols:
        n_outcomes = _count(
            cur,
            "SELECT COUNT(*) FROM outcomes "
            "WHERE snapshot_id IN "
            "(SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
            (SCAN_DATE,),
        )
        if "net_r_status" in outc_cols:
            n_valid = _count(
                cur,
                "SELECT COUNT(*) FROM outcomes WHERE net_r_status = 'VALID' "
                "AND snapshot_id IN "
                "(SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
                (SCAN_DATE,),
            )
            n_nonexec = _count(
                cur,
                "SELECT COUNT(*) FROM outcomes "
                "WHERE net_r_status = 'NON_EXECUTABLE' "
                "AND snapshot_id IN "
                "(SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
                (SCAN_DATE,),
            )
        else:
            n_valid = None
            n_nonexec = None
    else:
        n_outcomes = None
        n_valid = None
        n_nonexec = None

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
    print("  Snapshots (raw):          " + _fmt(n_snapshots))
    print()
    print("  -- Stage 2: PM Data --")
    print("  PM bars > 0:              " + _fmt(n_pm_ok))
    print("  PM bars = 0:              " + _fmt(n_pm_zero))
    print("  PM volume > 0:            " + _fmt(n_pm_vol))
    print()
    print("  -- Stage 3: Gates --")
    print("  Float <= 20M:             " + _fmt(n_float_pass))
    print("  Float Gate PASS:          " + _fmt(n_liq_pass))
    print("  Scored (composite):       " + _fmt(n_scored))
    print()
    print("  -- Stage 4: Triggers --")
    print("  Triggers total:           " + _fmt(n_triggers))
    print("  Trigger hits:             " + _fmt(n_hits))
    print()
    print("  -- Stage 5: Outcomes --")
    print("  Outcomes total:           " + _fmt(n_outcomes))
    print("  Outcomes VALID:           " + _fmt(n_valid))
    print("  Outcomes NON_EXECUTABLE:  " + _fmt(n_nonexec))
    print("=" * 74)

    # Also write JSON for archival
    write_json("data/counters.json", {
        "scan_date": SCAN_DATE,
        "event": EVENT,
        "run_number": RUN_NUMBER,
        "git_sha": GIT_SHA,
        "snapshots": n_snapshots,
        "pm_bars_ok": n_pm_ok,
        "pm_bars_zero": n_pm_zero,
        "pm_volume_positive": n_pm_vol,
        "float_le_20m": n_float_pass,
        "float_gate_pass": n_liq_pass,
        "scored": n_scored,
        "triggers_total": n_triggers,
        "trigger_hits": n_hits,
        "outcomes_total": n_outcomes,
        "outcomes_valid": n_valid,
        "outcomes_nonexec": n_nonexec,
    })


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    if not os.path.exists(DB_PATH):
        print("DB not found at " + DB_PATH)
        return 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1) schema (always useful)
    try:
        dump_schema(cur)
    except Exception as e:
        print("  ERROR in dump_schema: " + str(e))

    # 2) PM integrity
    try:
        check_pm_integrity(cur)
    except Exception as e:
        print("  ERROR in check_pm_integrity: " + str(e))

    # 3) stale data
    try:
        check_stale_data(cur)
    except Exception as e:
        print("  ERROR in check_stale_data: " + str(e))

    # 4) counters
    try:
        print_counters(cur)
    except Exception as e:
        print("  ERROR in print_counters: " + str(e))

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())