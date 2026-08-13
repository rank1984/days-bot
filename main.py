"""
DAYS-BOT – Main Entry Point
Modes: scan (watchlist) | entry (execute trades) | full (legacy)
"""
import sys
import os
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
from telegram_formatter import format_watchlist, format_no_candidates, send_message
from watchlist_manager import WatchlistManager
from trade_manager.trade_manager import TradeManager
from paper_trader.paper_trader import PaperTrader

# Trade Constraints
MAX_ACTIVE_TRADES = 2
MAX_TRADES_PER_DAY = 3


def scan_mode():
    """סריקה והוספה ל-Watchlist (ללא כניסה)"""
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
        if '/' in c['ticker'] or 'USDC' in c['ticker'] or 'USDT' in c['ticker']:
            continue
        # הוסף ל-Watchlist
        wm.add_to_watchlist(c)
        added += 1
    
    print(f"[Main] Added {added} candidates to Watchlist")
    
    # שליחת Watchlist
    watchlist = wm.get_active_watchlist()
    msg = format_watchlist(watchlist, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    
    # שמירת התראות
    for c in candidates[:10]:
        save_alert(
            ticker=c['ticker'],
            price=c['price'],
            gap_pct=c['gap_pct'],
            score=c.get('score', 0),
            catalyst=c.get('catalyst', '')
        )
    
    print(f"[Main] Done. {added} candidates added.")


def entry_mode():
    """ביצוע PaperTrades על מועמדים ב-READY בהתאם למגבלת הפוזיציות"""
    from database.db import get_open_trades, save_trade

    init_db()
    wm = WatchlistManager()
    trader = PaperTrader()

    # בדיקת כמות עסקים פתוחות
    open_trades = get_open_trades()
    if len(open_trades) >= MAX_ACTIVE_TRADES:
        print(f"[Entry] {len(open_trades)} active trades. Max={MAX_ACTIVE_TRADES}")
        return

    slots = MAX_ACTIVE_TRADES - len(open_trades)

    # קבל מועמדים ב-READY
    ready = [w for w in wm.get_active_watchlist() if w.get("status") == "READY"]
    if not ready:
        print("[Entry] No READY candidates.")
        return

    # מיון לפי Score
    ready.sort(key=lambda x: x.get("score", 0), reverse=True)

    executed = 0
    for candidate in ready[:slots]:
        ticker = candidate["ticker"]
        # שימוש במחיר ה-Breakout במידה וקיים, אחרת fallback למחיר המקורי
        entry_price = candidate.get("ready_price") or candidate["price"]

        print(f"[Entry] 🚀 ENTER {ticker} @ ${entry_price:.2f}")

        # כניסה לעסקה
        trader.enter_trade(ticker, entry_price)

        # עדכון סטטוס ל-EXECUTED ב-Watchlist
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            UPDATE watchlist SET status = 'EXECUTED'
            WHERE ticker = ? AND status = 'READY'
        """, (ticker,))
        conn.commit()
        conn.close()
        executed += 1

    print(f"[Entry] Executed {executed} trades.")


def full_mode():
    """מצב legacy – סריקה + כניסה מיידית (לבדיקה)"""
    init_db()
    wm = WatchlistManager()
    trader = PaperTrader()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[Main] FULL MODE - {today}")
    
    candidates = scan_premarket(today)
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        return
    
    # בדיקת Trigger
    tm = TradeManager()
    for c in candidates[:5]:
        if '/' in c['ticker']:
            continue
        trigger = tm.check_trigger(c)
        if trigger['status'] == 'READY':
            print(f"[Main] Ready: {c['ticker']} @ ${c['price']:.2f}")
            trader.enter_trade(c['ticker'], c['price'])
            # שמור ב-DB
            save_alert(
                ticker=c['ticker'],
                price=c['price'],
                gap_pct=c['gap_pct'],
                score=c.get('score', 0),
                catalyst=c.get('catalyst', '')
            )
        else:
            print(f"[Main] {c['ticker']} - {trigger['status']}: {trigger['reason']}")


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
        print(f"Unknown mode: {mode}. Use scan, entry, or full.")
