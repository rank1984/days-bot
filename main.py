"""
DAYS-BOT V3.2 – DECISION ENGINE + OPENING CONFIRMATION

Modes:
    python main.py scan
        Automatic/normal scan.
        Runs premarket (08:00-09:15 ET) and opening confirmation (after 09:30 ET).

    python main.py scan --manual
        Manual diagnostic/test run.
        Can be executed at any hour.
"""

import sys
from pathlib import Path
from datetime import datetime, time
import pytz
import pandas as pd

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
    MAX_RISK_PER_TRADE_V31,
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY
)

from scanner.premarket import scan_premarket
from scanner.opening import check_opening_confirmation
from scanner.universe import load_universe
from database.db import init_db, save_alert
from watchlist_manager import WatchlistManager

# Legacy Telegram formatters (kept for fallback/errors)
from telegram_formatter import format_no_candidates, send_message

# V3.2 modules
from risk.trade_plan import build_trade_plan
from telegram_v3 import format_trade_card_v32


def scan_mode(manual: bool = False):
    init_db()
    wm = WatchlistManager()

    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    # ============================================================
    # MODE
    # ============================================================

    if manual:
        run_mode = "MANUAL"
    else:
        run_mode = "V3.2_LIVE"

    # ============================================================
    # AUTOMATIC / EXPERIMENT WINDOW
    # ============================================================

    if not manual:
        # אם זה אחרי 09:30 – נרוץ רק את Opening Monitor (לא סריקה מלאה)
        if now_et.time() >= time(9, 30):
            print(f"\n[Main] {BOT_VERSION} – {now_et.strftime('%H:%M:%S')} ET – Opening Confirmation Mode")
            # טען את רשימת ה-Watchlist מהסריקה האחרונה (נשמור בקובץ או ב-DB)
            # לצורך פשטות, נשתמש ב-DB או בקובץ watchlist.json
            watchlist = wm.get_watchlist()  # נניח שיש פונקציה כזו
            if not watchlist:
                print("[Main] No watchlist found. Run premarket scan first.")
                return
            confirmed = check_opening_confirmation(watchlist, now_et)
            if confirmed:
                for c in confirmed[:3]:
                    plan = build_trade_plan(c, confirmed_price=c.get('current_price'))
                    c.update(plan)
                    # שלח כרטיס החלטה
                    msg = format_trade_card_v32(c, plan, confirmed=True)
                    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
            else:
                print("[Main] No confirmed breakouts.")
            return

        # אם זה לפני 09:30 – רוץ כרגיל (Premarket)
        if now_et.time() < time(8, 0):
            print(f"\n[Main] {BOT_VERSION} – {now_et.strftime('%H:%M:%S')} ET is before premarket window (08:00 ET).")
            print("[Main] Automatic scan aborted.")
            return

    # ============================================================
    # PREMARKET SCAN (עד 09:30)
    # ============================================================

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT V3.2 – PREMARKET SCAN")
    print(f"[Main] STRATEGY: {STRATEGY_VERSION}")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print("[Main] ⚠️ MANUAL RUN – diagnostic/testing only.")

    # ------------------------------------------------------------
    # SCAN
    # ------------------------------------------------------------
    candidates = scan_premarket(today)

    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found.")
        return

    # ------------------------------------------------------------
    # V3.2 TRADE PLAN GENERATION
    # ------------------------------------------------------------
    print("\n[Main] Generating V3.2 Trade Plans for Top 20...")
    enriched_candidates = []
    for c in candidates[:20]:
        plan = build_trade_plan(c)
        c.update(plan)
        c["account_size"] = ACCOUNT_SIZE
        c["risk_pct"] = MAX_RISK_PER_TRADE_V31
        enriched_candidates.append(c)
        print(f"[TradePlan] {c['ticker']} -> {c['decision']} | Entry: {c.get('entry')} | Stop: {c.get('stop')}")

    # ------------------------------------------------------------
    # SAVE TO DATABASE & WATCHLIST
    # ------------------------------------------------------------
    added = 0
    for c in enriched_candidates[:10]:
        if "/" in c["ticker"]:
            continue
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION
        c["mode"] = run_mode

        wm.add_to_watchlist(c)   # נניח ש-wm שומר גם את הרשימה
        save_alert(**c)
        added += 1

    print(f"\n[Main] Saved {added} candidates to Watchlist & DB.")

    # ------------------------------------------------------------
    # SEND TOP 3 TELEGRAM CARDS (PRE-MARKET)
    # ------------------------------------------------------------
    print("\n[Main] Sending V3.2 Pre-market watch cards...")
    for c in enriched_candidates[:3]:
        msg = format_trade_card_v32(c, c, confirmed=False)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    # ------------------------------------------------------------
    # END
    # ------------------------------------------------------------
    print("\n" + "=" * 70)
    print("[Main] NO AUTOMATIC ORDERS – MANUAL EXECUTION ONLY.")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py scan [--manual]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode != "scan":
        print(f"Unknown mode: {mode}")
        sys.exit(1)

    manual_run = "--manual" in sys.argv or "--force" in sys.argv
    scan_mode(manual=manual_run)
