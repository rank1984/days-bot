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
    MAX_FLOAT
)

client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
NY_TZ = pytz.timezone("America/New_York")

MIN_DOLLAR_VOLUME = 1_500_000


def get_premarket_bars(ticker: str) -> list:
    try:
        now_ny          = datetime.now(NY_TZ)
        premarket_start = now_ny.replace(hour=4, minute=0, second=0, microsecond=0)

        if now_ny < premarket_start:
            premarket_start -= timedelta(days=1)
            now_ny = premarket_start.replace(hour=9, minute=30)

        if premarket_start >= now_ny:
            return []

        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=premarket_start,
            end=now_ny,
            feed="iex",
        )
        bars_resp = client.get_stock_bars(req)
        df        = bars_resp.df

        if df is None or df.empty:
            return []

        if hasattr(df.index, "levels"):
            lvl0 = df.index.get_level_values(0)
            if ticker in lvl0:
                return df.loc[ticker].reset_index().to_dict("records")
            return []

        return df.reset_index().to_dict("records")

    except Exception as e:
        print(f"[Premarket] bars error {ticker}: {e}")
        return []


def calc_pm_rvol(pm_volume: int, avg_daily_volume: int) -> float:
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
    float_map   = universe.set_index("ticker")["float"].to_dict() \
                  if "float" in universe.columns else {}

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

            # HARD FILTER 1: Gap מינימום
            gap_pct = ((latest - prev_close) / prev_close) * 100
            if gap_pct < MIN_GAP_PCT:
                continue

            # שאיבת minute bars
            pm_bars   = get_premarket_bars(ticker)
            pm_volume = 0
            pm_high   = latest

            if pm_bars:
                for b in pm_bars:
                    pm_volume += int(b.get("volume", b.get("v", 0)) or 0)
                    h = float(b.get("high", b.get("h", 0)) or 0)
                    if h > pm_high:
                        pm_high = h

            # Fallback לנפח יומי אם אין minute bars
            if pm_volume == 0 and snap.daily_bar:
                pm_volume = int(snap.daily_bar.volume)
                print(f"[INFO] {ticker} fallback to snapshot volume: {pm_volume}")

            # HARD FILTER 2: נפח פרימרקט מינימום
            if pm_volume < MIN_PREMARKET_VOL:
                print(f"[DEBUG] {ticker} gap={gap_pct:.1f}% pm_vol={pm_volume} — low volume")
                continue

            # חישובים
            float_shares  = int(float_map.get(ticker, 0))
            dollar_volume = latest * pm_volume
            avg_vol       = avg_vol_map.get(ticker, 0)
            daily_rvol    = round(pm_volume / avg_vol, 2) if avg_vol > 0 else 0.0
            pm_rvol       = calc_pm_rvol(pm_volume, avg_vol)
            pm_high_dist  = round(((pm_high - latest) / latest) * 100, 2) if latest > 0 else 0.0

            # HARD FILTER 3: Float
            print(f"[FLOAT] {ticker} float={float_shares:,} MAX={MAX_FLOAT:,}")
            if float_shares > MAX_FLOAT and float_shares > 0:
                print(f"[FLOAT] {ticker} filtered — float too large")
                continue
            if float_shares == 0:
                print(f"[FLOAT] {ticker} float=0 — unknown, passing through")

            # HARD FILTER 4: Dollar Volume מינימום $1.5M
            if dollar_volume < MIN_DOLLAR_VOLUME:
                print(f"[DEBUG] {ticker} dvol=${dollar_volume:,.0f} — below $1.5M")
                continue

            # ELITE FILTER: RVOL נמוך + Dollar Volume נמוך = זבל
            if pm_rvol < 1.5 and dollar_volume < 2_000_000:
                print(f"[DEBUG] {ticker} rejected: rvol={pm_rvol} dvol=${dollar_volume:,.0f}")
                continue

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
            print(f"[Premarket] ✅ {ticker} gap={gap_pct:.1f}% "
                  f"pm_vol={pm_volume:,} rvol={pm_rvol}x "
                  f"dvol=${dollar_volume:,.0f}")

        except Exception as e:
            print(f"[Premarket] Error {ticker}: {e}")

    df = pd.DataFrame(results)
    if not df.empty:
        df.sort_values("dollar_volume", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)

    print(f"[Premarket] {len(df)} candidates passed all filters.")
    return df
