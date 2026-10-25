#!/usr/bin/env python3
"""
write_run_metadata.py — write run_metadata.json at scan start.

Reads:   GITHUB_*, PREFLIGHT_PASSED, SCAN_DATE, TIME_ET, IS_SCHEDULED,
         IN_PM_WINDOW, PRE_SCAN_COUNT
Writes:  run_metadata.json  (cwd)         — consumed by summarize_run.py
         data/run_metadata.json (copy)    — kept alongside DB in the artifact
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytz


ET = pytz.timezone("America/New_York")
IL = pytz.timezone("Asia/Jerusalem")


def _int_or_none(val):
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _str(val, default=""):
    return val if val is not None and val != "" else default


def main() -> int:
    now_utc = datetime.now(pytz.UTC)
    now_et = now_utc.astimezone(ET)
    now_il = now_utc.astimezone(IL)

    event = _str(os.environ.get("GITHUB_EVENT_NAME"), "unknown")
    scan_date = _str(os.environ.get("SCAN_DATE")) or now_et.strftime("%Y-%m-%d")
    time_et = _str(os.environ.get("TIME_ET")) or now_et.strftime("%H:%M")

    is_sched_env = os.environ.get("IS_SCHEDULED")
    is_scheduled = (int(is_sched_env) if is_sched_env and is_sched_env.isdigit()
                    else (1 if event == "schedule" else 0))

    pm_env = os.environ.get("IN_PM_WINDOW")
    in_pm_window = int(pm_env) if pm_env and pm_env.isdigit() else 0

    pf_env = os.environ.get("PREFLIGHT_PASSED")
    preflight_passed = int(pf_env) if pf_env and pf_env.isdigit() else 0

    meta = {
        "run_number": _int_or_none(os.environ.get("GITHUB_RUN_NUMBER")),
        "run_id": _str(os.environ.get("GITHUB_RUN_ID")),
        "time_et": time_et,
        "scan_date": scan_date,
        "event": event,
        "is_scheduled": is_scheduled,
        "in_pm_window": in_pm_window,
        "preflight_passed": preflight_passed,
        "pre_scan_snapshots": _int_or_none(os.environ.get("PRE_SCAN_COUNT")),
        "generated_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),

        "workflow": _str(os.environ.get("GITHUB_WORKFLOW")),
        "git_sha": _str(os.environ.get("GITHUB_SHA")),
        "branch": _str(os.environ.get("GITHUB_REF_NAME")),
        "repository": _str(os.environ.get("GITHUB_REPOSITORY")),
        "started_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "started_at_et": now_et.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "started_at_il": now_il.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    payload = json.dumps(meta, indent=2, ensure_ascii=False)
    Path("run_metadata.json").write_text(payload, encoding="utf-8")

    try:
        os.makedirs("data", exist_ok=True)
        Path("data/run_metadata.json").write_text(payload, encoding="utf-8")
    except OSError as e:
        print(f"[write_run_metadata] WARN: cannot write data/: {e}", file=sys.stderr)

    print("=== run_metadata.json ===")
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
