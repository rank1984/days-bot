"""
Update trade outcomes at the end of the day
"""
import yfinance as yf
import sqlite3
from datetime import datetime

DB_PATH = "data/alerts.db"  # שים לב – alerts.db, לא trades.db

def get_open_trades():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT * FROM alerts 
        WHERE exit_time IS NULL 
        ORDER BY sent_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_trade_outcome(ticker: str, exit_price: float, high: float, low: float, close: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        SELECT id, price, gap_pct FROM alerts
        WHERE ticker = ? AND exit_time IS NULL
        ORDER BY sent_at DESC LIMIT 1
    """, (ticker,))
    row = cursor.fetchone()
    if not row:
        print(f"[Update] No open trade found for {ticker}")
        conn.close()
        return
    
    trade_id, entry, gap = row
    pnl = ((exit_price - entry) / entry) * 100 if entry else 0
    win = 1 if pnl > 0 else 0
    
    conn.execute("""
        UPDATE alerts SET
            exit_time = ?,
            exit_price = ?,
            high = ?,
            low = ?,
            close = ?,
            pnl = ?,
            win = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), exit_price, high, low, close, pnl, win, trade_id))
    conn.commit()
    conn.close()
    print(f"[Update] ✅ Updated {ticker}: PnL={pnl:.2f}%")

def update_daily_results():
    trades = get_open_trades()
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
