"""
DAYS-BOT V3.4
Main Entry Point

Commands:
    python main.py scan
    python main.py scan --manual

    python main.py fullscan_v34
    python main.py fullscan_v34 --manual
    python main.py fullscan_v34 --manual --date YYYY-MM-DD

Historical replay:
    python main.py fullscan_v34 --manual --date 2026-08-28
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
    BOT_VERSION,
    STRATEGY_VERSION,
    EXPERIMENT_MODE,
    DATA_VERSION,
    ACCOUNT_SIZE,
    MAX_RISK_PER_TRADE_V31,
    MAX_POSITION_VALUE_PCT,
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
)

from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert
from watchlist_manager import WatchlistManager
from telegram_formatter import format_no_candidates, send_message
from risk.trade_plan_v34 import build_trade_plan
from telegram_v3 import format_trade_card_v34, format_debug_report, format_no_candidates_v34


# ============================================================
# DATE HELPERS
# ============================================================

def get_last_weekday(date_obj):
    """Return the most recent weekday (Mon-Fri)."""
    while date_obj.weekday() >= 5:  # 5=Sat, 6=Sun
        date_obj -= timedelta(days=1)
    return date_obj


def resolve_scan_date(manual=False, requested_date=None):
    """
    LIVE: always today.
    MANUAL: if --date supplied use it; otherwise:
        - weekday -> today
        - weekend -> previous Friday
    """
    now_et = datetime.now(ET)
    today = now_et.date()

    if requested_date:
        try:
            parsed = datetime.strptime(requested_date, "%Y-%m-%d").date()
            print(f"[Main] Historical replay: {parsed.strftime('%Y-%m-%d')}")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {requested_date}. Use YYYY-MM-DD.")

    if manual:
        if today.weekday() >= 5:
            replay_date = get_last_weekday(today)
            print(f"[Main] Manual run on weekend. Using last trading day: {replay_date.strftime('%Y-%m-%d')}")
            return replay_date.strftime("%Y-%m-%d")

    return today.strftime("%Y-%m-%d")


# ============================================================
# TRADE PLAN APPLICATION
# ============================================================

def apply_trade_plans(candidates):
    enriched = []
    for c in candidates:
        plan = build_trade_plan(
            c,
            account_size=ACCOUNT_SIZE,
            max_risk_pct=MAX_RISK_PER_TRADE_V31,
            max_position_pct=MAX_POSITION_VALUE_PCT,
        )
        c.update(plan)
        c["account_size"] = ACCOUNT_SIZE
        c["risk_pct"] = MAX_RISK_PER_TRADE_V31
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION
        enriched.append(c)
    return enriched


# ============================================================
# MAIN SCAN
# ============================================================

def run_fullscan_v34(manual=False, requested_date=None):
    init_db()
    wm = WatchlistManager()

    now_et = datetime.now(ET)
    scan_date = resolve_scan_date(manual, requested_date)

    if manual:
        run_mode = "MANUAL_REPLAY"
    else:
        run_mode = "V3.4_LIVE"

    # LIVE time window
    if not manual:
        if scan_date != now_et.strftime("%Y-%m-%d"):
            print("[Main] ERROR: LIVE scan must use current date.")
            return
        if now_et.time() < time(8, 0) or now_et.time() >= time(9, 30):
            print(f"[Main] {now_et.strftime('%H:%M:%S')} ET outside 08:00-09:30. Aborted.")
            return

    print()
    print("=" * 74)
    print("DAYS-BOT V3.4")
    print("FULLSCAN / TRADING-READY PIPELINE")
    print("=" * 74)
    print(f"Version:        {BOT_VERSION}")
    print(f"Strategy:       {STRATEGY_VERSION}")
    print(f"Mode:           {run_mode}")
    print(f"Scan Date:      {scan_date}")
    print(f"Time ET:        {now_et.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Account:        ${ACCOUNT_SIZE:,.2f}")
    print(f"Max Risk:       {MAX_RISK_PER_TRADE_V31 * 100:.2f}%")
    print(f"Max Position:   {MAX_POSITION_VALUE_PCT * 100:.1f}%")
    print("=" * 74)

    if manual:
        print("[Main] MANUAL / REPLAY MODE – NO LIVE EXECUTION.")

    # --------------------------------------------------------
    # DISCOVERY
    # --------------------------------------------------------
    print("\n[Main] Starting V3.4 premarket discovery...")
    candidates = scan_premarket(target_date_str=scan_date, manual=manual)

    if not candidates:
        print(f"[Main] No valid candidates for {scan_date}.")
        universe = load_universe()
        msg = format_no_candidates_v34(scan_date, now_et, learning_mode=False, debug=False)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        return

    # --------------------------------------------------------
    # TRADE PLANS
    # --------------------------------------------------------
    print(f"\n[Main] Building V3.4 trade plans for {len(candidates)} candidates...")
    enriched = apply_trade_plans(candidates[:20])

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------
    added = 0
    for c in enriched[:10]:
        if "/" in c.get("ticker", ""):
            continue
        try:
            wm.add_to_watchlist(c)
            save_alert(**c)
            added += 1
        except Exception as e:
            print(f"[DB] Failed saving {c.get('ticker')}: {e}")
    print(f"[Main] Saved {added} candidates to DB / Watchlist.")

    # --------------------------------------------------------
    # TELEGRAM (TOP 1)
    # --------------------------------------------------------
    if enriched:
        top = enriched[0]
        msg = format_trade_card_v34(top)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print(f"[Main] Sent V3.4 Telegram for {top['ticker']}")

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------
    print()
    print("=" * 74)
    print("TOP 5 V3.4")
    print("=" * 74)
    for i, c in enumerate(enriched[:5], 1):
        print(f"{i}. {c['ticker']} | Score: {c.get('event_score', 0)} | Gap: {c.get('gap_pct', 0):.1f}% | Entry: {c.get('entry')} | Stop: {c.get('stop')} | Decision: {c.get('decision', 'WATCH')}")

    print()
    print("=" * 74)
    print("⚠️ NO AUTOMATIC ORDERS")
    print("⚠️ PREMARKET CANDIDATE ≠ BUY")
    print("⚠️ BREAKOUT CONFIRMATION REQUIRED")
    print("=" * 74)


def run_scan(manual=False, requested_date=None):
    print("[Main] Legacy scan redirected to fullscan_v34.")
    return run_fullscan_v34(manual, requested_date)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py scan [--manual] [--date YYYY-MM-DD]")
        print("  python main.py fullscan_v34 [--manual] [--date YYYY-MM-DD]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    manual = "--manual" in sys.argv or "--force" in sys.argv
    requested_date = None

    if "--date" in sys.argv:
        try:
            idx = sys.argv.index("--date")
            requested_date = sys.argv[idx + 1]
        except (IndexError, ValueError):
            print("ERROR: --date requires YYYY-MM-DD")
            sys.exit(1)

    if mode in ("scan", "fullscan_v34"):
        run_fullscan_v34(manual=manual, requested_date=requested_date)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
