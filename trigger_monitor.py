"""
Trigger Monitor – checks watchlist for breakout confirmation
"""
import time
import yfinance as yf
from database.db import DB_PATH
from watchlist_manager import WatchlistManager
import sqlite3

def check_breakout(ticker, pm_high, trigger_price):
    """בודק אם המחיר פרץ מעל ה-Trigger עם אישור נפח"""
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if data.empty:
            return False
        current_price = data['Close'].iloc[-1]
        volume = data['Volume'].iloc[-1]
        avg_volume = data['Volume'].rolling(5).mean().iloc[-1]
        
        if current_price >= trigger_price and volume > avg_volume * 1.2:
            return True
    except:
        pass
    return False

def monitor_trigger():
    wm = WatchlistManager()
    watchlist = wm.get_active_watchlist()
    
    for item in watchlist:
        ticker = item['ticker']
        pm_high = item['pm_high']
        trigger = item['trigger_price']
        status = item['status']
        
        if status == 'EXECUTED':
            continue
        
        if check_breakout(ticker, pm_high, trigger):
            print(f"[Trigger] ✅ {ticker} breakout confirmed!")
            # עדכן סטטוס ל-READY (או EXECUTED)
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                UPDATE watchlist SET status = 'READY'
                WHERE ticker = ? AND status != 'EXECUTED'
            """, (ticker,))
            conn.commit()
            conn.close()
        else:
            print(f"[Trigger] ⏳ {ticker} waiting (Trigger: ${trigger:.2f})")

if __name__ == "__main__":
    monitor_trigger()
