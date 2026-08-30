"""
DAYS-BOT V3.4
FULLSCAN / TRADING-READY PIPELINE

Modes:
    python main.py scan
    python main.py scan --manual

    python main.py fullscan_v34
    python main.py fullscan_v34 --manual

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
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
    GEMINI_API_KEY,
    ACCOUNT_SIZE,
    MAX_RISK_PER_TRADE_V31,
)

from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert
from watchlist_manager import WatchlistManager

from telegram_formatter import format_no_candidates, send_message

from risk_engine import RiskEngine
from ai_decision import AIDecisionLayer
from telegram_v3 import format_decision_card

from risk.trade_plan_v34 import build_trade_plan_v34
from telegram_v3 import format_trade_card_v34


# ============================================================
# DATE HELPERS
# ============================================================

def get_last_weekday(date_obj):
    """
    Return the most recent weekday.
    Used only for MANUAL diagnostic mode.
    """
    while date_obj.weekday() >= 5:
        date_obj -= timedelta(days=1)
    return date_obj


def resolve_scan_date(manual=False, requested_date=None):
    """
    LIVE:
        Always use today's ET date.

    MANUAL:
        If --date supplied -> use it.
        Otherwise:
            weekday -> today
            weekend -> previous Friday
    """

    now_et = datetime.now(ET)
    today = now_et.date()

    if requested_date:
        try:
            parsed = datetime.strptime(
                requested_date,
                "%Y-%m-%d"
            ).date()

            print(
                f"[Main] Historical replay requested: "
                f"{parsed.strftime('%Y-%m-%d')}"
            )

            return parsed.strftime("%Y-%m-%d")

        except ValueError:
            raise ValueError(
                f"Invalid date '{requested_date}'. "
                f"Expected YYYY-MM-DD."
            )

    if manual:
        if today.weekday() >= 5:
            replay_date = get_last_weekday(today)

            print(
                f"[Main] Manual run on weekend detected."
            )
            print(
                f"[Main] Using previous trading day: "
                f"{replay_date.strftime('%Y-%m-%d')}"
            )

            return replay_date.strftime("%Y-%m-%d")

    return today.strftime("%Y-%m-%d")


# ============================================================
# MAIN SCAN
# ============================================================

def scan_mode(
    manual=False,
    requested_date=None
):

    init_db()
    wm = WatchlistManager()

    now_et = datetime.now(ET)

    # --------------------------------------------------------
    # RESOLVE DATE
    # --------------------------------------------------------

    scan_date = resolve_scan_date(
        manual=manual,
        requested_date=requested_date
    )

    # --------------------------------------------------------
    # MODE
    # --------------------------------------------------------

    if manual:
        run_mode = "MANUAL_REPLAY"
    else:
        run_mode = "V3_LIVE_EXPERIMENT"

    # --------------------------------------------------------
    # LIVE WINDOW
    # --------------------------------------------------------

    if not manual:

        # Never allow historical/live confusion.
        today_et = now_et.strftime("%Y-%m-%d")

        if scan_date != today_et:
            print(
                "[Main] ERROR: LIVE scan attempted with "
                "non-current date."
            )
            return

        if now_et.time() < time(8, 0):
            print(
                f"[Main] {now_et.strftime('%H:%M:%S')} ET "
                f"is before 08:00 ET."
            )
            print("[Main] Automatic scan aborted.")
            return

        if now_et.time() >= time(9, 30):
            print(
                f"[Main] {now_et.strftime('%H:%M:%S')} ET "
                f"is after 09:30 ET."
            )
            print("[Main] Automatic scan aborted.")
            return

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    print()
    print("=" * 74)
    print("DAYS-BOT V3.4")
    print("FULLSCAN / TRADING-READY PIPELINE")
    print("=" * 74)

    print(f"Version:        {BOT_VERSION}")
    print(f"Strategy:       {STRATEGY_VERSION}")
    print(f"Mode:            {run_mode}")
    print(f"Scan Date:      {scan_date}")
    print(f"Time ET:        {now_et.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Account:        ${ACCOUNT_SIZE:,.2f}")
    print(f"Max Risk:       {MAX_RISK_PER_TRADE_V31 * 100:.2f}%")
    print("=" * 74)

    if manual:
        print(
            "[Main] MANUAL / REPLAY MODE – "
            "NO LIVE EXECUTION."
        )

    # --------------------------------------------------------
    # PREMARKET DISCOVERY
    # --------------------------------------------------------

    print("\n[Main] Starting V3.4 premarket discovery...")

    candidates = scan_premarket(
        target_date_str=scan_date,
        manual=manual
    )

    # --------------------------------------------------------
    # NO CANDIDATES
    # --------------------------------------------------------

    if not candidates:

        print(
            "[Main] No valid candidates for "
            f"{scan_date}."
        )

        universe = load_universe()

        msg = format_no_candidates(
            scan_date,
            len(universe) if universe else 0
        )

        # In manual replay we still allow diagnostic Telegram.
        send_message(
            TELEGRAM_TOKEN,
            TELEGRAM_CHAT_ID,
            msg
        )

        return

    # --------------------------------------------------------
    # TRADE PLAN V3.4
    # --------------------------------------------------------

    print(
        f"\n[Main] Building V3.4 trade plans "
        f"for {len(candidates)} candidates..."
    )

    enriched_candidates = []

    for candidate in candidates[:20]:

        try:

            plan = build_trade_plan_v34(candidate)

            if not isinstance(plan, dict):
                plan = {}

            candidate.update(plan)

            candidate["account_size"] = ACCOUNT_SIZE
            candidate["risk_pct"] = MAX_RISK_PER_TRADE_V31
            candidate["mode"] = run_mode
            candidate["strategy_version"] = STRATEGY_VERSION
            candidate["data_version"] = DATA_VERSION

            enriched_candidates.append(candidate)

            print(
                f"[TradePlan] "
                f"{candidate['ticker']} -> "
                f"{candidate.get('decision', 'WATCH')} | "
                f"Entry={candidate.get('entry')} | "
                f"Stop={candidate.get('stop')}"
            )

        except Exception as e:

            print(
                f"[TradePlan] "
                f"{candidate.get('ticker')} failed: {e}"
            )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    added = 0

    for candidate in enriched_candidates[:10]:

        ticker = candidate.get("ticker", "")

        if "/" in ticker:
            continue

        try:

            wm.add_to_watchlist(candidate)
            save_alert(**candidate)

            added += 1

        except Exception as e:

            print(
                f"[DB] Failed saving {ticker}: {e}"
            )

    print(
        f"\n[Main] Saved {added} "
        f"candidates to Watchlist / DB."
    )

    # --------------------------------------------------------
    # V3.4 TELEGRAM
    # --------------------------------------------------------

    if not enriched_candidates:
        print("[Main] No enriched candidates.")
        return

    top_pick = enriched_candidates[0]

    print(
        "\n[Main] Top V3.4 candidate: "
        f"{top_pick.get('ticker')}"
    )

    try:

        msg_v34 = format_trade_card_v34(
            top_pick
        )

        send_message(
            TELEGRAM_TOKEN,
            TELEGRAM_CHAT_ID,
            msg_v34
        )

    except Exception as e:

        print(
            f"[Telegram] V3.4 card failed: {e}"
        )

    # --------------------------------------------------------
    # END
    # --------------------------------------------------------

    print()
    print("=" * 74)
    print(
        "[Main] NO AUTOMATIC ORDERS."
    )
    print(
        "[Main] MANUAL EXECUTION ONLY."
    )
    print("=" * 74)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Usage:"
        )
        print(
            "  python main.py scan [--manual]"
        )
        print(
            "  python main.py fullscan_v34 [--manual] "
            "[--date YYYY-MM-DD]"
        )
        sys.exit(1)

    mode = sys.argv[1].lower()

    manual = (
        "--manual" in sys.argv
        or "--force" in sys.argv
    )

    requested_date = None

    if "--date" in sys.argv:

        try:
            date_index = sys.argv.index("--date")
            requested_date = sys.argv[date_index + 1]

        except (IndexError, ValueError):
            print(
                "ERROR: --date requires YYYY-MM-DD"
            )
            sys.exit(1)

    if mode == "scan":

        scan_mode(
            manual=manual,
            requested_date=requested_date
        )

    elif mode == "fullscan_v34":

        scan_mode(
            manual=manual,
            requested_date=requested_date
        )

    else:

        print(f"Unknown mode: {mode}")
        sys.exit(1)
