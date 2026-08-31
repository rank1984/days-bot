"""
DAYS-BOT V3.5 – Research Engine (Always sends detailed report)
"""
import sys
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

ET = pytz.timezone("America/New_York")

from utils.config import (
    BOT_VERSION, STRATEGY_VERSION, ACCOUNT_SIZE,
    MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
)
from scanner.research_engine import run_research_engine
from database.db import init_db, save_alert
from telegram_v3 import send_message, format_research_report


def run_fullscan_v34(manual=False, requested_date=None):
    init_db()
    now_et = datetime.now(ET)

    print("\n" + "="*74)
    print("DAYS-BOT V3.5 – RESEARCH ENGINE")
    print(f"Date: {now_et.strftime('%Y-%m-%d')} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print("="*74)

    # Run research engine
    result = run_research_engine()

    # Save all candidates to DB
    for c in result.get('all_candidates', []):
        try:
            save_alert(**c)
        except:
            pass

    # Send research report (always)
    msg = format_research_report(result, now_et)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    print(f"[Main] Sent research report.")
    print("="*74)
    print("⚠️ NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY")
    print("="*74)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py fullscan_v34 [--manual]")
        sys.exit(1)

    manual = "--manual" in sys.argv
    run_fullscan_v34(manual)
