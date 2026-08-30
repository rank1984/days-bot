"""
DAYS-BOT V3.4
Main Entry Point

Commands:

    python main.py scan
    python main.py scan --manual

    python main.py fullscan_v34
    python main.py fullscan_v34 --manual

Execution remains MANUAL ONLY.
The bot never submits orders.
"""

import sys
from pathlib import Path
from datetime import datetime, time

import pytz


BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


ET = pytz.timezone("America/New_York")


from utils.config import (
    BOT_VERSION,
    STRATEGY_VERSION,
    EXPERIMENT_MODE,
    ACCOUNT_SIZE,
    MAX_RISK_PER_TRADE_V31,
    MAX_POSITION_VALUE_PCT,
    TELEGRAM_TOKEN,
    TELEGRAM_CHAT_ID,
)

from database.db import init_db

from scanner.premarket import scan_premarket

from risk.trade_plan_v34 import build_trade_plan


def _in_premarket_window() -> bool:
    now = datetime.now(ET).time()

    return (
        time(8, 0)
        <= now
        < time(9, 30)
    )


def _apply_trade_plans(candidates):

    enriched = []

    for candidate in candidates:

        plan = build_trade_plan(
            candidate,
            account_size=ACCOUNT_SIZE,
            max_risk_pct=MAX_RISK_PER_TRADE_V31,
            max_position_pct=MAX_POSITION_VALUE_PCT,
        )

        candidate.update(plan)

        enriched.append(candidate)

    return enriched


def run_fullscan_v34(manual: bool = False):

    init_db()

    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    print()
    print("=" * 75)
    print("DAYS-BOT V3.4")
    print("FULLSCAN / TRADING-READY PIPELINE")
    print("=" * 75)

    print(
        f"Version:        {BOT_VERSION}"
    )

    print(
        f"Strategy:       {STRATEGY_VERSION}"
    )

    print(
        f"Mode:            "
        f"{'MANUAL' if manual else 'AUTOMATIC'}"
    )

    print(
        f"Time ET:         "
        f"{now_et.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"Account:         ${ACCOUNT_SIZE:,.2f}"
    )

    print(
        f"Max Risk:        "
        f"{MAX_RISK_PER_TRADE_V31 * 100:.2f}%"
    )

    print(
        f"Max Position:    "
        f"{MAX_POSITION_VALUE_PCT * 100:.1f}%"
    )

    print("=" * 75)

    # ---------------------------------------------------------
    # Automatic time gate
    # ---------------------------------------------------------

    if not manual and not _in_premarket_window():

        print(
            "[Main] Automatic scan outside "
            "08:00-09:30 ET."
        )

        print(
            "[Main] Scan aborted safely."
        )

        return

    # ---------------------------------------------------------
    # PREMARKET DISCOVERY
    # ---------------------------------------------------------

    print(
        "\n[Main] Starting V3.4 premarket discovery..."
    )

    candidates = scan_premarket(today)

    if not candidates:

        print(
            "[Main] No candidates."
        )

        return

    print(
        f"[Main] Premarket candidates: "
        f"{len(candidates)}"
    )

    # ---------------------------------------------------------
    # TRADE PLAN
    # ---------------------------------------------------------

    print(
        "\n[Main] Building deterministic trade plans..."
    )

    enriched = _apply_trade_plans(
        candidates
    )

    # ---------------------------------------------------------
    # Only valid plans
    # ---------------------------------------------------------

    valid = [
        c for c in enriched
        if c.get("plan_valid") is True
    ]

    print(
        f"[Main] Valid trade plans: "
        f"{len(valid)}"
    )

    # ---------------------------------------------------------
    # Top 5
    # ---------------------------------------------------------

    top5 = sorted(
        enriched,
        key=lambda x: (
            x.get("event_score", 0),
            x.get("gap_pct", 0),
            x.get("pm_volume", 0),
        ),
        reverse=True,
    )[:5]

    # ---------------------------------------------------------
    # Print result
    # ---------------------------------------------------------

    print()
    print("=" * 75)
    print("TOP 5 V3.4")
    print("=" * 75)

    for i, candidate in enumerate(top5, 1):

        print(
            f"{i}. {candidate.get('ticker')}"
        )

        print(
            f"   Score: "
            f"{candidate.get('event_score')}"
        )

        print(
            f"   Gap: "
            f"{candidate.get('gap_pct', 0):.2f}%"
        )

        print(
            f"   PM Volume: "
            f"{candidate.get('pm_volume', 0):,}"
        )

        print(
            f"   Entry: "
            f"{candidate.get('entry')}"
        )

        print(
            f"   Stop: "
            f"{candidate.get('stop')}"
        )

        print(
            f"   T1: "
            f"{candidate.get('target_1')}"
        )

        print(
            f"   T2: "
            f"{candidate.get('target_2')}"
        )

        print(
            f"   Shares: "
            f"{candidate.get('position_size')}"
        )

        print(
            f"   Decision: "
            f"{candidate.get('decision')}"
        )

        print()

    # ---------------------------------------------------------
    # IMPORTANT
    # ---------------------------------------------------------

    print("=" * 75)
    print(
        "⚠️ NO AUTOMATIC ORDERS"
    )
    print(
        "⚠️ PREMARKET CANDIDATE ≠ BUY"
    )
    print(
        "⚠️ BREAKOUT CONFIRMATION REQUIRED"
    )
    print("=" * 75)

    return top5


def run_scan(manual: bool = False):

    print(
        "[Main] Legacy scan requested."
    )

    return run_fullscan_v34(
        manual=manual
    )


if __name__ == "__main__":

    if len(sys.argv) < 2:

        print(
            "Usage:"
        )

        print(
            "  python main.py fullscan_v34 [--manual]"
        )

        print(
            "  python main.py scan [--manual]"
        )

        sys.exit(1)

    command = sys.argv[1].lower()

    manual = (
        "--manual" in sys.argv
        or "--force" in sys.argv
    )

    if command == "fullscan_v34":

        run_fullscan_v34(
            manual=manual
        )

    elif command == "scan":

        run_scan(
            manual=manual
        )

    else:

        print(
            f"Unknown command: {command}"
        )

        sys.exit(1)
