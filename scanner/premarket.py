"""
premarket.py — Alpaca Premarket Scanner
----------------------------------------
לכל מניה ב-universe:
- שולף snapshot מ-Alpaca
- מחשב Gap%, Premarket Volume, RVOL
- מסנן לפי סף מינימום
"""

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest
from utils.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY,
    MIN_GAP_PCT, MIN_PREMARKET_VOL, MIN_RVOL
)

client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)


def scan_premarket(universe: pd.DataFrame) -> pd.DataFrame:
    """
    קריאה בקבוצות ל-Alpaca Snapshot API.
    מחזיר candidates עם gap, volume, rvol.
    """
    tickers = universe["ticker"].tolist()
    results = []

    # Alpaca מאפשר עד 1000 tickers בקריאה אחת
    BATCH = 500
    snapshots = {}
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i:i + BATCH]
        try:
            req  = StockSnapshotRequest(symbol_or_symbols=batch)
            snap = client.get_stock_snapshot(req)
            snapshots.update(snap)
            print(f"[Premarket] Fetched snapshot batch {i//BATCH + 1} ({len(snap)} results)")
        except Exception as e:
            print(f"[Premarket] Alpaca error batch {i}: {e}")

    # נפח ממוצע מה-universe (Polygon יומי)
    avg_vol_map = universe.set_index("ticker")["volume"].to_dict() if "volume" in universe.columns else {}

    for _, row in universe.iterrows():
        ticker = row["ticker"]
        snap   = snapshots.get(ticker)
        if snap is None:
            continue

        try:
            prev_close = snap.previous_daily_bar.close if snap.previous_daily_bar else None
            latest     = snap.latest_trade.price        if snap.latest_trade     else None

            if prev_close is None or latest is None or prev_close == 0:
                continue

            gap_pct = ((latest - prev_close) / prev_close) * 100

            # נפח premarket מה-minute bar האחרון
            pm_volume = 0
            if snap.minute_bars:
                pm_volume = sum(b.volume for b in snap.minute_bars)

            if gap_pct < MIN_GAP_PCT or pm_volume < MIN_PREMARKET_VOL:
                continue

            # RVOL — נפח יחסי לעומת הממוצע היומי מ-Polygon
            avg_vol  = avg_vol_map.get(ticker, 0)
            rvol     = (pm_volume / (avg_vol / 6.5)) if avg_vol > 0 else 0
            # avg_vol / 6.5 = ממוצע נפח לשעת מסחר

            if rvol < MIN_RVOL:
                continue

            results.append({
                "ticker":     ticker,
                "price":      round(latest, 2),
                "prev_close": round(prev_close, 2),
                "gap_pct":    round(gap_pct, 2),
                "pm_volume":  int(pm_volume),
                "vol_ratio":  round(rvol, 2),
                "sector":     row.get("sector", "Unknown"),
                "industry":   row.get("industry", "Unknown"),
            })

        except Exception as e:
            print(f"[Premarket] Error {ticker}: {e}")

    df = pd.DataFrame(results)
    if not df.empty:
        df.sort_values("gap_pct", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)

    print(f"[Premarket] {len(df)} candidates passed all filters.")
    return df
