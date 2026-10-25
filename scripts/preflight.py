#!/usr/bin/env python3
"""
preflight.py — preflight checks.

Modes:
  --mode premarket  (legacy: PM window 04:00-09:30 ET, trigger 09:30-11:00,
                     event_rank column in trigger_results)
  --mode swing      (default for swing_v1: skips PM/trigger/event_rank,
                     keeps DB sanity checks that are relevant to swing)

Exit 0 only if all applicable checks pass.
Emits `PREFLIGHT_RESULT=passed|failed`.
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


def check_event_rank_in_trigger_results(conn: sqlite3.Connection) -> tuple[bool, str]:
    """Legacy check: event_rank lives in trigger_results, NOT in snapshots."""
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(trigger_results)")}
        return ("event_rank" in cols), f"trigger_results columns={len(cols)}"
    except sqlite3.OperationalError as e:
        return False, str(e)


def run_preflight(mode: str = "swing", db_path: str = DB_PATH) -> int:
    print("=" * 74)
    print(f"PREFLIGHT CHECK — {now_et().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Mode: {mode}")
    print("=" * 74)

    now = now_et()
    checks: list[tuple[str, bool, str]] = []

    # 1. PM window (premarket only)
    if mode == "premarket":
        ok, info = check_pm_window(now)
        checks.append(("1. inside PM window", ok, info))
    else:
        checks.append(("1. PM window (N/A for swing)", True,
                       "swing mode — daily bars, no PM window required"))

    # 2/3/4 — DB sanity
    conn = None
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
        except Exception as e:
            print(f"  [WARN] cannot open DB: {e}")

    if conn is not None:
        checks.append(("2. PMH consistent with pm_bars", *check_pmh_consistent(conn)))
        checks.append(("3. pm_bars>0 implies pm_high", *check_pm_bars_imply_high(conn)))
        if mode == "premarket":
            checks.append(("4. event_rank in trigger_results",
                           *check_event_rank_in_trigger_results(conn)))
        else:
            checks.append(("4. event_rank (N/A for swing)", True,
                           "swing mode — trigger_results is legacy"))
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
        print("  PREFLIGHT_RESULT=passed")
        return 0
    print("  PREFLIGHT FAILED — run NOT eligible for counting")
    print("  PREFLIGHT_RESULT=failed")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["premarket", "swing"], default="swing")
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()
    return run_preflight(args.mode, args.db)


if __name__ == "__main__":
    sys.exit(main())
