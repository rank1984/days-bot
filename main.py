"""
DAYS-BOT V4.0 – Research Engine (Intraday + Swing)
"""
import sys
from pathlib import Path
from datetime import datetime
import pytz

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

ET = pytz.timezone("America/New_York")

from utils.config import (
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
)
from scanner.premarket import scan_premarket
from scanner.full_scan_v34 import full_scan_v34
from scanner.swing_engine import calculate_swing_score
from database.db import init_db, save_alert
from telegram_v3 import send_message, format_research_report


def run_fullscan_v34(manual=False):
    init_db()
    now_et = datetime.now(ET)

    print("\n" + "="*74)
    print("DAYS-BOT V4.0 – RESEARCH ENGINE (Intraday + Swing)")
    print(f"Date: {now_et.strftime('%Y-%m-%d')} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print("="*74)

    # 1. Discovery
    candidates = scan_premarket(now_et.strftime("%Y-%m-%d"), manual)
    if not candidates:
        print("[Main] No candidates found.")
        msg = "😴 לא נמצאו מועמדים היום. בדוק שוב ב-08:45 ET."
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        return

    # 2. Full Analysis (Intraday)
    top20 = full_scan_v34(candidates, manual)

    # 3. Swing Analysis for Top 20
    for c in top20:
        swing = calculate_swing_score(c)
        c['swing_score'] = swing.get('swing_score', 0)
        c['swing_data'] = swing
        c['trade_type'] = "WATCH"

        intraday_score = c.get('composite_score', 0)
        swing_score = c.get('swing_score', 0)

        if intraday_score >= 75 and swing_score >= 70:
            c['trade_type'] = "BOTH"
        elif intraday_score >= 75:
            c['trade_type'] = "INTRADAY"
        elif swing_score >= 70:
            c['trade_type'] = "SWING_1_3D"
        elif intraday_score >= 60 or swing_score >= 60:
            c['trade_type'] = "WATCH"
        else:
            c['trade_type'] = "NO_TRADE"

        save_alert(**c)

    # 4. Send Telegram
    msg = format_research_report(top20, now_et)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    print("="*74)
    print("⚠️ NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY")
    print("="*74)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py fullscan_v34 [--manual]")
        sys.exit(1)

    manual = "--manual" in sys.argv
    run_fullscan_v34(manual)
