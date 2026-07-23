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
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import *
from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_alert, already_sent_today, save_trade
from telegram_formatter import format_preopen_list, format_no_candidates, format_trade_plan, send_message

from trade_manager.trade_manager import TradeManager
from learning.feedback import FeedbackLearner

def process_feedback(learner, candidates_to_add=None):
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

def get_market_regime():
    try:
        spy = yf.Ticker("SPY")
        vix = yf.Ticker("^VIX")
        
        spy_hist = spy.history(period="200d")
        if spy_hist.empty:
            return "NEUTRAL"
            
        spy_50ma = spy_hist['Close'].tail(50).mean()
        spy_200ma = spy_hist['Close'].mean()
        
        spy_current = spy.info.get('regularMarketPrice', spy_hist['Close'].iloc[-1])
        
        vix_hist = vix.history(period="1d")
        vix_current = vix.info.get('regularMarketPrice', vix_hist['Close'].iloc[-1] if not vix_hist.empty else 20)
        
        if spy_current > spy_50ma and spy_50ma > spy_200ma and vix_current < 20:
            return "BULL"
        elif spy_current > spy_200ma and vix_current < 25:
            return "RANGE"
        elif vix_current > 30:
            return "RISK_OFF"
        else:
            return "NEUTRAL"
    except Exception as e:
        print(f"[Warning] Failed to determine market regime: {e}")
        return "NEUTRAL"

def run_full_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[Main] Mode: full (Alert Mode)")
    print(f"=== [DAYS-BOT] {today} {datetime.now().strftime('%H:%M')} ET ===")
    
    init_db()
    learner = FeedbackLearner()
    
    regime = get_market_regime()
    print(f"[Main] Current Market Regime: {regime}")
    if regime == "RISK_OFF":
        print("[Main] RISK OFF – No trades today.")
        return
    
    print("[Main] Scanning...")
    candidates = scan_premarket(today)
    
    if not candidates:
        universe = load_universe()
        msg = format_no_candidates(today, len(universe) if universe else 0)
        send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
        print("[Main] No candidates found")
        process_feedback(learner)
        return

    filtered = []
    for c in candidates:
        if not already_sent_today(c['ticker'], today):
            filtered.append(c)
            
    if not filtered:
        print("[Main] All candidates already sent today")
        process_feedback(learner)
        return

    universe = load_universe()
    msg = format_preopen_list(filtered, today, universe_size=len(universe) if universe else 0)
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
        print(f"[Main] Sent {len(filtered)} candidates summary to Telegram")
        
        # ====== Trade Manager ======
        try:
            # ✅ שלב 1: העברת הבוט ל-Paper Trading
            manager = TradeManager(paper=True)
            plans = []
            
            # ✅ שלב 3: הוספת הלוגים לפסילות + הגדלת הלולאה ל-5 כדי לראות יותר תוצאות
            for c in filtered[:5]:
                if hasattr(manager, 'generate_plan'):
                    plan = manager.generate_plan(c)
                else:
                    plan = None
                
                if plan:
                    print(f"[Main] ✅ Plan created for {c['ticker']} with RR1={plan['rr1']:.2f}")
                    plans.append(plan)
                else:
                    print(f"[Main] ❌ No plan for {c['ticker']} (RR too low or filtered out)")
            
            if not plans:
                print("[Main] No valid trades found by TradeManager after filtering.")
            else:
                for plan in plans:
                    if hasattr(manager, 'get_trade_summary'):
                        plan_msg = manager.get_trade_summary(plan)
                    else:
                        plan_msg = format_trade_plan(plan)
                        
                    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, plan_msg)
                    
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
                        catalyst=plan['raw_data']['catalyst'],
                        pm_high_dist=plan['raw_data'].get('pm_high_dist', 0),
                        news_score=plan['raw_data'].get('news_score', 0),
                        atr=plan['raw_data'].get('atr', 0)
                    )
                    time.sleep(1)
                print(f"[Main] Sent and saved {len(plans)} trade plans")
                
        except Exception as e:
            print(f"[Main Warning] Failed to generate/send trade plans: {e}")

        process_feedback(learner, candidates_to_add=filtered[:5])

def run_paper_trade():
    print("[Main] Paper trade mode selected")

def run_backtest():
    print("[Main] Backtest disabled")

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
