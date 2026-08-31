"""
DAYS-BOT V3.5 – Research Engine (Always sends Research Report)
"""
import sys
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

ET = pytz.timezone("America/New_York")

from utils.config import (
    BOT_VERSION, STRATEGY_VERSION, ACCOUNT_SIZE,
    MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
)
from scanner.premarket import scan_premarket
from scanner.full_scan_v35 import full_scan_v35
from scanner.universe import load_universe
from database.db import init_db, save_alert
from telegram_v3 import send_message, format_research_report
from risk.trade_plan_v34 import build_trade_plan


def resolve_scan_date(manual=False, requested_date=None):
    now = datetime.now(ET)
    if requested_date:
        return datetime.strptime(requested_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    if manual and now.weekday() >= 5:
        d = now.date() - timedelta(days=(now.weekday() - 4) % 7)
        return d.strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")


def run_research(manual=False, requested_date=None):
    init_db()
    now_et = datetime.now(ET)
    scan_date = resolve_scan_date(manual, requested_date)

    if not manual:
        if scan_date != now_et.strftime("%Y-%m-%d"):
            print("[Main] LIVE scan must use current date.")
            return
        if now_et.time() < time(8, 0) or now_et.time() >= time(9, 30):
            print("[Main] Outside 08:00-09:30 ET. Aborted.")
            return

    print("\n" + "="*74)
    print(f"DAYS-BOT V3.5 – RESEARCH ENGINE")
    print(f"Date: {scan_date} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print("="*74)

    # Discovery
    candidates = scan_premarket(scan_date, manual)
    if not candidates:
        # Send empty research report
        empty_result = {
            "top5_research": [],
            "trade_candidates": [],
            "filter_funnel": {"total": 0},
            "near_misses": []
        }
        msg = format_research_report(empty_result, scan_date, manual)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates – sent empty research report.")
        return

    # Full Research
    result = full_scan_v35(candidates, manual)

    # Save to DB (even rejected ones for learning)
    for c in result.get('top5_research', []):
        save_alert(**c)

    # Send Research Report
    msg = format_research_report(result, scan_date, manual)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    print(f"[Main] Sent research report.")
    print("="*74)
    print("⚠️ NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY")
    print("="*74)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py fullscan_v35 [--manual] [--date YYYY-MM-DD]")
        sys.exit(1)

    manual = "--manual" in sys.argv
    requested_date = None
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        requested_date = sys.argv[idx+1] if idx+1 < len(sys.argv) else None

    run_research(manual, requested_date)
