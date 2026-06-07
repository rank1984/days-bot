import pandas as pd
import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest
from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, MIN_GAP_PCT, MIN_PREMARKET_VOL

client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)


def get_avg_volume(ticker: str, days: int = 30) -> float:
    try:
        hist = yf.Ticker(ticker).history(period=f"{days}d")
        if hist.empty:
            return 0.0
        return float(hist["Volume"].mean())
    except Exception:
        return 0.0


def scan_premarket(universe: pd.DataFrame) -> pd.DataFrame:
    tickers = universe["ticker"].tolist()
    results = []

    BATCH = 500
    snapshots = {}
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i : i + BATCH]
        try:
            req  = StockSnapshotRequest(symbol_or_symbols=batch)
            snap = client.get_stock_snapshot(req)
            snapshots.update(snap)
        except Exception as e:
            print(f"[Premarket] Alpaca snapshot error (batch {i}): {e}")

    for _, row in universe.iterrows():
        ticker = row["ticker"]
        snap   = snapshots.get(ticker)
        if snap is None:
            continue

        try:
            pm_bar     = snap.minute_bars[-1] if snap.minute_bars else None
            prev_close = snap.previous_daily_bar.close if snap.previous_daily_bar else None

            if pm_bar is None or prev_close is None or prev_close == 0:
                continue

            pm_price  = pm_bar.close
            pm_volume = pm_bar.volume
            gap_pct   = ((pm_price - prev_close) / prev_close) * 100

            if gap_pct < MIN_GAP_PCT or pm_volume < MIN_PREMARKET_VOL:
                continue

            avg_vol   = get_avg_volume(ticker)
            vol_ratio = (pm_volume / avg_vol) if avg_vol > 0 else 0.0

            results.append({
                "ticker":     ticker,
                "price":      pm_price,
                "prev_close": prev_close,
                "gap_pct":    round(gap_pct, 2),
                "pm_volume":  pm_volume,
                "vol_ratio":  round(vol_ratio, 2),
                "sector":     row.get("sector", ""),
                "industry":   row.get("industry", ""),
            })
        except Exception as e:
            print(f"[Premarket] Error processing {ticker}: {e}")

    df = pd.DataFrame(results)
    print(f"[Premarket] {len(df)} candidates after gap/volume filter.")
    return df
