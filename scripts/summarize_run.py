#!/usr/bin/env python3
"""
summarize_run.py — parse scan.log → run_summary.json (V5.0.8+)

Fixes vs previous version:
  * valid_alerts regex now matches "Valid alerts (saved): N" AND "Valid alerts: N"
  * snapshots_saved regex matches "V5.0.8 snapshots saved: N" and "snapshots saved: N"
  * pre/post snapshot counts read from DB *after* scan (no more 1234/1234 bug)
  * PRE_SCAN_COUNT env honored if set by the workflow
  * top5_returned populated from telegram_sent in swing mode
  * robust fallbacks if any log line is missing
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


# ---------- helpers ----------

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
            cur = conn.execute("SELECT COUNT(*) FROM snapshots")
            return int(cur.fetchone()[0])
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


# ---------- main ----------

def main() -> int:
    log_path = os.environ.get("SCAN_LOG", LOG_PATH_DEFAULT)
    db_path = os.environ.get("DB_PATH", DB_PATH_DEFAULT)
    log = read_log(log_path)

    meta = load_json("run_metadata.json")
    prior = load_json("run_summary_prior.json")

    # Pre-scan snapshot count: prefer env (set by workflow), then prior summary,
    # then metadata, then "current - saved".
    pre_count_env = os.environ.get("PRE_SCAN_COUNT")
    pre_count = None
    if pre_count_env and pre_count_env.isdigit():
        pre_count = int(pre_count_env)
    elif "pre_scan_snapshots" in prior:
        pre_count = prior["pre_scan_snapshots"]
    elif "pre_scan_snapshots" in meta:
        pre_count = meta["pre_scan_snapshots"]

    # Post-scan snapshot count: read *now* from DB (after the scanner finished).
    post_count = count_snapshots(db_path)

    # --- parse log lines ---
    universe = find_int(r"\[Universe\]\s*Final:\s*(\d+)\s+symbols", log, 0)

    candidates = find_int(r"\[SwingDiscovery\]\s*Found\s+(\d+)\s+candidates", log, 0)
    if candidates == 0:
        candidates = find_int(r"Discovery returned\s+(\d+)", log, 0)

    snapshots_saved = find_int(r"snapshots saved:\s*(\d+)", log, 0)
    if snapshots_saved == 0:
        # Try the legacy header "Discovery returned N" pattern as fallback
        snapshots_saved = candidates

    # Important: matches "Valid alerts (saved):   45" AND "Valid alerts:   0"
    valid_alerts = find_int(
        r"Valid alerts(?:\s*\([^)]*\))?\s*:\s*(\d+)",
        log, 0,
    )

    telegram_sent = find_int(r"Telegram sent:\s*(\d+)", log, 0)
    stop_too_tight = find_int(r"Stop too tight:\s*(\d+)", log, 0)
    stop_too_wide  = find_int(r"Stop too wide:\s*(\d+)", log, 0)
    other_blocked  = find_int(r"Other \(low score\):\s*(\d+)", log, 0)

    plan_blocked = find_int(r"Plan blocked:\s*(\d+)", log, 0)
    if plan_blocked == 0:
        plan_blocked = stop_too_tight + stop_too_wide + other_blocked

    # In swing mode, "top5_returned" is a legacy pre-market field.
    # We define it as the number of actionable alerts sent to Telegram.
    top5_returned = telegram_sent

    # --- post_scan count: if DB not present, derive from pre + saved ---
    if post_count == 0 and pre_count is not None and snapshots_saved:
        post_count = pre_count + snapshots_saved

    if pre_count is None:
        pre_count = max(0, post_count - snapshots_saved)

    # --- assemble summary ---
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
        "liquidity_rejects": find_int(r"liquidity_rejects\s*[:=]\s*(\d+)", log, 0),
        "dataquality_blocked": find_int(r"dataquality_blocked\s*[:=]\s*(\d+)", log, 0),
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

    Path("run_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Persist for next run (so next run knows pre_scan_snapshots).
    Path("run_summary_prior.json").write_text(
        json.dumps({"pre_scan_snapshots": post_count,
                    "post_scan_snapshots": post_count}),
        encoding="utf-8",
    )

    print(
        "[summarize_run] wrote run_summary.json: "
        f"universe={universe} candidates={candidates} "
        f"snapshots_saved={snapshots_saved} valid_alerts={valid_alerts} "
        f"telegram_sent={telegram_sent} plan_blocked={plan_blocked} "
        f"pre={pre_count} post={post_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
