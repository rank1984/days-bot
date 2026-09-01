"""
DAYS-BOT V4.0 – Fast Discovery Engine
Uses daily data to find candidates quickly, even outside PM hours.
"""
from datetime import datetime
from typing import List
import pytz
import pandas as pd
import yfinance as yf
from scanner.universe import load_universe

ET = pytz.timezone("America/New_York")
BATCH_SIZE = 50


def fast_discovery() -> List[dict]:
    """
    Quick discovery using daily data.
    Returns up to 20 candidates based on Gap and RVOL.
    Works 24/7, no PM dependency.
    """
    universe = load_universe()
    if not universe:
        return []

    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")
    candidates = []

    print("[FastDiscovery] Scanning universe for daily movers...")

    for i in range(0, len(universe), BATCH_SIZE):
        batch = universe[i:i+BATCH_SIZE]
        try:
            data = yf.download(" ".join(batch), period="5d", interval="1d", progress=False, threads=False)
            if data.empty:
                continue

            for ticker in batch:
                try:
                    if len(batch) == 1:
                        df = data.copy()
                    else:
                        if ticker not in data.columns.get_level_values(0):
                            continue
                        df = data[ticker].copy()

                    df = df.dropna(subset=['Close', 'Volume'])
                    if len(df) < 2:
                        continue

                    price = float(df['Close'].iloc[-1])
                    prev_close = float(df['Close'].iloc[-2])
                    volume = int(df['Volume'].iloc[-1])
                    avg_volume = int(df['Volume'].iloc[-5:].mean()) if len(df) >= 5 else volume

                    gap_pct = ((price - prev_close) / prev_close) * 100
                    rvol = volume / avg_volume if avg_volume > 0 else 1.0

                    # Filter: basic liquidity and price
                    if price < 1.0 or volume < 50000:
                        continue

                    # Quick score
                    score = 0
                    score += min(max(gap_pct, 0) * 2, 30)
                    score += min(rvol * 5, 25)
                    if gap_pct > 3:
                        score += 15
                    if rvol > 2:
                        score += 15
                    score = round(min(100, max(0, score)), 1)

                    candidate = {
                        "ticker": ticker,
                        "price": price,
                        "prev_close": prev_close,
                        "gap_pct": gap_pct,
                        "pm_volume": volume,
                        "pm_high": price,
                        "pm_low": price,
                        "pm_vwap": price,
                        "pm_dist_signed": 0,
                        "event_score": score,
                        "pm_data_quality": "DAILY_DATA",
                        "mode": "LIVE",
                        "strategy_version": "V4.0",
                        "data_version": "YFINANCE_V40",
                        "scan_date": today,
                        "source": "FAST_DISCOVERY"
                    }
                    candidates.append(candidate)

                except Exception:
                    continue

        except Exception:
            continue

    candidates.sort(key=lambda x: x.get('event_score', 0), reverse=True)
    print(f"[FastDiscovery] Found {len(candidates)} candidates")
    return candidates[:30]
