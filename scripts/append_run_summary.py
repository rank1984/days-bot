#!/usr/bin/env python3
"""
DAYS-BOT — Append run_summary.json into all_runs.csv
----------------------------------------------------
מוסיף (או מחליף) את השורה של הריצה הנוכחית בקובץ all_runs.csv.
אידמפוטנטי: אם run_number כבר קיים, השורה שלו מוחלפת ולא משוכפלת.

Usage:
    python3 scripts/append_run_summary.py run_summary.json all_runs.csv

הקובץ all_runs.csv נוצר אוטומטית עם header אם אינו קיים.
"""
import csv
import json
import os
import sys


# סדר העמודות ב-CSV — זהה לסדר ב-run_summary.json
FIELDS = [
    "run_number",
    "run_id",
    "time_et",
    "scan_date",
    "event",
    "is_scheduled",
    "in_pm_window",
    "preflight_passed",
    "universe",
    "strict",
    "liquidity_rejects",
    "dataquality_blocked",
    "plan_blocked",
    "plan_blocked_list",
    "top5_returned",
    "pre_scan_snapshots",
    "post_scan_snapshots",
    "generated_at_utc",
]


def load_rows(csv_path: str):
    """טוען שורות מ-CSV קיים, או מחזיר רשימה ריקה."""
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sort_key(row: dict):
    """מיון לפי run_number כמספר; None/ריק -> 0."""
    try:
        return int(row.get("run_number") or 0)
    except (ValueError, TypeError):
        return 0


def main():
    if len(sys.argv) < 3:
        print(
            "usage: append_run_summary.py <run_summary.json> <all_runs.csv>",
            file=sys.stderr,
        )
        sys.exit(2)

    json_path = sys.argv[1]
    csv_path = sys.argv[2]

    if not os.path.exists(json_path):
        print(f"missing input: {json_path}", file=sys.stderr)
        sys.exit(1)

    # --- קרא את ה-JSON של הריצה הנוכחית ---
    with open(json_path, encoding="utf-8") as f:
        new = json.load(f)

    # plan_blocked_list הוא list -> הופך למחרוזת עם "; " כמפריד
    if isinstance(new.get("plan_blocked_list"), list):
        new["plan_blocked_list"] = "; ".join(new["plan_blocked_list"])
    elif new.get("plan_blocked_list") is None:
        new["plan_blocked_list"] = ""

    # --- בנה שורה עם סדר עמודות קבוע ---
    row = {k: new.get(k, "") for k in FIELDS}

    # --- טען קיים, החלף לפי run_number, מיין, שמור ---
    rows = load_rows(csv_path)
    rows = [
        r for r in rows
        if str(r.get("run_number")) != str(row["run_number"])
    ]
    rows.append(row)
    rows.sort(key=sort_key)

    # --- וודא שתיקיית היעד קיימת ---
    out_dir = os.path.dirname(csv_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # --- כתוב חזרה ---
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"all_runs.csv updated: {len(rows)} rows "
        f"(run #{row['run_number']}) -> {csv_path}"
    )


if __name__ == "__main__":
    main()
