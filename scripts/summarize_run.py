#!/usr/bin/env python3
"""
DAYS-BOT — Run Summary Extractor (v4)
-------------------------------------
תומך בשני המנועים: fullscan_v34 (Pre-Market) ו-swing_v1 (Swing).
מייצר run_summary.json עם כל השדות משני הפורמטים.
"""
import re
import json
import sys
import os
from datetime import datetime, timezone


def load(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def find(pat: str, text: str, default=None, cast=str):
    m = re.search(pat, text, re.MULTILINE)
    if not m:
        return default
    try:
        return cast(m.group(1).strip())
    except (ValueError, TypeError):
        return default


def first_not_none(*values):
    for v in values:
        if v is not None and v != "":
            return v
    return None


def _env_int(name: str, default: int = 0) -> int:
    raw = os.environ.get(name, "")
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except (ValueError, TypeError):
        return default


def extract(log: str) -> dict:
    env = os.environ

    # ---------- Pre-Market patterns (fullscan_v34) ----------
    plan_blocked_pairs = re.findall(
        r"PLAN_BLOCKED\s+([A-Z0-9\.\-]+)\s*\|\s*reason=([A-Z_]+)",
        log,
    )
    pre_strict = find(r"Discovery returned\s+(\d+)\s+candidates", log, None, int)

    # ---------- Swing patterns (swing_v1) ----------
    swing_candidates = find(r"\[SwingDiscovery\] Found\s+(\d+)\s+candidates", log, None, int)
    swing_valid_alerts = find(r"Valid alerts:\s+(\d+)", log, 0, int)
    swing_plan_blocked = find(r"Plan blocked:\s+(\d+)", log, 0, int)
    swing_telegram_sent = find(r"Telegram sent:\s+(\d+)", log, 0, int)
    swing_stop_tight = find(r"Stop too tight:\s+(\d+)", log, 0, int)
    swing_stop_wide = find(r"Stop too wide:\s+(\d+)", log, 0, int)
    swing_other_blocked = find(r"Other \(low score\):\s+(\d+)", log, 0, int)

    # ---------- Pre/Post snapshots ----------
    pre = find(r"Pre-scan DB state:.*?\n\s*snapshots:\s*(\d+)", log, None, int)
    if pre is None:
        pre = find(r"^\s*snapshots:\s*(\d+)", log, 0, int)
    saved = find(r"V5\.0\.6 snapshots saved:\s*(\d+)", log, 0, int)

    # ---------- שדות מזוהים ----------
    run_number = first_not_none(
        find(r"Run:\s+\d+\s+\(#(\d+)\)", log, cast=int),
        env.get("RUN_NUMBER"),
    )
    if run_number is not None:
        try:
            run_number = int(run_number)
        except (ValueError, TypeError):
            pass

    run_id = first_not_none(
        find(r"Run:\s+(\d+)\s+\(#\d+\)", log),
        env.get("RUN_ID"),
    )

    time_et = first_not_none(
        find(r"ET:\s+\d{4}-\d{2}-\d{2}\s+(\d{2}:\d{2})", log),
        env.get("TIME_ET"),
    )

    scan_date = first_not_none(
        find(r"Scan date:\s+(\d{4}-\d{2}-\d{2})", log),
        env.get("SCAN_DATE"),
    )

    event = first_not_none(
        find(r"Event:\s+(\w+)", log),
        env.get("EVENT"),
    )

    # ---------- שלושת השדות הרגישים ----------
    is_scheduled = find(r"IS_SCHEDULED:\s+(\d)", log, _env_int("IS_SCHEDULED", 0), int)
    in_pm_window = find(r"IN_PM_WINDOW:\s+(\d)", log, _env_int("IN_PM_WINDOW", 0), int)
    preflight_passed = find(r"PREFLIGHT_PASSED:\s+(\d)", log, _env_int("PREFLIGHT_PASSED", 0), int)

    # ---------- שילוב: strict + plan_blocked ----------
    strict = pre_strict if pre_strict is not None else (swing_candidates or 0)
    plan_blocked = len(plan_blocked_pairs)
    if plan_blocked == 0:
        plan_blocked = swing_plan_blocked

    summary = {
        # זיהוי הריצה
        "run_number":          run_number,
        "run_id":              run_id,
        "time_et":             time_et,
        "scan_date":           scan_date,
        "event":               event,

        # דגלי context
        "is_scheduled":        is_scheduled,
        "in_pm_window":        in_pm_window,
        "preflight_passed":    preflight_passed,

        # שלבי Discovery
        "universe":            find(r"Final:\s+(\d+)\s+symbols", log, cast=int),
        "strict":              strict,

        # שלבי FullScan / Gates
        "liquidity_rejects":   find(r"Liquidity rejects:\s+(\d+)", log, 0, int),
        "dataquality_blocked": find(r"DataQuality blocked:\s+(\d+)", log, 0, int),
        "plan_blocked":        plan_blocked,
        "plan_blocked_list":   [f"{t} ({r})" for t, r in plan_blocked_pairs],
        "top5_returned":       find(r"Top 5 returned:\s+(\d+)", log, 0, int),

        # Swing-specific
        "valid_alerts":        swing_valid_alerts,
        "telegram_sent":       swing_telegram_sent,
        "stop_too_tight":      swing_stop_tight,
        "stop_too_wide":       swing_stop_wide,
        "other_blocked":       swing_other_blocked,

        # גדילת ה-chain
        "pre_scan_snapshots":  pre,
        "post_scan_snapshots": pre + saved,
        "snapshots_saved":     saved,

        # מטא
        "generated_at_utc":    datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return summary


def main():
    if len(sys.argv) < 2:
        print("usage: summarize_run.py <log_file> [output.json]", file=sys.stderr)
        sys.exit(2)

    log_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "run_summary.json"

    summary = extract(load(log_path))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
