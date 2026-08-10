"""
DAYS-BOT – WATCH MODE (no auto entry)
"""
import sys
import os
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import *
from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert
from telegram_formatter import format_watchlist, format_no_candidates, send_message
from watchlist_manager import WatchlistManager


def main():
    # 1. אתחול מסד הנתונים
    init_db()
    
    # 2. אתחול Watchlist Manager
    wm = WatchlistManager()
    
    # 3. סריקה
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n[Main] Scanning for {today}")
    candidates = scan_premarket(today)
    
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return
    
    # 4. הוספת מועמדויות ל-Watchlist (ולא כניסה)
    added = 0
    for c in candidates[:10]:
        # דילוג על קריפטו
        if '/' in c['ticker'] or 'USDC' in c['ticker'] or 'USDT' in c['ticker']:
            continue
        
        # הוסף ל-Watchlist (שומר ב-DB)
        wm.add_to_watchlist(c)
        added += 1
    
    print(f"[Main] Added {added} candidates to Watchlist")
    
    # 5. שליחת הודעת Watchlist לטלגרם
    watchlist = wm.get_active_watchlist()
    msg = format_watchlist(watchlist, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    
    # 6. שמירת התראות (alerts)
    for c in candidates[:10]:
        save_alert(
            ticker=c['ticker'],
            price=c['price'],
            gap_pct=c['gap_pct'],
            score=c.get('score', 0),
            catalyst=c.get('catalyst', '')
        )
    
    print(f"[Main] Done. {added} candidates added to Watchlist.")


if __name__ == "__main__":
    # קביעת מצב הרצה
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        main()
    else:
        print("Usage: python main.py scan")
