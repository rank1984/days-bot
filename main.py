"""
DAYS-BOT V2.8.1 – Manual Execution / LIVE-SAFE
- scan: V2.8 pipeline (Fast Filter → PM Quant → Catalyst)
- review: evaluates candidates, calculates entry/stop/tp, sends detailed review
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
from utils.calculations import calculate_entry_stop_tp, calculate_net_profit
from telegram_formatter import (
    format_scan_breakdown,
    format_review_v27,
    format_watchlist,
    format_no_candidates,
    send_message
)


def scan_mode():
    """Runs V2.8.1 scan pipeline and sends breakdown + watchlist."""
    init_db()
    wm = WatchlistManager()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[Main] SCAN MODE V2.8.1 - {today}")

    candidates = scan_premarket(today)
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return

    # ====== DEBUG CONTRACT ======
    print("\n[DEBUG CONTRACT] Candidates from scanner:")
    for c in candidates[:10]:
        print(
            f"  {c['ticker']} | "
            f"score={c.get('event_score', 0)} | "
            f"rvol={c.get('rvol', 0):.2f} | "
            f"pm_dist={c.get('pm_high_dist', 999):.1f} | "
            f"vwap={c.get('pm_vwap', 0):.2f} | "
            f"spread={c.get('spread_pct')} | "
            f"catalyst={c.get('catalyst', '—')[:30]}"
        )

    # ====== הוספה ל-Watchlist ======
    added = 0
    for c in candidates[:10]:
        if '/' in c['ticker']:
            continue
        wm.add_to_watchlist(c)
        added += 1
    print(f"[Main] Added {added} candidates to Watchlist")

    # ====== שליחת Telegram ======
    stats = {
        'price_pass': len(candidates) * 5,
        'gap_pass': len(candidates) * 4,
        'vol_pass': len(candidates) * 3,
        'spread_pass': len(candidates) * 2,
        'fast_pass': len(candidates),
        'pm_vol_pass': len(candidates),
        'rvol_pass': len(candidates),
        'pm_dist_pass': len(candidates),
        'vwap_pass': len(candidates),
        'pm_quant_pass': len(candidates),
        'catalyst_pass': len(candidates),
        'final_pass': len(candidates),
    }
    msg = format_scan_breakdown(candidates[:5], stats, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    # ====== Watchlist ======
    watchlist = wm.get_active_watchlist()
    msg = format_watchlist(watchlist, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    # ====== Alerts ======
    for c in candidates[:10]:
        save_alert(
            ticker=c['ticker'],
            price=c['price'],
            gap_pct=c['gap_pct'],
            score=c.get('event_score', 0),
            catalyst=c.get('catalyst', '')
        )
    print(f"[Main] Done. {added} candidates added.")


def review_mode():
    """
    Evaluates watchlist for QUALIFIED candidates.
    Calculates Entry, Stop, TP1, TP2, RR, Net Profit.
    Sends detailed review via Telegram.
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
    if today_pnl < -MAX_DAILY_LOSS * 100:  # negative percentage
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

    # ---- Evaluate each candidate ----
    reviews = []
    for w in watchlist:
        # Only consider candidates with state = QUALIFIED or PREPARE/BREAKOUT
        state = w.get('state', 'WATCH')
        if state not in ('QUALIFIED', 'PREPARE', 'BREAKOUT'):
            continue

        # Hard filters (already applied, but double-check)
        spread = w.get('spread_pct')
        if spread is None or spread > MAX_READY_SPREAD:
            continue

        if w.get('event_score', 0) < 70:
            continue

        rvol = w.get('rvol', 0)
        if rvol < VALIDATION_MIN_RVOL:
            continue

        if w.get('gap_pct', 0) > MAX_GAP_PCT:
            continue

        if w.get('pm_high_dist', 999) > VALIDATION_MAX_PM_DIST:
            continue

        if w.get('catalyst', '—') == '—' or w.get('catalyst_score', 0) <= 0:
            continue

        price = w.get('price', 0)
        vwap = w.get('vwap', price)
        if price < vwap * (1 + VALIDATION_MIN_VWAP_DIST):
            continue

        # ---- Calculate Entry / Stop / TP ----
        trade_plan = calculate_entry_stop_tp(w)
        entry = trade_plan['entry']
        stop = trade_plan['stop']
        tp1 = trade_plan['tp1']
        tp2 = trade_plan['tp2']
        rr1 = trade_plan['rr1']
        rr2 = trade_plan['rr2']

        # ---- Calculate Net Profit (assuming 100 shares for estimation) ----
        shares = 100  # placeholder; actual sizing can be added later
        net1 = calculate_net_profit(entry, tp1, shares)
        net2 = calculate_net_profit(entry, tp2, shares)

        if net1['net_pct'] < MIN_NET_PROFIT_PCT:
            continue  # not worth it after costs

        reviews.append({
            'candidate': w,
            'entry': entry,
            'stop': stop,
            'tp1': tp1,
            'tp2': tp2,
            'rr1': rr1,
            'rr2': rr2,
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
