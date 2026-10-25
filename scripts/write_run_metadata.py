#!/usr/bin/env python3
"""
write_run_metadata.py — write run_metadata.json at scan start.

Reads:   env vars set by the workflow (GITHUB_*, PREFLIGHT_PASSED,
         SCAN_DATE, TIME_ET, IS_SCHEDULED, IN_PM_WINDOW, PRE_SCAN_COUNT)
Writes:  run_metadata.json  (cwd)      -> consumed by summarize_run.py
         data/run_metadata.json (copy) -> kept alongside DB for traceability

Contract with summarize_run.py:
    run_number        int | str
    run_id            str
    time_et           "HH:MM"
    scan_date         "YYYY-MM-DD"
    event             "schedule" | "workflow_dispatch" | "push" | ...
    is_scheduled      0 | 1
    in_pm_window      0 | 1          (always 0 in swing mode; kept for CSV compat)
    preflight_passed  0 | 1
    generated_at_utc  ISO-8601
    pre_scan_snapshots int | null     (informational; summarize re-reads env)

All other fields are extra breadcrumbs for debugging and are ignored by the
summarizer.
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


def _int_or_none(val: str | None):
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _str(val: str | None, default: str = "") -> str:
    return val if val is not None and val != "" else default


def main() -> int:
    now_utc = datetime.now(pytz.UTC)
    now_et = now_utc.astimezone(ET)
    now_il = now_utc.astimezone(IL)

    # ---- primary fields consumed by summarize_run.py ----
    run_number = _int_or_none(os.environ.get("GITHUB_RUN_NUMBER"))
    run_id = _str(os.environ.get("GITHUB_RUN_ID"))
    event = _str(os.environ.get("GITHUB_EVENT_NAME"), "unknown")

    # Prefer explicit env (set by workflow) over wall-clock; keeps summarize
    # deterministic even if the step runs slightly after the scanner.
    scan_date = _str(os.environ.get("SCAN_DATE")) or now_et.strftime("%Y-%m-%d")
    time_et = _str(os.environ.get("TIME_ET")) or now_et.strftime("%H:%M")

    is_scheduled_env = os.environ.get("IS_SCHEDULED")
    if is_scheduled_env is not None:
        is_scheduled = int(is_scheduled_env) if is_scheduled_env.strip() else 0
    else:
        is_scheduled = 1 if event == "schedule" else 0

    in_pm_window_env = os.environ.get("IN_PM_WINDOW")
    in_pm_window = (
        int(in_pm_window_env)
        if in_pm_window_env is not None and in_pm_window_env.strip().isdigit()
        else 0
    )

    preflight_env = os.environ.get("PREFLIGHT_PASSED")
    preflight_passed = (
        int(preflight_env)
        if preflight_env is not None and preflight_env.strip().isdigit()
        else 0
    )

    pre_scan_snapshots = _int_or_none(os.environ.get("PRE_SCAN_COUNT"))

    # ---- extra breadcrumbs (ignored by summarizer) ----
    meta = {
        # -- contract with summarize_run.py --
        "run_number": run_number,
        "run_id": run_id,
        "time_et": time_et,
        "scan_date": scan_date,
        "event": event,
        "is_scheduled": is_scheduled,
        "in_pm_window": in_pm_window,
        "preflight_passed": preflight_passed,
        "pre_scan_snapshots": pre_scan_snapshots,
        "generated_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),

        # -- debugging breadcrumbs --
        "workflow": _str(os.environ.get("GITHUB_WORKFLOW")),
        "git_sha": _str(os.environ.get("GITHUB_SHA")),
        "branch": _str(os.environ.get("GITHUB_REF_NAME")),
        "repository": _str(os.environ.get("GITHUB_REPOSITORY")),
        "started_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "started_at_et": now_et.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "started_at_il": now_il.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    payload = json.dumps(meta, indent=2, ensure_ascii=False)

    # Primary location: cwd (summarize_run.py reads here first)
    Path("run_metadata.json").write_text(payload, encoding="utf-8")

    # Secondary copy: data/ (kept alongside alerts.db in the artifact)
    try:
        os.makedirs("data", exist_ok=True)
        Path("data/run_metadata.json").write_text(payload, encoding="utf-8")
    except OSError as e:
        print(f"[write_run_metadata] WARN: cannot write data/run_metadata.json: {e}",
              file=sys.stderr)

    print("=== run_metadata.json ===")
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
