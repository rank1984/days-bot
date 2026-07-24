"""
DAYS-BOT Main Entry Point
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
from database.db import init_db, save_trade
from telegram_formatter import format_preopen_list, format_no_candidates, send_message
from trade_manager.trade_manager import TradeManager
from paper_trader.paper_trader import PaperTrader


def main():
    # 1. אתחול מסד הנתונים
    init_db()
    
    # 2. אתחול PaperTrader
    trader = PaperTrader()
    
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
    
    # 4. שליחת הודעת מועמדויות לטלגרם
    msg = format_preopen_list(candidates, today)
    send_message(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, msg)
    print(f"[Main] Sent {len(candidates)} candidates summary to Telegram")
    
    # 5. יצירת תוכניות מסחר
    manager = TradeManager()
    plans = []
    for c in candidates[:5]:
        # דילוג על קריפטו
        if '/' in c['ticker'] or 'USDC' in c['ticker'] or 'USDT' in c['ticker']:
            continue
        plan = manager.generate_plan(c)
        if plan:
            plans.append(plan)
    
    trades_taken = len(plans)
    print(f"\n[Main] Trades taken: {trades_taken}")
    print("-" * 30)
    
    for plan in plans:
        ticker = plan['ticker']
        entry = plan['entry']
        print(f"[Main] Entering {ticker} @ ${entry:.2f}")
        
        trader.enter_trade(ticker, entry)
        trader.set_stop_loss(ticker, plan['stop'])
        trader.set_take_profit(ticker, plan['tp1'])
        
        if plan.get('runner'):
            trader.set_take_profit(ticker, plan['tp2'])
        
        save_trade(
            ticker=ticker,
            entry=entry,
            stop=plan['stop'],
            tp1=plan['tp1'],
            tp2=plan['tp2'],
            rr1=plan.get('rr1', 0.0),
            rr2=plan.get('rr2', 0.0),
            score=plan.get('quality_score', 0.0),
            rvol=plan['raw_data'].get('rvol', 0.0),
            gap=plan['raw_data'].get('gap', 0.0),
            dvol=plan['raw_data'].get('dvol', 0.0),
            catalyst=plan['raw_data'].get('catalyst', '')
        )
    
    print(f"[Main] Done. {trades_taken} trades executed.")


if __name__ == "__main__":
    main()
