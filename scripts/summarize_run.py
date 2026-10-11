#!/usr/bin/env python3
"""
DAYS-BOT — Run Summary Extractor
---------------------------------
קורא לוג של ריצת סורק אחת (scan.log) ומייצר run_summary.json
עם 16 השדות המרכזיים שרוצים לראות בכל ריצה.

Usage:
    python3 scripts/summarize_run.py scan.log [run_summary.json]

Default output: run_summary.json (בתיקייה הנוכחית).
"""
import re
import json
import sys
import os
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load(path: str) -> str:
    """קורא קובץ טקסט בבטחה."""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def find(pat: str, text: str, default=None, cast=str):
    """מחזיר את group(1) של ההתאמה הראשונה, או default אם אין."""
    m = re.search(pat, text, re.MULTILINE)
    if not m:
        return default
    val = m.group(1).strip()
    try:
        return cast(val)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract(log: str) -> dict:
    # --- PLAN_BLOCKED entries ---
    # דוגמה: "[FullScan] PLAN_BLOCKED AIXI | reason=MISSING_PM_VWAP ..."
    plan_blocked_pairs = re.findall(
        r"PLAN_BLOCKED\s+([A-Z0-9\.\-]+)\s*\|\s*reason=([A-Z_]+)",
        log,
    )
    plan_blocked_list = [f"{t} ({r})" for t, r in plan_blocked_pairs]

    # --- Pre/Post snapshots ---
    # Pre-scan DB state:
    #   snapshots:       23
    pre = find(r"Pre-scan DB state:\s*\n\s*snapshots:\s*(\d+)", log, 0, int)
    saved = find(r"V5\.0\.6 snapshots saved:\s*(\d+)", log, 0, int)

    summary = {
        # זיהוי הריצה
        "run_number":          find(r"Run:\s+\d+\s+\(#(\d+)\)", log, cast=int),
        "run_id":              find(r"Run:\s+(\d+)\s+\(#\d+\)", log),
        "time_et":             find(r"ET:\s+\d{4}-\d{2}-\d{2}\s+(\d{2}:\d{2})", log),
        "scan_date":           find(r"Scan date:\s+(\d{4}-\d{2}-\d{2})", log),
        "event":               find(r"Event:\s+(\w+)", log),

        # דגלי context
        "is_scheduled":        find(r"IS_SCHEDULED:\s+(\d)", log, 0, int),
        "in_pm_window":        find(r"IN_PM_WINDOW:\s+(\d)", log, 0, int),
        "preflight_passed":    find(r"PREFLIGHT_PASSED:\s+(\d)", log, 0, int),

        # שלבי Discovery
        "universe":            find(r"Final:\s+(\d+)\s+symbols", log, cast=int),
        "strict":              find(r"Discovery returned\s+(\d+)\s+candidates", log, 0, int),

        # שלבי FullScan / Gates
        "liquidity_rejects":   find(r"Liquidity rejects:\s+(\d+)", log, 0, int),
        "dataquality_blocked": find(r"DataQuality blocked:\s+(\d+)", log, 0, int),
        "plan_blocked":        len(plan_blocked_pairs),
        "plan_blocked_list":   plan_blocked_list,
        "top5_returned":       find(r"Top 5 returned:\s+(\d+)", log, 0, int),

        # גדילת ה-chain
        "pre_scan_snapshots":  pre,
        "post_scan_snapshots": pre + saved,

        # מטא
        "generated_at_utc":    datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("usage: summarize_run.py <log_file> [output.json]", file=sys.stderr)
        sys.exit(2)

    log_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "run_summary.json"

    if not os.path.exists(log_path):
        print(f"log file not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    summary = extract(load(log_path))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # גם stdout, כדי לראות ב-Actions log
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
