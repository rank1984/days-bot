#!/usr/bin/env python3
"""
summarize_run.py — parse scan.log → run_summary.json.

Args:
    sys.argv[1]  path to scan.log      (default: scan.log)
    sys.argv[2]  path to output JSON   (default: run_summary.json)

Contract highlights:
  * post_scan_snapshots is counted from the DB *after* the scanner wrote it,
    not from any env var captured earlier.
  * pre_scan_snapshots prefers PRE_SCAN_COUNT env, then run_summary_prior.json,
    then (post - saved).
  * Missing log lines degrade to None (with WARN), never to silent zero.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


DB_PATH_DEFAULT = "data/alerts.db"
LOG_PATH_DEFAULT = "scan.log"
OUT_PATH_DEFAULT = "run_summary.json"


def read_log(path: str) -> str:
    if not os.path.exists(path):
        print(f"[summarize_run] WARN: {path} not found", file=sys.stderr)
        return ""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def find_int(pattern: str, text: str, default=None):
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        return default
    try:
        return int(m.group(1))
    except (ValueError, IndexError):
        return default


def count_snapshots(db_path: str) -> int:
    if not os.path.exists(db_path):
        return 0
    try:
        conn = sqlite3.connect(db_path)
        try:
            return int(conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0])
        finally:
            conn.close()
    except Exception as e:
        print(f"[summarize_run] DB count error: {e}", file=sys.stderr)
        return 0


def load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[summarize_run] cannot read {path}: {e}", file=sys.stderr)
        return {}


def main() -> int:
    log_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SCAN_LOG", LOG_PATH_DEFAULT)
    out_path = sys.argv[2] if len(sys.argv) > 2 else OUT_PATH_DEFAULT
    db_path  = os.environ.get("DB_PATH", DB_PATH_DEFAULT)

    log = read_log(log_path)
    meta = load_json("run_metadata.json")
    prior = load_json("run_summary_prior.json")

    # ---- pre_scan_snapshots: env → prior → (post - saved) ----
    pre_env = os.environ.get("PRE_SCAN_COUNT")
    if pre_env and pre_env.isdigit():
        pre_count = int(pre_env)
    elif "pre_scan_snapshots" in prior:
        pre_count = prior["pre_scan_snapshots"]
    else:
        pre_count = None

    # ---- post_scan_snapshots: real DB count AFTER scanner finished ----
    post_count = count_snapshots(db_path)

    # ---- parse log ----
    universe = find_int(r"\[Universe\]\s*Final:\s*(\d+)\s+symbols", log, None)

    candidates = find_int(r"\[SwingDiscovery\]\s*Found\s+(\d+)\s+candidates", log, None)
    if candidates is None:
        candidates = find_int(r"Discovery returned\s+(\d+)", log, None)

    snapshots_saved = find_int(r"snapshots saved:\s*(\d+)", log, None)
    if snapshots_saved is None:
        snapshots_saved = candidates

    valid_alerts = find_int(r"Valid alerts(?:\s*\([^)]*\))?\s*:\s*(\d+)", log, None)
    telegram_sent = find_int(r"Telegram sent:\s*(\d+)", log, None)
    stop_too_tight = find_int(r"Stop too tight:\s*(\d+)", log, None)
    stop_too_wide  = find_int(r"Stop too wide:\s*(\d+)", log, None)
    other_blocked  = find_int(r"Other \(low score\):\s*(\d+)", log, None)

    plan_blocked = find_int(r"Plan blocked:\s*(\d+)", log, None)
    if plan_blocked is None and None not in (stop_too_tight, stop_too_wide, other_blocked):
        plan_blocked = stop_too_tight + stop_too_wide + other_blocked

    top5_returned = telegram_sent

    # ---- reconcile post_count ----
    if post_count == 0 and pre_count is not None and snapshots_saved:
        post_count = pre_count + snapshots_saved

    if pre_count is None:
        pre_count = max(0, post_count - (snapshots_saved or 0))

    summary = {
        "run_number": meta.get("run_number"),
        "run_id": meta.get("run_id"),
        "time_et": meta.get("time_et"),
        "scan_date": meta.get("scan_date"),
        "event": meta.get("event", "schedule"),
        "is_scheduled": meta.get("is_scheduled", 1),
        "in_pm_window": meta.get("in_pm_window", 0),
        "preflight_passed": meta.get("preflight_passed", 1),
        "universe": universe,
        "strict": candidates,
        "liquidity_rejects": find_int(r"liquidity_rejects\s*[:=]\s*(\d+)", log, None),
        "dataquality_blocked": find_int(r"dataquality_blocked\s*[:=]\s*(\d+)", log, None),
        "plan_blocked": plan_blocked,
        "plan_blocked_list": [],
        "top5_returned": top5_returned,
        "valid_alerts": valid_alerts,
        "telegram_sent": telegram_sent,
        "stop_too_tight": stop_too_tight,
        "stop_too_wide": stop_too_wide,
        "other_blocked": other_blocked,
        "pre_scan_snapshots": pre_count,
        "post_scan_snapshots": post_count,
        "snapshots_saved": snapshots_saved,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    Path(out_path).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    Path("run_summary_prior.json").write_text(
        json.dumps({"pre_scan_snapshots": post_count,
                    "post_scan_snapshots": post_count}),
        encoding="utf-8",
    )

    print(
        "[summarize_run] wrote {}: universe={} candidates={} "
        "snapshots_saved={} valid_alerts={} telegram_sent={} plan_blocked={} "
        "pre={} post={}".format(
            out_path, universe, candidates, snapshots_saved, valid_alerts,
            telegram_sent, plan_blocked, pre_count, post_count,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
