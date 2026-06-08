"""
premarket.py — שדרוגים #5 + #7
--------------------------------
#5: Dollar Volume = price × volume (לא רק volume)
#7: RVOL אמיתי = volume עכשיו / ממוצע באותה שעה

תיקון: Alpaca הסיר snap.minute_bars — שולפים נפח פרימרקט דרך get_stock_bars
"""

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import pytz

from utils.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY,
    MIN_GAP_PCT, MIN_PREMARKET_VOL,
    MIN_RVOL, MIN_DOLLAR_VOLUME
)

client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
ET     = pytz.timezone("America/New_York")


def get_premarket_volume(ticker: str) -> int:
    """
    שולף נפח פרימרקט מ-04:00 עד עכשיו דרך get_stock_bars.
    מחליף את snap.minute_bars שהוסר מה-API.
    """
    try:
        now_et          = datetime.now(ET)
        premarket_start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)

        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=premarket_start,
            end=now_et,
        )
        bars = client.get_stock_bars(req)
        ticker_bars = bars.get(ticker) if hasattr(bars, "get") else bars[ticker] if ticker in bars else None
        if not ticker_bars:
            return 0
        return int(sum(b.volume for b in ticker_bars))
    except Exception:
        return 0


def get_historical_rvol(ticker: str, current_volume: int) -> float:
    """
    שדרוג #7: RVOL אמיתי — משווה לאותה שעה בימים קודמים.
    שולף 10 ימים אחרונים ומחשב ממוצע volume עד שעה זו.
    """
    try:
        now_et    = datetime.now(ET)
        start     = now_et - timedelta(days=14)
        req       = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start,
            end=now_et,
            limit=10,
        )
        bars = client.get_stock_bars(req)
        ticker_bars = bars.get(ticker) if hasattr(bars, "get") else bars[ticker] if ticker in bars else None
        if not ticker_bars or len(ticker_bars) < 3:
            return 0.0

        avg_daily = sum(b.volume for b in ticker_bars[:-1]) / len(ticker_bars[:-1])

        premarket_start = now_et.replace(hour=4, minute=0, second=0)
        minutes_elapsed = (now_et - premarket_start).total_seconds() / 60
        pct_of_day      = min(minutes_elapsed / (6.5 * 60 + 330), 1.0)

        expected_volume = avg_daily * pct_of_day
        if expected_volume <= 0:
            return 0.0

        return round(current_volume / expected_volume, 2)
    except Exception:
        return 0.0


def scan_premarket(universe: pd.DataFrame) -> pd.DataFrame:
    tickers   = universe["ticker"].tolist()
    results   = []
    snapshots = {}

    BATCH = 500
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        try:
            req  = StockSnapshotRequest(symbol_or_symbols=batch)
            snap = client.get_stock_snapshot(req)
            snapshots.update(snap)
            print(f"[Premarket] Snapshot batch {i//BATCH + 1}: {len(snap)} results")
        except Exception as e:
            print(f"[Premarket] Alpaca error: {e}")

    for _, row in universe.iterrows():
        ticker = row["ticker"]
        snap   = snapshots.get(ticker)
        if snap is None:
            continue

        try:
            prev_close = snap.previous_daily_bar.close if snap.previous_daily_bar else None
            latest     = snap.latest_trade.price        if snap.latest_trade     else None

            if not prev_close or not latest or prev_close == 0:
                continue

            gap_pct = ((latest - prev_close) / prev_close) * 100
            if gap_pct < MIN_GAP_PCT:
                continue

            # תיקון: שולפים נפח פרימרקט דרך API במקום snap.minute_bars
            pm_volume = get_premarket_volume(ticker)

            if pm_volume < MIN_PREMARKET_VOL:
                continue

            # שדרוג #5 — Dollar Volume
            dollar_volume = latest * pm_volume
            if dollar_volume < MIN_DOLLAR_VOLUME:
                continue

            # שדרוג #7 — RVOL אמיתי
            rvol = get_historical_rvol(ticker, pm_volume)
            if rvol > 0 and rvol < MIN_RVOL:
                continue

            results.append({
                "ticker":        ticker,
                "price":         round(latest, 2),
                "prev_close":    round(prev_close, 2),
                "gap_pct":       round(gap_pct, 2),
                "pm_volume":     int(pm_volume),
                "dollar_volume": int(dollar_volume),
                "vol_ratio":     rvol,
                "float":         int(row.get("float", 0)),
                "sector":        row.get("sector", "Unknown"),
                "industry":      row.get("industry", "Unknown"),
            })

        except Exception as e:
            print(f"[Premarket] Error {ticker}: {e}")

    df = pd.DataFrame(results)
    if not df.empty:
        df.sort_values("dollar_volume", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)

    print(f"[Premarket] {len(df)} candidates passed all filters.")
    return df
