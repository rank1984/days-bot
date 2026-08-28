"""
DAYS-BOT V2.14 – EXPERIMENT MODE MAIN ENGINE
"""
import sys
from pathlib import Path
from datetime import datetime, time
import pytz

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

ET = pytz.timezone('America/New_York')

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
    send_message
)


def scan_mode(force: bool = False):
    init_db()
    wm = WatchlistManager()
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")

    # Strict Hard Check: 08:00 ET to 09:30 ET window
    if not force:
        if now_et.time() < time(8, 0):
            print(f"\n[Main] Current time is {now_et.strftime('%H:%M:%S')} ET (< 08:00 ET) - Premarket scan aborted.")
            return
        if now_et.time() >= time(9, 30):
            print(f"\n[Main] Current time is {now_et.strftime('%H:%M:%S')} ET (>= 09:30 ET) - Market already open. Premarket scan aborted.")
            return

    print(f"\n[Main] SCAN MODE {BOT_VERSION} ({EXPERIMENT_MODE}) - {today} {now_et.strftime('%H:%M:%S')} (ET) {'[FORCED]' if force else ''}")

    candidates = scan_premarket(today)
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return

    print("\n[DEBUG CONTRACT] Candidates from scanner (first 5):")
    for c in candidates[:5]:
        rvol_str = "UNAVAILABLE"
        spread = c.get('spread_pct')
        spread_str = f"{spread:.2f}%" if spread is not None else "N/A"
        catalyst = c.get('catalyst_status', 'UNAVAILABLE')
        pm_dist = c.get('pm_high_dist')
        pm_dist_str = f"{pm_dist:.1f}%" if pm_dist is not None else "N/A"
        
        print(
            f"  {c['ticker']} | "
            f"mode={EXPERIMENT_MODE} | "
            f"quality={c.get('pm_data_quality')} | "
            f"rvol={rvol_str} | "
            f"pm_dist={pm_dist_str} | "
            f"vwap={c.get('pm_vwap', 0):.2f} | "
            f"spread={spread_str} | "
            f"catalyst={catalyst}"
        )

    added = 0
    for c in candidates[:10]:
        if '/' in c['ticker']:
            continue
        wm.add_to_watchlist(c)
        save_alert(**c)
        added += 1

    stats = {
        'price_pass': len(candidates),
        'gap_pass': len(candidates),
        'vol_pass': len(candidates),
        'spread_pass': len(candidates),
        'fast_pass': len(candidates),
        'pm_vol_pass': len([c for c in candidates if c.get('pm_volume', 0) > 0]),
        'rvol_pass': len(candidates),
        'pm_dist_pass': len(candidates),
        'vwap_pass': len([c for c in candidates if c.get('pm_vwap', 0) > 0]),
        'pm_quant_pass': len(candidates),
        'catalyst_pass': len(candidates),
        'final_pass': len(candidates),
    }

    msg = format_scan_breakdown(candidates[:5], stats, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    watchlist = wm.get_active_watchlist()
    msg = format_watchlist(watchlist, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    print(f"[Main] Done. {added} candidates added to DB & Watchlist.")
    print("[Main] NO LIVE TRADING EXECUTED – SIGNAL LOGGING ONLY.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py [scan] [--force]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    force_run = "--force" in sys.argv

    if mode == "scan":
        scan_mode(force=force_run)
    else:
        print(f"Unknown mode: {mode}")
