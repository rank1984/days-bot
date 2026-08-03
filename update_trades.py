"""
Update trade outcomes at the end of the day
"""
import yfinance as yf
import sqlite3
from datetime import datetime
import sys
from pathlib import Path

# הוסף את הנתיב לפרויקט
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# ====== השתמש ב-db.py (שעובד עם alerts.db) ======
from database.db import DB_PATH, get_open_trades, update_trade_outcome

def update_daily_results():
    # קבל את כל העסקאות הפתוחות
    trades = get_open_trades()
    
    if not trades:
        print("[Update] No open trades found.")
        return
    
    updated = 0
    for trade in trades:
        ticker = trade['ticker']
        try:
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                high = data['High'].max()
                low = data['Low'].min()
                close = data['Close'].iloc[-1]
                update_trade_outcome(ticker, exit_price=close, high=high, low=low, close=close)
                updated += 1
        except Exception as e:
            print(f"[Update] ❌ {ticker} failed: {e}")
    
    print(f"[Update] Updated {updated} trades")

if __name__ == "__main__":
    update_daily_results()
