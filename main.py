"""
DAYS-BOT V3.4 – Main Entry (Always sends Telegram, even with no candidates)
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
from scanner.full_scan_v34 import full_scan_v34
from scanner.universe import load_universe
from database.db import init_db, save_alert
from watchlist_manager import WatchlistManager
from telegram_v3 import send_message, format_trade_card_v34, format_no_candidates_v34
from risk.trade_plan_v34 import build_trade_plan


def resolve_scan_date(manual=False, requested_date=None):
    now = datetime.now(ET)
    if requested_date:
        return datetime.strptime(requested_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    if manual and now.weekday() >= 5:
        d = now.date() - timedelta(days=(now.weekday() - 4) % 7)
        return d.strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")


def run_fullscan_v34(manual=False, requested_date=None):
    init_db()
    wm = WatchlistManager()
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
    print("DAYS-BOT V3.4 – FULLSCAN")
    print(f"Date: {scan_date} | Mode: {'MANUAL' if manual else 'LIVE'}")
    print("="*74)

    candidates = scan_premarket(scan_date, manual)
    if not candidates:
        msg = format_no_candidates_v34(scan_date, now_et, learning_mode=False, debug=False)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates – sent notification.")
        return

    # Full analysis
    top5 = full_scan_v34(candidates, manual)

    if not top5:
        # Fallback: use best candidates from premarket
        top5 = candidates[:5]
        for c in top5:
            c['composite_score'] = c.get('event_score', 0)
            c['analysis'] = {}

    # Apply trade plans
    for c in top5:
        plan = build_trade_plan(c, ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT)
        c.update(plan)
        c["account_size"] = ACCOUNT_SIZE
        c["risk_pct"] = MAX_RISK_PER_TRADE_V31
        c["strategy_version"] = STRATEGY_VERSION
        c["mode"] = "MANUAL_REPLAY" if manual else "LIVE"
        save_alert(**c)

    # Send Telegram
    for c in top5[:3]:
        msg = format_trade_card_v34(c)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    print(f"[Main] Sent {len(top5[:3])} alerts.")
    print("="*74)
    print("⚠️ NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY")
    print("="*74)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py fullscan_v34 [--manual] [--date YYYY-MM-DD]")
        sys.exit(1)

    manual = "--manual" in sys.argv
    requested_date = None
    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        requested_date = sys.argv[idx+1] if idx+1 < len(sys.argv) else None

    run_fullscan_v34(manual, requested_date)