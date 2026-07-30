"""
Update trade outcomes at the end of the day
"""
import yfinance as yf
from database.trade_db import get_all_trades, update_trade_outcome

def update_daily_results():
    trades = get_all_trades()
    updated = 0
    for trade in trades:
        if trade.get('exit_time'):
            continue
        ticker = trade['ticker']
        try:
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                high = data['High'].max()
                low = data['Low'].min()
                close = data['Close'].iloc[-1]
                update_trade_outcome(ticker, exit_price=close, high=high, low=low, close=close)
                print(f"[Update] ✅ {ticker} updated")
                updated += 1
            else:
                print(f"[Update] ❌ No data for {ticker}")
        except Exception as e:
            print(f"[Update] ❌ {ticker} failed: {e}")
    print(f"[Update] Updated {updated} trades")

if __name__ == "__main__":
    update_daily_results()
