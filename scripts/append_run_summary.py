#!/usr/bin/env python3
"""
DAYS-BOT — Append run_summary.json into all_runs.csv (v3)
תומך בשדות Swing חדשים.
"""
import csv
import json
import os
import sys


FIELDS = [
    "run_number", "run_id", "time_et", "scan_date", "event",
    "is_scheduled", "in_pm_window", "preflight_passed",
    "universe", "strict",
    "liquidity_rejects", "dataquality_blocked", "plan_blocked",
    "top5_returned",
    # Swing-specific
    "valid_alerts", "telegram_sent",
    "stop_too_tight", "stop_too_wide", "other_blocked",
    # Chain
    "pre_scan_snapshots", "post_scan_snapshots", "snapshots_saved",
    # Meta
    "generated_at_utc",
]


def load_rows(csv_path: str):
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sort_key(row):
    try:
        return int(row.get("run_number") or 0)
    except (ValueError, TypeError):
        return 0


def main():
    if len(sys.argv) < 3:
        print("usage: append_run_summary.py <run_summary.json> <all_runs.csv>", file=sys.stderr)
        sys.exit(2)

    json_path, csv_path = sys.argv[1], sys.argv[2]

    if not os.path.exists(json_path):
        print(f"missing input: {json_path}", file=sys.stderr)
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        new = json.load(f)

    if not new.get("run_number"):
        print("run_summary.json has no run_number — skipping write", file=sys.stderr)
        sys.exit(0)

    # plan_blocked_list -> string
    if isinstance(new.get("plan_blocked_list"), list):
        new["plan_blocked_list"] = "; ".join(new["plan_blocked_list"])
    elif new.get("plan_blocked_list") is None:
        new["plan_blocked_list"] = ""

    row = {k: (new.get(k) if new.get(k) is not None else "") for k in FIELDS}

    rows = load_rows(csv_path)

    # הסרת שורות ריקות
    rows = [r for r in rows if str(r.get("run_number") or "").strip() not in ("", "0")]

    # החלפה לפי run_number
    rows = [r for r in rows if str(r.get("run_number")) != str(row["run_number"])]
    rows.append(row)
    rows.sort(key=sort_key)

    out_dir = os.path.dirname(csv_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"all_runs.csv updated: {len(rows)} rows (run #{row['run_number']}) -> {csv_path}")


if __name__ == "__main__":
    main()
