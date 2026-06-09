"""
premarket.py V3
----------------
Hard Filters:  gap > 8%, pm_volume > 100K, float < 150M
Soft Scoring:  RVOL משפיע על ציון — לא פוסל
שני RVOL:      daily_rvol + pm_rvol
"""

import requests
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta
import pytz

from utils.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY,
    MIN_GAP_PCT, MIN_PREMARKET_VOL,
    MIN_DOLLAR_VOLUME, MAX_FLOAT
)

client  = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
ET      = pytz.timezone("America/New_York")


def get_premarket_bars(ticker: str) -> list:
    try:
        now_et          = datetime.now(ET)
        premarket_start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=premarket_start,
            end=now_et,
        )
        bars_resp = client.get_stock_bars(req)
        df = bars_resp.df
        if df.empty:
            return []
        if hasattr(df.index, 'levels'):
            if ticker in df.index.get_level_values(0):
                return df.loc[ticker].to_dict("records")
        return df.to_dict("records")
    except Exception as e:
        print(f"[Premarket] bars error {ticker}: {e}")
        return []


def calc_pm_rvol(pm_volume: int, avg_daily_volume: int) -> float:
    """
    Premarket RVOL מנורמל לשעות פרימרקט.
    פרימרקט = 330 דקות, יום מסחר = 390 דקות
    """
    if avg_daily_volume <= 0 or pm_volume <= 0:
        return 0.0
    avg_pm_expected = avg_daily_volume * (330 / 390)
    return round(pm_volume / avg_pm_expected, 2)


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
            print(f"[Premarket] Snapshot batch {i//BATCH+1}: {len(snap)} results")
        except Exception as e:
            print(f"[Premarket] Alpaca error: {e}")

    avg_vol_map = universe.set_index("ticker")["volume"].to_dict()
    float_map   = universe.set_index("ticker")["float"].to_dict() if "float" in universe.columns else {}

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

            # HARD FILTER 1: Gap
            gap_pct = ((latest - prev_close) / prev_close) * 100
            if gap_pct < MIN_GAP_PCT:
                continue

            # שולף premarket bars
            pm_bars   = get_premarket_bars(ticker)
            pm_volume = sum(b.get("volume", b.get("v", 0)) for b in pm_bars) if pm_bars else 0
            pm_high   = max((b.get("high", b.get("h", latest)) for b in pm_bars), default=latest)

            # HARD FILTER 2: Premarket Volume
            if pm_volume < MIN_PREMARKET_VOL:
                print(f"[DEBUG] {ticker} gap={gap_pct:.1f}% pm_vol={pm_volume} — low volume")
                continue

            # HARD FILTER 3: Float
            float_shares = int(float_map.get(ticker, 0))
            if float_shares > MAX_FLOAT and float_shares > 0:
                continue

            # Dollar Volume
            dollar_volume = latest * pm_volume

            # שני RVOL — SOFT
            avg_vol    = avg_vol_map.get(ticker, 0)
            daily_rvol = round(pm_volume / avg_vol, 2) if avg_vol > 0 else 0.0
            pm_rvol    = calc_pm_rvol(pm_volume, avg_vol)

            # מרחק מ-PM High
            pm_high_dist = round(((pm_high - latest) / latest) * 100, 2) if latest > 0 else 0

            results.append({
                "ticker":        ticker,
                "price":         round(latest, 2),
                "prev_close":    round(prev_close, 2),
                "gap_pct":       round(gap_pct, 2),
                "pm_volume":     int(pm_volume),
                "pm_high":       round(pm_high, 2),
                "pm_high_dist":  pm_high_dist,
                "dollar_volume": int(dollar_volume),
                "daily_rvol":    daily_rvol,
                "pm_rvol":       pm_rvol,
                "vol_ratio":     pm_rvol,
                "float":         float_shares,
                "sector":        row.get("sector", "Unknown"),
                "industry":      row.get("industry", "Unknown"),
            })
            print(f"[Premarket] ✅ {ticker} gap={gap_pct:.1f}% pm_vol={pm_volume:,} pm_rvol={pm_rvol}x")

        except Exception as e:
            print(f"[Premarket] Error {ticker}: {e}")

    df = pd.DataFrame(results)
    if not df.empty:
        df.sort_values("dollar_volume", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)

    print(f"[Premarket] {len(df)} candidates passed hard filters.")
    return df
