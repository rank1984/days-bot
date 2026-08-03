"""
Update trade outcomes at the end of the day
"""
import yfinance as yf
import sqlite3
from datetime import datetime

DB_PATH = "data/alerts.db"

def update_trade_outcome(ticker: str, exit_price: float, high: float, low: float, close: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT id, entry_price, tp1, tp2, stop_price FROM trades
        WHERE ticker = ? AND exit_time IS NULL
        ORDER BY entry_time DESC LIMIT 1
    """, (ticker,))
    row = cursor.fetchone()
    if not row:
        print(f"[Update] No open trade found for {ticker}")
        conn.close()
        return
    
    trade_id, entry, tp1, tp2, stop = row
    pnl = ((exit_price - entry) / entry) * 100 if entry else 0
    win = 1 if pnl > 0 else 0
    tp1_hit = 1 if high >= tp1 else 0
    tp2_hit = 1 if high >= tp2 else 0
    stop_hit = 1 if low <= stop else 0
    
    conn.execute("""
        UPDATE trades SET
            exit_time = ?,
            exit_price = ?,
            high = ?,
            low = ?,
            close = ?,
            pnl = ?,
            win = ?,
            tp1_hit = ?,
            tp2_hit = ?,
            stop_hit = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), exit_price, high, low, close, pnl, win, tp1_hit, tp2_hit, stop_hit, trade_id))
    conn.commit()
    conn.close()
    print(f"[Update] ✅ Updated {ticker}: PnL={pnl:.2f}%")

def update_daily_results():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT ticker FROM trades WHERE exit_time IS NULL
    """)
    trades = cursor.fetchall()
    conn.close()
    
    updated = 0
    for (ticker,) in trades:
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
