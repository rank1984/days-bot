"""
DAYS-BOT V2.6 – Main Entry Point
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
from database.db import init_db, save_alert, DB_PATH
from watchlist_manager import WatchlistManager
from paper_trader.paper_trader import PaperTrader
from telegram_formatter import (
    format_quant_report_v26,
    format_watchlist,
    format_no_candidates,
    send_message
)


def scan_mode():
    init_db()
    wm = WatchlistManager()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[Main] SCAN MODE - {today}")

    candidates = scan_premarket(today)
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return

    added = 0
    for c in candidates[:10]:
        if '/' in c['ticker']:
            continue
        wm.add_to_watchlist(c)
        added += 1

    print(f"[Main] Added {added} candidates to Watchlist")

    msg = format_quant_report_v26(candidates[:5], today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    watchlist = wm.get_active_watchlist()
    msg = format_watchlist(watchlist, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)

    for c in candidates[:10]:
        save_alert(
            ticker=c['ticker'],
            price=c['price'],
            gap_pct=c['gap_pct'],
            score=c.get('event_score', 0),
            catalyst=c.get('catalyst', '')
        )

    print(f"[Main] Done. {added} candidates added.")


def entry_mode():
    from database.db import get_open_trades, save_trade
    init_db()
    wm = WatchlistManager()
    trader = PaperTrader()

    # ---- Daily trade count ----
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT COUNT(*) FROM trades
        WHERE entry_time LIKE ?
    """, (today + '%',))
    daily_trades = cursor.fetchone()[0]
    conn.close()
    if daily_trades >= MAX_TRADES_PER_DAY:
        print(f"[Entry] Daily limit reached: {daily_trades} >= {MAX_TRADES_PER_DAY}")
        return

    # ---- Active trades ----
    open_trades = get_open_trades()
    if len(open_trades) >= MAX_ACTIVE_TRADES:
        print(f"[Entry] {len(open_trades)} active trades. Max={MAX_ACTIVE_TRADES}")
        return

    slots = min(
        MAX_ACTIVE_TRADES - len(open_trades),
        MAX_TRADES_PER_DAY - daily_trades
    )
    if slots <= 0:
        print("[Entry] No slots available")
        return

    # ---- READY candidates with HARD FILTERS ----
    ready = []
    for w in wm.get_active_watchlist():
        # 1. Spread must be known and <= MAX_READY_SPREAD
        spread = w.get("spread_pct")
        if spread is None or spread > MAX_READY_SPREAD:
            continue

        # 2. Status must be READY
        if w.get("status") != "READY":
            continue

        # 3. Event Score
        if w.get("event_score", 0) < MIN_READY_EVENT_SCORE:
            continue

        # 4. RVOL
        if w.get("rvol", 0) < MIN_READY_RVOL:
            continue

        # 5. Gap not too extended
        if w.get("gap_pct", 0) >= MAX_GAP_FOR_READY:
            continue

        # 6. PM High Distance must be within threshold
        if w.get("pm_high_dist", 999) > MAX_PM_HIGH_DIST_READY:
            continue

        # 7. VWAP – price must be above VWAP
        price = w.get("price", 0)
        vwap = w.get("vwap", price)
        if price < vwap * 1.01:  # at least 1% above VWAP
            continue

        # 8. Dilution risk
        if w.get("dilution_risk") in ("HIGH", "CRITICAL"):
            continue

        # 9. Catalyst must exist (not "—")
        catalyst = w.get("catalyst", "—")
        if catalyst == "—" or catalyst == "":
            continue

        ready.append(w)

    if not ready:
        print("[Entry] No READY candidates meeting V2.6 execution criteria.")
        return

    ready.sort(key=lambda x: x.get("event_score", 0), reverse=True)

    for candidate in ready[:slots]:
        ticker = candidate["ticker"]
        price = candidate.get("ready_price") or candidate["price"]

        # ---- Duplicate protection ----
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("""
            SELECT id FROM trades
            WHERE ticker = ? AND exit_time IS NULL
        """, (ticker,))
        if cursor.fetchone():
            print(f"[Entry] {ticker} already has open trade. Skipping.")
            conn.close()
            continue
        conn.close()

        result = trader.enter_trade(
            symbol=ticker,
            price=price,
            stop_price=candidate.get("stop_price"),
            tp1=candidate.get("tp1"),
            tp2=candidate.get("tp2"),
            rr1=candidate.get("rr1"),
            rr2=candidate.get("rr2"),
            score=candidate.get("event_score", 0),
            rvol=candidate.get("rvol", 0),
            gap=candidate.get("gap_pct", 0),
            dvol=candidate.get("dvol", 0),
            catalyst=candidate.get("catalyst", ""),
            trigger_price=candidate.get("trigger_price"),
            pm_high=candidate.get("pm_high"),
            vwap=candidate.get("vwap"),
            entry_type="LIMIT",
            wait_for_fill=10
        )

        if result.get("filled"):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                UPDATE watchlist SET status = 'EXECUTED'
                WHERE ticker = ? AND status = 'READY'
            """, (ticker,))
            conn.commit()
            conn.close()
            print(f"[Entry] ✅ {ticker} FILLED @ ${result['filled_price']:.2f}")
        else:
            print(f"[Entry] ⏳ {ticker} NOT FILLED — remains READY")


def full_mode():
    """Legacy full mode – for testing only"""
    scan_mode()
    entry_mode()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py [scan|entry|full]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    if mode == "scan":
        scan_mode()
    elif mode == "entry":
        entry_mode()
    elif mode == "full":
        full_mode()
    else:
        print(f"Unknown mode: {mode}")
