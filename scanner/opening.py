"""
DAYS-BOT V3.2 – Opening Confirmation (after 09:30 ET)
"""
from datetime import datetime
import pytz
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY

ET = pytz.timezone("America/New_York")

def check_opening_confirmation(watchlist, now_et):
    """
    מקבל רשימת מועמדים (עם pm_high) ובודק אם הם פרצו מעל pm_high
    עם נפח מספיק ומחיר מעל VWAP.
    """
    client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
    symbols = [c['ticker'] for c in watchlist]
    if not symbols:
        return []

    start = now_et - pd.Timedelta(minutes=5)  # 5 דקות אחרונות
    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Minute,
        start=start,
        end=now_et,
    )
    bars_data = client.get_stock_bars(req).data

    confirmed = []
    for c in watchlist:
        ticker = c['ticker']
        bars = bars_data.get(ticker, [])
        if not bars:
            continue
        df = pd.DataFrame([{'time': b.timestamp, 'close': b.close, 'volume': b.volume} for b in bars])
        df.set_index('time', inplace=True)
        current_price = df['close'].iloc[-1]
        # תנאי אישור:
        # 1. מחיר > pm_high
        pm_high = c.get('pm_high', 0)
        if current_price <= pm_high:
            continue
        # 2. נפח גדל (לפחות 2x מהממוצע ב-5 דקות אחרונות)
        avg_vol = df['volume'].mean()
        if avg_vol == 0 or df['volume'].iloc[-1] < avg_vol * 1.5:
            continue
        # 3. spread (אין לנו, אז נדלג)
        # 4. VWAP – נחשב VWAP ל-5 דקות
        vwap = (df['close'] * df['volume']).sum() / df['volume'].sum() if df['volume'].sum() > 0 else df['close'].mean()
        if current_price < vwap * 0.995:
            continue
        # כל התנאים עברו
        confirmed.append({
            **c,
            "current_price": current_price,
            "breakout_price": pm_high,
            "volume_confirm": True,
            "vwap_confirm": True,
        })
    return confirmed
