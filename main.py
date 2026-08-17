"""
DAYS-BOT – Main Entry Point
Modes: scan (watchlist) | entry (execute trades) | ai (ai-powered analysis) | full (legacy)
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
from telegram_formatter import (
    format_watchlist,
    format_quant_report,
    format_no_candidates,
    send_message
)
from watchlist_manager import WatchlistManager
from trade_manager.trade_manager import TradeManager
from paper_trader.paper_trader import PaperTrader
from ai_quant.parser import parse_and_validate
from ai_quant.engine import AIQuantEngine
from ai_quant.formatter import format_report

# DEBUG: בדיקת טעינת מפתח Finnhub בעת עליית המערכת
finnhub_key = globals().get('FINNHUB_API_KEY', os.getenv('FINNHUB_API_KEY'))
if finnhub_key:
    print(f"[DEBUG] FINNHUB_API_KEY Loaded: {finnhub_key[:5]}***")
else:
    print("[DEBUG] ⚠️ FINNHUB_API_KEY NOT FOUND in Config / Environment Variables!")

# Trade Constraints
MAX_ACTIVE_TRADES = 2
MAX_TRADES_PER_DAY = 3


def scan_mode():
    """סריקה, הוספה ל-Watchlist ושליחת דוחות לטלגרם"""
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
            
        # הוסף Event Score ונתונים נלווים למועמד
        c['event_score'] = c.get('event_score', 0)
        c['setup_grade'] = c.get('setup_grade', 'UNKNOWN')
        c['dilution_risk'] = c.get('dilution_risk', 'UNKNOWN')
        
        # הוסף ל-Watchlist
        wm.add_to_watchlist(c)
        added += 1
    
    print(f"[Main] Added {added} candidates to Watchlist")
    
    # 1. שליחת דוח AI Quant Report
    try:
        msg_quant = format_quant_report(candidates[:10], today)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg_quant)
        print("[Main] ✅ AI Quant report sent to Telegram")
    except Exception as e:
        print(f"[Main] ❌ Error sending Quant report: {e}")

    # 2. שליחת Watchlist
    try:
        watchlist = wm.get_active_watchlist()
        msg_watchlist = format_watchlist(watchlist, today)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg_watchlist)
        print("[Main] ✅ Watchlist report sent to Telegram")
    except Exception as e:
        print(f"[Main] ❌ Error sending Watchlist report: {e}")

    # שמירת התראות
    for c in candidates[:10]:
        save_alert(
            ticker=c['ticker'],
            price=c['price'],
            gap_pct=c['gap_pct'],
            score=c.get('score', 0),
            catalyst=c.get('catalyst', '')
        )
    
    print(f"[Main] Done. {added} candidates processed.")


def entry_mode():
    """ביצוע PaperTrades על מועמדים ב-READY בהתאם למגבלת הפוזיציות ול-Event Score"""
    from database.db import get_open_trades

    init_db()
    wm = WatchlistManager()
    trader = PaperTrader()

    open_trades = get_open_trades()
    if len(open_trades) >= MAX_ACTIVE_TRADES:
        print(f"[Entry] {len(open_trades)} active trades. Max={MAX_ACTIVE_TRADES}")
        return

    slots = MAX_ACTIVE_TRADES - len(open_trades)

    min_ready_score = globals().get('MIN_READY_EVENT_SCORE', 60)
    min_ready_rvol = globals().get('MIN_READY_RVOL', 1.5)
    max_ready_spread = globals().get('MAX_READY_SPREAD', 3.0)

    ready = [w for w in wm.get_active_watchlist() 
             if w.get("status") == "READY"
             and w.get("event_score", 0) >= min_ready_score
             and w.get("rvol", 0) >= min_ready_rvol
             and w.get("spread_pct", 10) <= max_ready_spread
             and w.get("dilution_risk") != "CRITICAL"]
             
    if not ready:
        print("[Entry] No READY candidates meeting Event Score criteria.")
        return

    ready.sort(key=lambda x: x.get("event_score", x.get("score", 0)), reverse=True)

    for candidate in ready[:slots]:
        ticker = candidate["ticker"]
        price = candidate.get("ready_price") or candidate["price"]

        result = trader.enter_trade(
            symbol=ticker,
            price=price,
            stop_price=candidate.get("stop_price"),
            tp1=candidate.get("tp1"),
            tp2=candidate.get("tp2"),
            rr1=candidate.get("rr1"),
            rr2=candidate.get("rr2"),
            score=candidate.get("event_score", candidate.get("score", 0)),
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
            print(f"[Entry] ⏳ {ticker} NOT FILLED")


def ai_mode():
    candidates = parse_and_validate()

    if not candidates:
        print("[AI] ❌ No valid candidates parsed.")
        return

    for candidate in candidates:
        print(
            f"[AI] Candidate: "
            f"{candidate['ticker']} "
            f"${candidate['price']:.2f} "
            f"Gap={candidate['gap_pct']:.2f}% "
            f"DAYS={candidate['days_score']}"
        )

    engine = AIQuantEngine()
    result = engine.analyze(candidates)
    report = format_report(result)

    print("\n")
    print(report)

    try:
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, report)
        print("[AI] ✅ Report sent to Telegram.")
    except Exception as e:
        print(f"[AI] ⚠️ Telegram error: {e}")


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
    
    tm = TradeManager()
    for c in candidates[:5]:
        if '/' in c['ticker']:
            continue
        trigger = tm.check_trigger(c)
        if trigger['status'] == 'READY':
            print(f"[Main] Ready: {c['ticker']} @ ${c['price']:.2f}")
            trader.enter_trade(c['ticker'], c['price'])
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
        print("Usage: python main.py [scan|entry|ai|full]")
        sys.exit(1)
    
    mode = sys.argv[1].lower()

    if mode == "scan":
        scan_mode()
    elif mode == "entry":
        entry_mode()
    elif mode == "ai":
        ai_mode()
    elif mode == "full":
        full_mode()
    else:
        print(f"Unknown mode: {mode}. Use scan, entry, ai, or full.")
