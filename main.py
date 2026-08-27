"""
DAYS-BOT V2.12.1 – PM DIAGNOSTICS & PRODUCTION MAIN
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime, time
import pytz

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

ET = pytz.timezone('America/New_York')

from utils.config import *
from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import (
    init_db,
    save_alert,
    DB_PATH,
    get_all_trades,
    get_open_trades,
    get_monthly_usage
)
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


def get_equity() -> float:
    return 10_000.0


def scan_mode(force: bool = False):
    init_db()
    wm = WatchlistManager()
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")
    
    # Market Open Guardrail: Do not run premarket scan after 09:30 ET unless forced
    if not force and now_et.time() >= time(9, 30):
        print(f"\n[Main] Current time is {now_et.strftime('%H:%M:%S')} ET. Market already open (>= 09:30 ET) - Premarket scan aborted.")
        return

    print(f"\n[Main] SCAN MODE V2.12.1 - {today} {now_et.strftime('%H:%M:%S')} (ET) {'[FORCED]' if force else ''}")

    candidates = scan_premarket(today)
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return

    print("\n[DEBUG CONTRACT] Candidates from scanner (first 5):")
    for c in candidates[:5]:
        rvol = c.get('rvol')
        rvol_str = f"{rvol:.2f}" if rvol is not None else "N/A"
        spread = c.get('spread_pct')
        spread_str = f"{spread:.2f}" if spread is not None else "N/A"
        catalyst = c.get('catalyst')
        catalyst_str = catalyst[:30] if catalyst else "N/A"
        
        pm_dist = c.get('pm_high_dist')
        pm_dist_str = f"{pm_dist:.1f}" if pm_dist is not None else "N/A"
        
        print(
            f"  {c['ticker']} | "
            f"score={c.get('event_score', 0)} | "
            f"rvol={rvol_str} | "
            f"pm_dist={pm_dist_str} | "
            f"vwap={c.get('pm_vwap', 0):.2f} | "
            f"spread={spread_str} | "
            f"catalyst={catalyst_str}"
        )

    added = 0
    for c in candidates[:10]:
        if '/' in c['ticker']:
            continue
        wm.add_to_watchlist(c)
        added += 1
    print(f"[Main] Added {added} candidates to Watchlist")

    stats = {
        'price_pass': len(candidates) * 5,
        'gap_pass': len(candidates) * 4,
        'vol_pass': len(candidates) * 3,
        'spread_pass': len([c for c in candidates if c.get('spread_pct') is not None]),
        'fast_pass': len(candidates),
        'pm_vol_pass': len([c for c in candidates if c.get('pm_volume', 0) > 0]),
        'rvol_pass': len([c for c in candidates if c.get('rvol') is not None and c.get('rvol') >= VALIDATION_MIN_RVOL]),
        'pm_dist_pass': len([c for c in candidates if c.get('pm_high_dist') is not None and c.get('pm_high_dist') <= VALIDATION_MAX_PM_DIST]),
        'vwap_pass': len([c for c in candidates if c.get('pm_vwap', 0) > 0]),
        'pm_quant_pass': len(candidates),
        'catalyst_pass': len([c for c in candidates if c.get('catalyst_score', 0) >= VALIDATION_MIN_CATALYST_SCORE]),
        'final_pass': len(candidates),
    }
    msg = format_scan_breakdown(candidates[:5], stats, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    watchlist = wm.get_active_watchlist()
    msg = format_watchlist(watchlist, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

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
    print(f"[Main] Done. {added} candidates added to DB & Watchlist.")


def review_mode():
    init_db()
    wm = WatchlistManager()
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")
    print(f"\n[Main] REVIEW MODE - {today} {now_et.strftime('%H:%M:%S')} (ET)")

    monthly_ops, monthly_shares = get_monthly_usage()
    print(f"[Main] Current Monthly Usage (ET): {monthly_ops} ops | {monthly_shares} shares")

    watchlist = wm.get_active_watchlist()
    if not watchlist:
        print("[Main] Watchlist empty.")
        return

    trades = get_all_trades()
    today_trades = [t for t in trades if t.get('entry_time', '').startswith(today)]
    today_pnl = sum(t.get('pnl', 0) for t in today_trades if t.get('exit_time'))
    if today_pnl < -MAX_DAILY_LOSS * 100:
        print(f"[Main] Daily loss limit reached: {today_pnl:.2f}%. Stopping new recommendations.")
        return

    open_trades = get_open_trades()
    if len(open_trades) >= MAX_ACTIVE_TRADES:
        print(f"[Main] {len(open_trades)} active trades. Max={MAX_ACTIVE_TRADES}")
        return

    today_trades_count = len([t for t in trades if t.get('entry_time', '').startswith(today)])
    if today_trades_count >= MAX_TRADES_PER_DAY:
        print(f"[Main] Daily trade limit reached: {today_trades_count} >= {MAX_TRADES_PER_DAY}")
        return

    equity = get_equity()
    reviews = []

    for w in watchlist:
        state = w.get('state', 'WATCH')
        if state not in ('PREPARE', 'WATCH'):
            continue

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

        pm_dist = w.get('pm_high_dist')
        if pm_dist is not None and pm_dist > VALIDATION_MAX_PM_DIST:
            continue

        catalyst_score = w.get('catalyst_score', 0)
        if catalyst_score < VALIDATION_MIN_CATALYST_SCORE:
            continue

        price = w.get('price', 0)
        vwap = w.get('vwap', price)
        if vwap > 0 and price < vwap * (1 + VALIDATION_MIN_VWAP_DIST):
            continue

        trade_plan = calculate_entry_stop_tp(w)
        entry = trade_plan['entry']
        stop = trade_plan['stop']
        tp1 = trade_plan['tp1']
        tp2 = trade_plan['tp2']
        rr1 = trade_plan['rr1']
        rr2 = trade_plan['rr2']

        shares = calculate_position_size(entry, stop, equity, MAX_RISK_PER_TRADE)
        if shares <= 0:
            continue

        net1 = calculate_net_profit(
            entry=entry,
            exit_price=tp1,
            shares=shares,
            monthly_ops_used=monthly_ops,
            monthly_shares_used=monthly_shares
        )
        net2 = calculate_net_profit(
            entry=entry,
            exit_price=tp2,
            shares=shares,
            monthly_ops_used=monthly_ops,
            monthly_shares_used=monthly_shares
        )

        target_min_pct = MIN_NET_PROFIT_PCT * 100 if MIN_NET_PROFIT_PCT < 1.0 else MIN_NET_PROFIT_PCT
        if net1['net_pct'] < target_min_pct:
            print(f"[{w['ticker']}] Rejected: Net return ({net1['net_pct']}%) below minimum target ({target_min_pct}%).")
            continue

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

    msg = format_review_v27(reviews, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    print(f"[Main] Sent review for {len(reviews)} candidates.")
    print("[Main] MANUAL EXECUTION REQUIRED – BOT DOES NOT TRADE.")


def full_mode():
    print("[Main] Full mode disabled. Use scan and review only.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py [scan|review|full] [--force]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    force_run = "--force" in sys.argv

    if mode == "scan":
        scan_mode(force=force_run)
    elif mode == "review":
        review_mode()
    elif mode == "full":
        full_mode()
    else:
        print(f"Unknown mode: {mode}")
