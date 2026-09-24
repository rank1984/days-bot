#!/usr/bin/env python3
"""DAYS-BOT V5.0.6 - Write run_metadata.json at scan start."""
import json
import os
from datetime import datetime
import pytz

ET = pytz.timezone("America/New_York")
IL = pytz.timezone("Asia/Jerusalem")

now_utc = datetime.now(pytz.UTC)
now_et = now_utc.astimezone(ET)
now_il = now_utc.astimezone(IL)

meta = {
    "workflow_run_id": os.environ.get("GITHUB_RUN_ID", ""),
    "run_number": os.environ.get("GITHUB_RUN_NUMBER", ""),
    "event": os.environ.get("GITHUB_EVENT_NAME", ""),
    "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
    "git_sha": os.environ.get("GITHUB_SHA", ""),
    "branch": os.environ.get("GITHUB_REF_NAME", ""),
    "repository": os.environ.get("GITHUB_REPOSITORY", ""),
    "scan_date_et": now_et.strftime("%Y-%m-%d"),
    "started_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "started_at_et": now_et.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "started_at_il": now_il.strftime("%Y-%m-%dT%H:%M:%S%z"),
}

os.makedirs("data", exist_ok=True)
with open("data/run_metadata.json", "w") as f:
    json.dump(meta, f, indent=2)

print("=== run_metadata.json ===")
print(json.dumps(meta, indent=2))