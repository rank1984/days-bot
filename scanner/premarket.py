"""
premarket.py — שדרוגים #5 + #7 (תיקון Feed פרימרקט)
--------------------------------
#5: Dollar Volume = price × volume
#7: RVOL אמיתי = volume עכשיו / ממוצע באותה שעה
"""

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed  # <-- הוספת ה-Enum של הפידים
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
    שולף נפח פרימרקט מ-04:00 עד עכשיו עם פיד מפורש (IEX).
    """
    try:
        now_et          = datetime.now(ET)
        premarket_start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)

        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=premarket_start,
            end=now_et,
            feed=DataFeed.IEX  # <-- תיקון: הגדרת פיד מפורש לחשבונות חינמיים/Paper
        )
        bars = client.get_stock_bars(req)
        
        # גישה בטוחה ישירות למילון הנתונים ללא סיכון לקריסת אינדקסים
        ticker_bars = bars.data.get(ticker) if (bars and hasattr(bars, "data")) else None

        if not ticker_bars:
            print(f"[DEBUG-VOL] {ticker} no bars returned")
            return 0
            
        total = int(sum(b.volume for b in ticker_bars))
        print(f"[DEBUG-VOL] {ticker} bars={len(ticker_bars)} vol={total}")
        return total
        
    except Exception as e:
        print(f"[DEBUG-VOL] {ticker} exception: {e}")
        return 0


def get_historical_rvol(ticker: str, current_volume: int) -> float:
    """
    שדרוג #7: RVOL אמיתי — משווה לאותה שעה בימים קודמים.
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
            feed=DataFeed.IEX  # <-- מיושר לפי אותו פיד של פרימרקט
        )
        bars = client.get_stock_bars(req)
        
        ticker_bars = bars.data.get(ticker) if (bars and hasattr(bars, "data")) else None

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
    except Exception as e:
        print(f"[DEBUG ERROR] Failed to get RVOL for {ticker}: {e}")
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

            # קריאה לפונקציה המעודכנת
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
