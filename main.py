"""
DAYS-BOT V2.12 – FULL FIXED
- Scan: V2.12 with Near-Miss Debug
- Review: Unified Entry, Double Fees, Net Tax, Position Sizing
- NO ORDER EXECUTION – bot recommends, you execute manually in BLINK
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import *
from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert, DB_PATH, get_all_trades, get_open_trades
from watchlist_manager import WatchlistManager
from utils.calculations import (
    calculate_entry_stop_tp,
    calculate_net_profit,
    calculate_position_size,
)
from telegram_formatter import (
    format_scan_breakdown,
    format_review_v27,
    format_watchlist,
    format_no_candidates,
    send_message
)


# ── Helper for position sizing (placeholder equity until real account) ──
def get_equity() -> float:
    """
    Placeholder: return a fixed equity for now.
    Later, replace with actual account equity from Alpaca Paper API.
    """
    # You can set your paper trading starting equity here, e.g., 10,000 USD
    return 10_000.0


def scan_mode():
    """Runs V2.12 scan pipeline and sends breakdown + watchlist."""
    init_db()
    wm = WatchlistManager()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[Main] SCAN MODE V2.12 - {today}")

    candidates = scan_premarket(today)
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return

    # Debug Contract
    print("\n[DEBUG CONTRACT] Candidates from scanner (first 5):")
    for c in candidates[:5]:
        rvol = c.get('rvol')
        rvol_str = f"{rvol:.2f}" if rvol is not None else "N/A"
        spread = c.get('spread_pct')
        spread_str = f"{spread:.2f}" if spread is not None else "N/A"
        catalyst = c.get('catalyst')
        catalyst_str = catalyst[:30] if catalyst else "N/A"
        print(
            f"  {c['ticker']} | "
            f"score={c.get('event_score', 0)} | "
            f"rvol={rvol_str} | "
            f"pm_dist={c.get('pm_high_dist', 999):.1f} | "
            f"vwap={c.get('pm_vwap', 0):.2f} | "
            f"spread={spread_str} | "
            f"catalyst={catalyst_str}"
        )

    # Add to watchlist
    added = 0
    for c in candidates[:10]:
        if '/' in c['ticker']:
            continue
        wm.add_to_watchlist(c)
        added += 1
    print(f"[Main] Added {added} candidates to Watchlist")

    # Statistics for Telegram
    stats = {
        'price_pass': len(candidates) * 5,
        'gap_pass': len(candidates) * 4,
        'vol_pass': len(candidates) * 3,
        'spread_pass': len([c for c in candidates if c.get('spread_pct') is not None]),
        'fast_pass': len(candidates),
        'pm_vol_pass': len([c for c in candidates if c.get('pm_volume', 0) > 0]),
        'rvol_pass': len([c for c in candidates if c.get('rvol') is not None and c.get('rvol') >= VALIDATION_MIN_RVOL]),
        'pm_dist_pass': len([c for c in candidates if c.get('pm_high_dist', 999) <= VALIDATION_MAX_PM_DIST]),
        'vwap_pass': len([c for c in candidates if c.get('pm_vwap', 0) > 0]),
        'pm_quant_pass': len(candidates),
        'catalyst_pass': len([c for c in candidates if c.get('catalyst') is not None and c.get('catalyst_score', 0) >= VALIDATION_MIN_CATALYST_SCORE]),
        'final_pass': len(candidates),
    }
    msg = format_scan_breakdown(candidates[:5], stats, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    # Watchlist
    watchlist = wm.get_active_watchlist()
    msg = format_watchlist(watchlist, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    # Save alerts
    for c in candidates[:10]:
        catalyst = c.get('catalyst')
        catalyst_str = catalyst if catalyst else 'N/A'
        save_alert(
            ticker=c['ticker'],
            price=c['price'],
            gap_pct=c['gap_pct'],
            score=c.get('event_score', 0),
            catalyst=catalyst_str
        )
    print(f"[Main] Done. {added} candidates added.")


def review_mode():
    """
    Evaluates watchlist candidates against all hard filters,
    calculates Entry/Stop/TP/RR with unified Entry logic,
    computes Net Profit using real position sizing and double fees,
    sends detailed review via Telegram.
    BOT DOES NOT EXECUTE ORDERS.
    """
    init_db()
    wm = WatchlistManager()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[Main] REVIEW MODE - {today}")

    watchlist = wm.get_active_watchlist()
    if not watchlist:
        print("[Main] Watchlist empty.")
        return

    # ---- Check daily loss limit ----
    trades = get_all_trades()
    today_trades = [t for t in trades if t.get('entry_time', '').startswith(today)]
    today_pnl = sum(t.get('pnl', 0) for t in today_trades if t.get('exit_time'))
    if today_pnl < -MAX_DAILY_LOSS * 100:
        print(f"[Main] Daily loss limit reached: {today_pnl:.2f}%. Stopping new recommendations.")
        return

    # ---- Active trades count ----
    open_trades = get_open_trades()
    if len(open_trades) >= MAX_ACTIVE_TRADES:
        print(f"[Main] {len(open_trades)} active trades. Max={MAX_ACTIVE_TRADES}")
        return

    # ---- Daily trade count ----
    today_trades_count = len([t for t in trades if t.get('entry_time', '').startswith(today)])
    if today_trades_count >= MAX_TRADES_PER_DAY:
        print(f"[Main] Daily trade limit reached: {today_trades_count} >= {MAX_TRADES_PER_DAY}")
        return

    # ---- Equity for position sizing ----
    equity = get_equity()   # placeholder; replace with real account later

    reviews = []
    for w in watchlist:
        state = w.get('state', 'WATCH')
        if state not in ('PREPARE', 'WATCH'):
            continue

        # ---- Hard Filters ----
        spread = w.get('spread_pct')
        if spread is not None and spread > VALIDATION_MAX_SPREAD:
            continue

        event_score = w.get('event_score', 0)
        if event_score < 60:
            continue

        rvol = w.get('rvol')
        if rvol is not None and rvol < VALIDATION_MIN_RVOL:
            continue

        gap = w.get('gap_pct', 0)
        if gap > DISCOVERY_MAX_GAP:
            continue

        pm_dist = w.get('pm_high_dist', 999)
        if pm_dist > VALIDATION_MAX_PM_DIST:
            continue

        catalyst_score = w.get('catalyst_score', 0)
        if catalyst_score < VALIDATION_MIN_CATALYST_SCORE:
            continue

        price = w.get('price', 0)
        vwap = w.get('vwap', price)
        if vwap > 0 and price < vwap * (1 + VALIDATION_MIN_VWAP_DIST):
            continue

        # ---- Unified Entry Calculation ----
        trade_plan = calculate_entry_stop_tp(w)
        entry = trade_plan['entry']
        stop = trade_plan['stop']
        tp1 = trade_plan['tp1']
        tp2 = trade_plan['tp2']
        rr1 = trade_plan['rr1']
        rr2 = trade_plan['rr2']

        # ---- Position Sizing ----
        shares = calculate_position_size(entry, stop, equity, MAX_RISK_PER_TRADE)
        if shares <= 0:
            continue   # not enough capital for this trade

        # ---- Net Profit Calculations (using correct fees, tax) ----
        net1 = calculate_net_profit(entry, tp1, shares)
        net2 = calculate_net_profit(entry, tp2, shares)

        # ---- Minimum net profit gate ----
        if net1['net_pct'] < MIN_NET_PROFIT_PCT:
            # If even TP1 doesn't meet the net profit threshold, skip
            continue

        # ---- Candidate passed all ----
        reviews.append({
            'candidate': w,
            'entry': entry,
            'stop': stop,
            'tp1': tp1,
            'tp2': tp2,
            'rr1': rr1,
            'rr2': rr2,
            'shares': shares,
            'net1': net1,
            'net2': net2,
        })

    if not reviews:
        print("[Main] No review-worthy candidates.")
        return

    # ---- Send review to Telegram ----
    msg = format_review_v27(reviews, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    print(f"[Main] Sent review for {len(reviews)} candidates.")
    print("[Main] MANUAL EXECUTION REQUIRED – BOT DOES NOT TRADE.")


def full_mode():
    """Legacy full mode – disabled for safety."""
    print("[Main] Full mode disabled. Use scan and review only.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py [scan|review|full]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    if mode == "scan":
        scan_mode()
    elif mode == "review":
        review_mode()
    elif mode == "full":
        full_mode()
    else:
        print(f"Unknown mode: {mode}")
