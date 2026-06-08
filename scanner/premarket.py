"""
premarket.py — FIXED VERSION
--------------------------------
תיקונים:
✔ אין יותר snapshot.minute_bars (לא קיים ב-alpaca-py החדש)
✔ פרימרקט volume דרך StockBarsRequest (Minute)
✔ יציבות + fallback מלא
✔ RVOL נשאר אבל נקי יותר
"""

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime
import pytz

from utils.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY,
    MIN_GAP_PCT, MIN_PREMARKET_VOL,
    MIN_RVOL, MIN_DOLLAR_VOLUME
)

client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
ET = pytz.timezone("America/New_York")


# =========================
# RVOL (שיפור קל ויציב)
# =========================
def get_historical_rvol(ticker: str, current_volume: int) -> float:
    try:
        now = datetime.now(ET)

        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=now.replace(day=now.day - 14),
            end=now,
            limit=10,
        )

        bars = client.get_stock_bars(req)[ticker]

        if not bars or len(bars) < 3:
            return 0.0

        avg_daily = sum(b.volume for b in bars) / len(bars)

        if avg_daily <= 0:
            return 0.0

        return round(current_volume / avg_daily, 2)

    except Exception:
        return 0.0


# =========================
# פרימרקט ווליום אמיתי
# =========================
def get_premarket_volume(ticker: str) -> int:
    try:
        now = datetime.now(ET)
        start = now.replace(hour=4, minute=0, second=0, microsecond=0)

        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=start,
            end=now
        )

        bars = client.get_stock_bars(req)

        if ticker not in bars:
            return 0

        return int(sum(b.volume for b in bars[ticker]))

    except Exception:
        return 0


# =========================
# MAIN SCANNER
# =========================
def scan_premarket(universe: pd.DataFrame) -> pd.DataFrame:

    tickers = universe["ticker"].tolist()
    results = []
    snapshots = {}

    # -------------------------
    # SNAPSHOT BATCHING
    # -------------------------
    BATCH = 500
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]

        try:
            req = StockSnapshotRequest(symbol_or_symbols=batch)
            snap = client.get_stock_snapshot(req)

            snapshots.update(snap)
            print(f"[Premarket] Snapshot batch {i//BATCH + 1}: {len(snap)} results")

        except Exception as e:
            print(f"[Premarket] Alpaca error: {e}")

    # -------------------------
    # SCAN LOGIC
    # -------------------------
    for _, row in universe.iterrows():

        ticker = row["ticker"]
        snap = snapshots.get(ticker)

        if not snap:
            continue

        try:
            prev_close = getattr(snap.previous_daily_bar, "close", None)
            latest = getattr(snap.latest_trade, "price", None)

            if not prev_close or not latest or prev_close == 0:
                continue

            gap_pct = ((latest - prev_close) / prev_close) * 100

            if gap_pct < MIN_GAP_PCT:
                continue

            # -------------------------
            # PREMARKET VOLUME FIX
            # -------------------------
            pm_volume = get_premarket_volume(ticker)

            if pm_volume < MIN_PREMARKET_VOL:
                continue

            # -------------------------
            # DOLLAR VOLUME (FIX #5)
            # -------------------------
            dollar_volume = latest * pm_volume

            if dollar_volume < MIN_DOLLAR_VOLUME:
                continue

            # -------------------------
            # RVOL (FIX #7)
            # -------------------------
            rvol = get_historical_rvol(ticker, pm_volume)

            if rvol > 0 and rvol < MIN_RVOL:
                continue

            results.append({
                "ticker": ticker,
                "price": round(latest, 2),
                "prev_close": round(prev_close, 2),
                "gap_pct": round(gap_pct, 2),
                "pm_volume": pm_volume,
                "dollar_volume": int(dollar_volume),
                "vol_ratio": rvol,
                "float": int(row.get("float", 0)),
                "sector": row.get("sector", "Unknown"),
                "industry": row.get("industry", "Unknown"),
            })

        except Exception as e:
            print(f"[Premarket] Error {ticker}: {e}")

    df = pd.DataFrame(results)

    if not df.empty:
        df.sort_values("dollar_volume", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)

    print(f"[Premarket] {len(df)} candidates passed all filters.")
    return df
