"""
DAYS-BOT Main Entry Point
Integrated with automated Premarket Scanning, Trade Management, and Feedback Learning.
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
from telegram_formatter import format_preopen_list, format_no_candidates, format_trade_plan, send_message

# ייבוא מנהל העסקאות ומנגנון הלמידה
from trade_manager import TradeManager
from learning.feedback import FeedbackLearner
from backtest.daily_backtest import DailyBacktest

# backtester מושבת זמנית
# from backtester.backtester import Backtester


def process_feedback(learner, candidates_to_add=None):
    """פונקציית עזר להרצת בדיקת תוצאות עבר ועדכון הדוח בבטחה"""
    try:
        print("[Feedback] Checking past candidates performance...")
        learner.check_results(days_back=7)
        
        if candidates_to_add:
            for c in candidates_to_add:
                learner.add_candidate(c)
                
        report = learner.generate_report()
        print("\n=== [FEEDBACK LEARNING REPORT] ===")
        print(report)
        print("===================================\n")
    except Exception as e:
        print(f"[Feedback Warning] Failed to update feedback learner: {e}")


def run_full_pipeline():
    """Run the full scan and alert pipeline"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[Main] Mode: full (Alert Mode)")
    print(f"=== [DAYS-BOT] {today} {datetime.now().strftime('%H:%M')} ET ===")
    
    init_db()
    
    # אתחול מנגנון הלמידה ובדיקת תוצאות קודמות
    learner = FeedbackLearner()
    
    # הרצת הסורק המשופר
    universe = load_universe()
    universe_size = len(universe) if universe else 0
    candidates = scan_premarket(today)
    
    if not candidates:
        msg = format_no_candidates(today, universe_size)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        # ניתוח תוצאות העבר גם אם אין מועמדים היום
        process_feedback(learner)
        return

    # סינון מניות שכבר נשלחו היום למניעת כפילויות במובייל
    filtered = [c for c in candidates if not already_sent_today(c['ticker'], today)]
    
    if not filtered:
        print("[Main] All candidates already sent today")
        process_feedback(learner)
        return

    # שליחת רשימת הטופ 5 הכללית לטלגרם
    msg = format_preopen_list(filtered, today, universe_size=universe_size)
    success = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    
    if success:
        # שמירת המועמדים ב-DB
        for c in filtered:
            save_alert(
                ticker=c['ticker'],
                price=c['price'],
                gap_pct=c['gap_pct'],
                score=c.get('score', 0),
                catalyst=c.get('catalyst', '—')
            )
        print(f"[Main] Sent {len(filtered)} candidates summary to Telegram")
        
        # ====== Trade Manager ======
        try:
            manager = TradeManager()
            plans = []
            
            for c in filtered[:3]:  # 3 המובילים
                if hasattr(manager, 'generate_plan'):
                    plan = manager.generate_plan(c)
                else:
                    # יצירת תוכנית ברירת מחדל אם generate_plan לא קיים
                    entry = c.get('price', 0.0)
                    stop = entry * 0.95
                    tp1 = entry * 1.10
                    tp2 = entry * 1.20
                    risk = entry - stop
                    reward = tp1 - entry
                    rr = reward / risk if risk > 0 else 0
                    
                    if rr >= 1.5:
                        plan = {
                            'ticker': c.get('ticker', '???'),
                            'confidence': '🚀 High' if c.get('score', 0) >= 70 else '⚡ Medium',
                            'entry': entry,
                            'stop': stop,
                            'tp1': tp1,
                            'tp2': tp2,
                            'runner': True,
                            'level': c.get('level', 'Breakout'),
                            'score': c.get('score', 0),
                            'rvol': c.get('rvol', 0.0)
                        }
                    else:
                        plan = None
                
                if plan:  # בודק שהתוכנית תקינה (ועומדת ב-RR >= 1.5)
                    plans.append(plan)
            
            if not plans:
                print("[Main] No trades with RR >= 1.5")
            else:
                # שליחת תוכניות המסחר לטלגרם
                for plan in plans:
                    if hasattr(manager, 'get_trade_summary'):
                        plan_msg = manager.get_trade_summary(plan)
                    else:
                        plan_msg = format_trade_plan(plan)
                        
                    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, plan_msg)
                    time.sleep(1)  # השהייה קלה בין שליחות
                print(f"[Main] Sent {len(plans)} trade plans to Telegram")
                
        except Exception as e:
            print(f"[Main Warning] Failed to generate/send trade plans: {e}")

        # עדכון הלמידה עם ה-Top 5 מהסינון הנוכחי
        process_feedback(learner, candidates_to_add=filtered[:5])


def run_paper_trade():
    """
    Paper Trading Mode with Automatic Preopen Scanner and Live Execution/Exit Management
    """
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[Main] Mode: paper (Automated Trading)")
    print(f"=== [DAYS-BOT TRADER] {today} {datetime.now().strftime('%H:%M')} ET ===")
    
    init_db()
    
    # אתחול למידה ובדיקת היסטוריה לפני המסחר
    learner = FeedbackLearner()
    process_feedback(learner)
    
    trader = TradeManager(paper=True)
    
    candidates = scan_premarket(today)
    if not candidates:
        print("[PaperTrade] 😴 No high quality breakout candidates found today. Aborting trade cycle.")
        return
    
    # בחירת המועמדת המובילה ביותר
    top_candidate = candidates[0]
    print(f"[PaperTrade] 🚀 Selected top momentum candidate: {top_candidate['ticker']} (Score: {top_candidate['score']:.0f}/100)")

    # הרצת Backtest יומי למועמדים
    backtest = DailyBacktest()
    for c in candidates[:10]:
        backtest.add_candidate(c)
    
    # הדפסת דוח Backtest
    report = backtest.get_report()
    print(report)
    
    # הוספת המועמדת הנבחרת למערכת הלמידה
    try:
        learner.add_candidate(top_candidate)
    except Exception as e:
        print(f"[PaperTrade Warning] Could not log candidate to learner: {e}")
    
    trade_entered = trader.enter_trade(top_candidate)
    
    if not trade_entered:
        print(f"[PaperTrade] ❌ Execution skipped or failed for {top_candidate['ticker']}.")
        return
        
    print(f"[PaperTrade] 🔥 Active position initialized for {top_candidate['ticker']}. Entering monitoring loop...")
    
    try:
        while True:
            active_trades = trader.monitor_and_exit()
            
            if not active_trades:
                print("[PaperTrade] 🏁 No active open trades left in portfolio. Closing system cycle.")
                break
                
            print(f"[PaperTrade] [Time: {datetime.now().strftime('%H:%M:%S')}] Monitoring positions... Next check in 5 minutes.")
            time.sleep(300)
            
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
