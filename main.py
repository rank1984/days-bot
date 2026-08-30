"""
DAYS-BOT V3.2 – Full Scan & Manual Trading MVP
"""
import sys
from pathlib import Path
from datetime import datetime, time
import pytz

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

ET = pytz.timezone("America/New_York")

from utils.config import (
    BOT_VERSION,
    STRATEGY_VERSION,
    EXPERIMENT_MODE,
    DATA_VERSION,
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
    ACCOUNT_SIZE,
    MAX_RISK_PER_TRADE_V31
)

from scanner.premarket import scan_premarket
from scanner.opening import check_opening_confirmation
from scanner.full_scan import full_scan
from scanner.universe import load_universe
from database.db import init_db, save_alert
from watchlist_manager import WatchlistManager
from telegram_formatter import format_no_candidates, send_message
from risk.trade_plan import build_trade_plan
from telegram_v3 import format_trade_card_v31, format_full_alert


def scan_mode(manual: bool = False):
    init_db()
    wm = WatchlistManager()

    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    if manual:
        run_mode = "MANUAL"
    else:
        run_mode = "V3.2_LIVE_EXPERIMENT"

    # Automatic window
    if not manual:
        if now_et.time() < time(8, 0):
            print(f"[Main] Before 08:00 ET – abort.")
            return
        if now_et.time() >= time(9, 30):
            print(f"[Main] After 09:30 ET – abort (use --manual for testing).")
            return

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT V3.2 – PREMARKET SCAN")
    print(f"[Main] STRATEGY: {STRATEGY_VERSION}")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print("[Main] ⚠️ MANUAL RUN – diagnostic/testing only.")

    # 1. Scan
    candidates = scan_premarket(today)
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found.")
        return

    # 2. Build Trade Plan for Top 10
    enriched = []
    for c in candidates[:10]:
        plan = build_trade_plan(c)
        c.update(plan)
        c["account_size"] = ACCOUNT_SIZE
        c["risk_pct"] = MAX_RISK_PER_TRADE_V31
        enriched.append(c)

    # 3. Save to DB & Watchlist
    added = 0
    for c in enriched[:5]:
        if "/" in c["ticker"]:
            continue
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION
        c["mode"] = run_mode
        wm.add_to_watchlist(c)
        save_alert(**c)
        added += 1
    print(f"[Main] Saved {added} candidates.")

    # 4. Send Telegram (top 1 – V3.1 format)
    if enriched:
        top = enriched[0]
        msg = format_trade_card_v31(top)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print(f"[Main] Sent Telegram for {top['ticker']}")

    print("\n" + "=" * 70)
    print("[Main] NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY.")
    print("=" * 70)


def full_scan_mode(manual: bool = False):
    """מצב סריקה מלאה – מחזיר 5 מניות עם ניתוח מעמיק"""
    init_db()

    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    if manual:
        run_mode = "MANUAL_FULL"
    else:
        run_mode = "V3.2_FULL_AUTO"

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT V3.2 – FULL SCAN (5 TOP PICKS)")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print("[Main] ⚠️ MANUAL RUN – diagnostic/testing only.")

    top5 = full_scan(manual)
    if not top5:
        print("[Main] No candidates after full analysis.")
        return

    # Save to DB & send Telegram
    for c in top5:
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION
        c["mode"] = run_mode
        save_alert(**c)
        msg = format_full_alert(c)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print(f"[Main] Sent full alert for {c['ticker']}")

    print("\n" + "=" * 70)
    print("[Main] Full scan complete. 5 picks sent to Telegram.")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py scan [--manual]")
        print("  python main.py fullscan [--manual]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    manual_run = "--manual" in sys.argv or "--force" in sys.argv

    if mode == "scan":
        scan_mode(manual=manual_run)
    elif mode == "fullscan":
        full_scan_mode(manual=manual_run)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
