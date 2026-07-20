"""
DAYS-BOT Main Entry Point
Integrated with automated Premarket Scanning and Trade Management.
"""
import sys
import os
from pathlib import Path
import time
from datetime import datetime
import argparse

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import *
from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert, already_sent_today
from telegram_formatter import format_preopen_list, format_no_candidates, send_message

# ייבוא מנהל העסקאות החדש שלך
from trade_manager import TradeManager

# backtester מושבת זמנית
# from backtester.backtester import Backtester


def run_full_pipeline():
    """Run the full scan and alert pipeline"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[Main] Mode: full (Alert Mode)")
    print(f"=== [DAYS-BOT] {today} {datetime.now().strftime('%H:%M')} ET ===")
    
    init_db()
    
    # הרצת הסורק המשופר (כולל RVOL, DVol וחדשות)
    universe = load_universe()
    universe_size = len(universe) if universe else 0
    candidates = scan_premarket(today)
    
    if not candidates:
        msg = format_no_candidates(today, universe_size)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        return
    
    # סינון מניות שכבר נשלחו היום למניעת כפילויות במובייל
    filtered = []
    for c in candidates:
        if not already_sent_today(c['ticker'], today):
            filtered.append(c)
    
    if not filtered:
        print("[Main] All candidates already sent today")
        return
    
    # שליחת רשימת הטופ 5 לטלגרם
    msg = format_preopen_list(filtered, today, universe_size=universe_size)
    success = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    
    if success:
        for c in filtered:
            save_alert(
                ticker=c['ticker'],
                price=c['price'],
                gap_pct=c['gap_pct'],
                score=c.get('score', 0),
                catalyst=c.get('catalyst', '—')
            )
        print(f"[Main] Sent {len(filtered)} candidates to Telegram")


def run_paper_trade():
    """
    Paper Trading Mode with Automatic Preopen Scanner and Live Execution/Exit Management
    """
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[Main] Mode: paper (Automated Trading)")
    print(f"=== [DAYS-BOT TRADER] {today} {datetime.now().strftime('%H:%M')} ET ===")
    
    # אתחול בסיס הנתונים ומנהל המסחר (במצב Paper)
    init_db()
    trader = TradeManager(paper=True)
    
    # הפעלת הסורק האגרסיבי
    candidates = scan_premarket(today)
    if not candidates:
        print("[PaperTrade] 😴 No high quality breakout candidates found today. Aborting trade cycle.")
        return
    
    # בחירת המועמדת המובילה ביותר (מדורגת במקום ה-1 עם הציון הגבוה ביותר בסורק)
    top_candidate = candidates[0]
    print(f"[PaperTrade] 🚀 Selected top momentum candidate: {top_candidate['ticker']} (Score: {top_candidate['score']:.0f}/100)")
    
    # ניסיון כניסה לפוזיציה (מציב פקודות/חוקי כניסה ב-TradeManager)
    trade_entered = trader.enter_trade(top_candidate)
    
    if not trade_entered:
        print(f"[PaperTrade] ❌ Execution skipped or failed for {top_candidate['ticker']}.")
        return
        
    print(f"[PaperTrade] 🔥 Active position initialized for {top_candidate['ticker']}. Entering monitoring loop...")
    
    # לולאת מעקב, ניהול סיכונים ויציאה (Trailing Stop / Target / Stop Loss)
    # הלולאה תרוץ כל 5 דקות כל עוד יש פוזיציה פתוחה במערכת
    try:
        while True:
            # מעקב ובדיקת יעדי רווח/הפסד
            active_trades = trader.monitor_and_exit()
            
            # מנגנון הגנה: אם אין פוזיציות פתוחות יותר, נסיים את ריצת המערכת להיום
            if not active_trades:
                print("[PaperTrade] 🏁 No active open trades left in portfolio. Closing system cycle.")
                break
                
            print(f"[PaperTrade] [Time: {datetime.now().strftime('%H:%M:%S')}] Monitoring positions... Next check in 5 minutes.")
            time.sleep(300)  # הדמיה/המתנה של 5 דקות בין בדיקה לבדיקה
            
    except KeyboardInterrupt:
        print("[PaperTrade] 🛑 Operational loop stopped manually by operator.")


def run_backtest():
    """Run backtest - מושבת זמנית"""
    print("[Main] Backtest disabled - need to fix data_fetcher")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DAYS-BOT Global Execution Engine")
    parser.add_argument('mode', choices=['full', 'backtest', 'paper'], help="Execution mode for the bot")
    args = parser.parse_args()
    
    if args.mode == 'full':
        run_full_pipeline()
    elif args.mode == 'paper':
        run_paper_trade()
    elif args.mode == 'backtest':
        run_backtest()
