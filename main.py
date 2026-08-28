"""
DAYS-BOT V2.14 – EXPERIMENT MODE MAIN ENGINE

Modes:
    python main.py scan
        Automatic/normal experiment scan.
        Runs only during 08:00-09:30 ET.

    python main.py scan --manual
        Manual diagnostic/test run.
        Can be executed at any hour.
        Marked MANUAL and should NOT be treated as part of the
        official V2.14 experiment.

    python main.py scan --force
        Legacy compatibility option.
        Behaves like manual mode.
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
)

from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert
from watchlist_manager import WatchlistManager

from telegram_formatter import (
    format_scan_breakdown,
    format_watchlist,
    format_no_candidates,
    send_message,
)


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
        run_mode = "EXPERIMENT"

    # ============================================================
    # AUTOMATIC / EXPERIMENT WINDOW
    # ============================================================

    if not manual:

        if now_et.time() < time(8, 0):
            print(
                f"\n[Main] {BOT_VERSION} – "
                f"{now_et.strftime('%H:%M:%S')} ET "
                f"is before experiment window (08:00 ET)."
            )
            print("[Main] Automatic scan aborted.")
            return

        if now_et.time() >= time(9, 30):
            print(
                f"\n[Main] {BOT_VERSION} – "
                f"{now_et.strftime('%H:%M:%S')} ET "
                f"is after experiment window (09:30 ET)."
            )
            print("[Main] Automatic scan aborted.")
            return

    # ============================================================
    # START
    # ============================================================

    print("\n" + "=" * 70)
    print(f"[Main] DAYS-BOT {BOT_VERSION}")
    print(f"[Main] STRATEGY: {STRATEGY_VERSION}")
    print(f"[Main] MODE: {run_mode}")
    print(f"[Main] DATA: {DATA_VERSION}")
    print(f"[Main] DATE: {today}")
    print(f"[Main] TIME: {now_et.strftime('%H:%M:%S')} ET")
    print("=" * 70)

    if manual:
        print(
            "[Main] ⚠️ MANUAL RUN – "
            "diagnostic/testing only."
        )
        print(
            "[Main] This run must NOT be counted "
            "as an official V2.14 experiment observation."
        )

    # ============================================================
    # SCAN
    # ============================================================

    candidates = scan_premarket(today)

    if not candidates:

        universe = load_universe()

        msg = format_no_candidates(
            today,
            len(universe) if universe else 0
        )

        send_message(
            TELEGRAM_TOKEN,
            TELEGRAM_CHAT_ID,
            msg
        )

        print("[Main] No candidates found.")
        return

    # ============================================================
    # DEBUG CONTRACT
    # ============================================================

    print("\n[DEBUG CONTRACT] Candidates from scanner:")

    for c in candidates[:5]:

        spread = c.get("spread_pct")
        spread_str = (
            f"{spread:.2f}%"
            if spread is not None
            else "N/A"
        )

        catalyst = c.get(
            "catalyst_status",
            "UNAVAILABLE"
        )

        pm_dist = c.get("pm_high_dist")

        pm_dist_str = (
            f"{pm_dist:.1f}%"
            if pm_dist is not None
            else "N/A"
        )

        print(
            f"  {c['ticker']} | "
            f"mode={run_mode} | "
            f"strategy={STRATEGY_VERSION} | "
            f"quality={c.get('pm_data_quality', 'N/A')} | "
            f"rvol=UNAVAILABLE | "
            f"pm_dist={pm_dist_str} | "
            f"vwap={c.get('pm_vwap', 0):.2f} | "
            f"spread={spread_str} | "
            f"catalyst={catalyst}"
        )

    # ============================================================
    # SAVE
    # ============================================================

    added = 0

    for c in candidates[:10]:

        if "/" in c["ticker"]:
            continue

        # Experiment metadata
        c["strategy_version"] = STRATEGY_VERSION
        c["data_version"] = DATA_VERSION

        if manual:
            c["mode"] = "MANUAL"
        else:
            c["mode"] = EXPERIMENT_MODE

        wm.add_to_watchlist(c)

        save_alert(**c)

        added += 1

    # ============================================================
    # STATS
    # ============================================================

    stats = {
        "price_pass": len(candidates),
        "gap_pass": len(candidates),
        "vol_pass": len(candidates),
        "spread_pass": len(candidates),
        "fast_pass": len(candidates),
        "pm_vol_pass": len([
            c for c in candidates
            if c.get("pm_volume", 0) > 0
        ]),
        "rvol_pass": len(candidates),
        "pm_dist_pass": len(candidates),
        "vwap_pass": len([
            c for c in candidates
            if c.get("pm_vwap", 0) > 0
        ]),
        "pm_quant_pass": len(candidates),
        "catalyst_pass": len(candidates),
        "final_pass": len(candidates),
    }

    # ============================================================
    # TELEGRAM
    # ============================================================

    msg = format_scan_breakdown(
        candidates[:5],
        stats,
        today
    )

    send_message(
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
        msg
    )

    watchlist = wm.get_active_watchlist()

    msg = format_watchlist(
        watchlist,
        today
    )

    send_message(
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
        msg
    )

    # ============================================================
    # END
    # ============================================================

    print(
        f"\n[Main] Done. "
        f"{added} candidates added to DB & Watchlist."
    )

    print(
        "[Main] NO LIVE TRADING EXECUTED – "
        "SIGNAL LOGGING ONLY."
    )

    if manual:
        print(
            "[Main] ⚠️ MANUAL RUN COMPLETE – "
            "NOT PART OF OFFICIAL EXPERIMENT."
        )


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Usage: python main.py scan "
            "[--manual]"
        )
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode != "scan":
        print(f"Unknown mode: {mode}")
        sys.exit(1)

    manual_run = "--manual" in sys.argv

    # Backward compatibility:
    # --force is treated as manual.
    if "--force" in sys.argv:
        manual_run = True

    scan_mode(manual=manual_run)