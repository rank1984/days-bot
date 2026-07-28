"""
DAYS-BOT Main Entry Point
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import *
from scanner.premarket import scan_premarket
from scanner.universe import load_universe
from database.db import init_db, save_trade, get_open_trades, update_trade_outcome
from telegram_formatter import format_preopen_list, format_no_candidates, send_message
from trade_manager.trade_manager import TradeManager
from paper_trader.paper_trader import PaperTrader


def update_daily_results():
    """עדכון תוצאות היום – מופעל בסוף היום"""
    print("\n[Main] Updating daily trade results...")
    trades = get_open_trades()
    
    if not trades:
        print("[Main] No open trades to update.")
        return

    for trade in trades:
        ticker = trade['ticker']
        try:
            # שליפת נתונים מ-yfinance עבור היום
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                high = float(data['High'].max())
                low = float(data['Low'].min())
                close = float(data['Close'].iloc[-1])
                
                update_trade_outcome(ticker, exit_price=close, high=high, low=low, close=close)
                print(f"[Main] Updated {ticker}: High=${high:.2f}, Low=${low:.2f}, Close=${close:.2f}")
            else:
                print(f"[Main] ⚠️ No yfinance data found for {ticker}")
        except Exception as e:
            print(f"[Main] ❌ Error updating results for {ticker}: {e}")

    print("[Main] Daily results updated successfully.")


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
        ticker = c.get('ticker') or c.get('symbol', '')
        if '/' in ticker or 'USDC' in ticker or 'USDT' in ticker:
            continue
            
        plan = manager.generate_plan(c)
        if plan:
            plans.append(plan)
    
    trades_taken = len(plans)
    print(f"\n[Main] Trades taken: {trades_taken}")
    print("-" * 30)
    
    # 6. ביצוע העסקאות ושמירה במסד הנתונים
    for plan in plans:
        ticker = plan.get('ticker') or plan.get('symbol', 'UNKNOWN')
        entry = plan.get('entry') or plan.get('price', 0.0)
        stop = plan.get('stop') or plan.get('stop_loss', 0.0)
        tp1 = plan.get('tp1') or plan.get('take_profit', 0.0)
        tp2 = plan.get('tp2', tp1)
        
        print(f"[Main] Entering {ticker} @ ${entry:.2f}")
        
        # ביצוע ב-PaperTrader
        trader.enter_trade(ticker, entry)
        if stop > 0:
            trader.set_stop_loss(ticker, stop)
        if tp1 > 0:
            trader.set_take_profit(ticker, tp1)
        
        if plan.get('runner') and tp2 > 0:
            trader.set_take_profit(ticker, tp2)
        
        # חילוץ נתונים גולמיים בצורה בטוחה
        raw_data = plan.get('raw_data') or plan.get('candidate') or {}
        
        save_trade(
            ticker=ticker,
            entry=entry,
            stop=stop,
            tp1=tp1,
            tp2=tp2,
            rr1=plan.get('rr1', 0.0),
            rr2=plan.get('rr2', 0.0),
            score=plan.get('quality_score') or plan.get('score', 0.0),
            rvol=raw_data.get('rvol', 0.0),
            gap=raw_data.get('gap', 0.0),
            dvol=raw_data.get('dvol', 0.0),
            catalyst=raw_data.get('catalyst', '')
        )
    
    print(f"[Main] Done. {trades_taken} trades executed.")

    # בסוף הריצה (או בשימוש בתזמון נפרד לסוף היום) ניתן לעדכן תוצאות:
    # update_daily_results()


if __name__ == "__main__":
    main()
