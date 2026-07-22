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
from database.db import init_db, save_alert, already_sent_today, save_trade
from telegram_formatter import format_preopen_list, format_no_candidates, format_trade_plan, send_message

# ייבוא מנהל העסקאות ומנגנון הלמידה
from trade_manager import TradeManager
from learning.feedback import FeedbackLearner
from backtest.daily_backtest import DailyBacktest

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

def market_condition_ok():
    """Kill Switch (מצב שוק חלש)"""
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY")
        vix = yf.Ticker("^VIX")
        spy_info = spy.info
        vix_info = vix.info
        
        spy_change = (spy_info['regularMarketPrice'] - spy_info['previousClose']) / spy_info['previousClose'] * 100
        vix_change = (vix_info['regularMarketPrice'] - vix_info['previousClose']) / vix_info['previousClose'] * 100
        
        if spy_change < -1.0 or vix_change > 5.0:
            return False
        return True
    except:
        return True  # אם אין נתונים – נניח שהשוק תקין

def run_full_pipeline():
    """Run the full scan and alert pipeline"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[Main] Mode: full (Alert Mode)")
    print(f"=== [DAYS-BOT] {today} {datetime.now().strftime('%H:%M')} ET ===")
    
    init_db()
    learner = FeedbackLearner()
    
    # 4 סריקות בשעות שונות (סימולציה של סריקות מרובות כדי לצבור Count)
    scan_times = ["08:00", "08:15", "08:30", "08:45"]
    all_candidates = {}
    
    for t in scan_times:
        print(f"[Main] Scanning at {t} ET...")
        candidates = scan_premarket(today)
        for c in candidates:
            ticker = c['ticker']
            if ticker not in all_candidates:
                all_candidates[ticker] = {'count': 0, 'data': c}
            all_candidates[ticker]['count'] += 1
            
    # סנן רק מניות שהופיעו ב-2+ סריקות
    filtered = []
    for ticker, info in all_candidates.items():
        if info['count'] >= 2:
            filtered.append(info['data'])
            
    if not filtered:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No consistent candidates")
        process_feedback(learner)
        return
        
    # Kill switch בדיקת תנאי שוק
    if not market_condition_ok():
        print("[Main] Market conditions poor. Kill Switch Activated. No trades.")
        return

    # סינון מניות שכבר נשלחו היום למניעת כפילויות במובייל
    filtered_new = [c for c in filtered if not already_sent_today(c['ticker'], today)]
    
    if not filtered_new:
        print("[Main] All candidates already sent today")
        process_feedback(learner)
        return

    # שליחת רשימת הטופ 5 הכללית לטלגרם
    universe = load_universe()
    msg = format_preopen_list(filtered_new, today, universe_size=len(universe) if universe else 0)
    success = send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    
    if success:
        # שמירת המועמדים ב-DB
        for c in filtered_new:
            save_alert(
                ticker=c['ticker'],
                price=c['price'],
                gap_pct=c['gap_pct'],
                score=c.get('score', 0),
                catalyst=c.get('catalyst', '—')
            )
        print(f"[Main] Sent {len(filtered_new)} candidates summary to Telegram")
        
        # ====== Trade Manager ======
        try:
            manager = TradeManager()
            plans = []
            
            for c in filtered_new[:3]:  # 3 המובילים
                if hasattr(manager, 'generate_plan'):
                    plan = manager.generate_plan(c)
                else:
                    plan = None
                
                if plan:  # בודק שהתוכנית תקינה
                    plans.append(plan)
            
            if not plans:
                print("[Main] No trades with RR >= 1.5")
            else:
                # שליחת תוכניות המסחר לטלגרם ושמירה
                for plan in plans:
                    if hasattr(manager, 'get_trade_summary'):
                        plan_msg = manager.get_trade_summary(plan)
                    else:
                        plan_msg = format_trade_plan(plan)
                        
                    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, plan_msg)
                    
                    # שמירת כל עסקה ללמידה
                    save_trade(
                        ticker=plan['ticker'],
                        entry=plan['entry'],
                        stop=plan['stop'],
                        tp1=plan['tp1'],
                        tp2=plan['tp2'],
                        rr1=plan['rr1'],
                        rr2=plan['rr2'],
                        score=plan.get('quality_score', 0),
                        rvol=plan['raw_data']['rvol'],
                        gap=plan['raw_data']['gap'],
                        dvol=plan['raw_data']['dvol'],
                        catalyst=plan['raw_data']['catalyst']
                    )
                    time.sleep(1)  # השהייה קלה בין שליחות
                print(f"[Main] Sent and saved {len(plans)} trade plans")
                
        except Exception as e:
            print(f"[Main Warning] Failed to generate/send trade plans: {e}")

        # עדכון הלמידה עם ה-Top 5 מהסינון הנוכחי
        process_feedback(learner, candidates_to_add=filtered_new[:5])

def run_paper_trade():
    """Paper Trading Mode"""
    print("[Main] Paper trade mode selected (Placeholder)")

def run_backtest():
    """Run backtest"""
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
