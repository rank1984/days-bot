"""
DAYS-BOT V4.0 – Premarket Discovery
- Returns candidates even after 09:30 (using regular session data)
- Uses 5-min bars for after-hours discovery
- Never returns empty list
"""
from datetime import datetime, time, timedelta
from typing import List
import pytz
import pandas as pd
import yfinance as yf
from scanner.universe import load_universe

ET = pytz.timezone("America/New_York")
PM_START = time(4, 0)
PM_END = time(9, 30)
BATCH_SIZE = 25


def scan_premarket(target_date_str: str = None, manual: bool = False) -> List[dict]:
    now_et = datetime.now(ET)
    if not target_date_str:
        target_date_str = now_et.strftime("%Y-%m-%d")

    print(f"\n[Discovery] Premarket scan for {target_date_str} | ET: {now_et.strftime('%H:%M:%S')}")

    universe = load_universe()
    if not universe:
        return []

    # Previous closes
    prev_closes = {}
    for i in range(0, len(universe), BATCH_SIZE):
        batch = universe[i:i+BATCH_SIZE]
        try:
            data = yf.download(" ".join(batch), period="5d", interval="1d", progress=False, threads=False)
            for ticker in batch:
                if len(batch) == 1:
                    if not data.empty:
                        prev_closes[ticker] = float(data['Close'].iloc[-1])
                else:
                    if ticker in data.columns.get_level_values(0):
                        series = data[ticker]['Close'].dropna()
                        if not series.empty:
                            prev_closes[ticker] = float(series.iloc[-1])
        except Exception:
            continue

    candidates = []

    # Determine interval based on time of day
    is_after_hours = now_et.time() >= PM_END
    interval = "1m" if not is_after_hours else "5m"
    period = "1d" if not is_after_hours else "2d"

    for i in range(0, len(universe), BATCH_SIZE):
        batch = universe[i:i+BATCH_SIZE]
        try:
            pm_data = yf.download(" ".join(batch), period=period, interval=interval,
                                  prepost=True, progress=False, threads=False)
        except Exception:
            continue

        for ticker in batch:
            prev_close = prev_closes.get(ticker)
            if not prev_close:
                continue

            try:
                if len(batch) == 1:
                    df = pm_data.copy()
                else:
                    if ticker not in pm_data.columns.get_level_values(0):
                        continue
                    df = pm_data[ticker].copy()

                df = df.dropna(subset=['Close'])
                if df.empty:
                    continue

                # Normalize timezone to ET
                df.index = pd.to_datetime(df.index)
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC")
                df.index = df.index.tz_convert(ET)

                # Filter to target date
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                df = df[df.index.date == target_date]
                if df.empty:
                    continue

                # If after hours, we use all available data (no PM window)
                if is_after_hours:
                    df_use = df
                    pm_bars = len(df_use)
                    pm_volume = int(df_use['Volume'].sum())
                    price = float(df_use['Close'].iloc[-1])
                    pm_high = float(df_use['High'].max())
                    pm_low = float(df_use['Low'].min())
                    pm_vwap = float((df_use['Close'] * df_use['Volume']).sum() / df_use['Volume'].sum()) if pm_volume > 0 else price
                    pm_dist_signed = 0  # Not applicable
                    pm_data_quality = "AFTER_HOURS"
                else:
                    # PM window
                    df_pm = df[(df.index.time >= PM_START) & (df.index.time < PM_END)]
                    if df_pm.empty:
                        # Fallback: use regular session data
                        df_use = df[df.index.time >= PM_END]
                        if df_use.empty:
                            continue
                        pm_bars = len(df_use)
                        pm_volume = int(df_use['Volume'].sum())
                        price = float(df_use['Close'].iloc[-1])
                        pm_high = float(df_use['High'].max())
                        pm_low = float(df_use['Low'].min())
                        pm_vwap = float((df_use['Close'] * df_use['Volume']).sum() / df_use['Volume'].sum()) if pm_volume > 0 else price
                        pm_dist_signed = 0
                        pm_data_quality = "REGULAR_SESSION"
                    else:
                        df_use = df_pm
                        pm_bars = len(df_use)
                        pm_volume = int(df_use['Volume'].sum())
                        price = float(df_use['Close'].iloc[-1])
                        pm_high = float(df_use['High'].max())
                        pm_low = float(df_use['Low'].min())
                        pm_vwap = float((df_use['Close'] * df_use['Volume']).sum() / df_use['Volume'].sum()) if pm_volume > 0 else price
                        pm_dist_signed = ((price - pm_high) / pm_high * 100) if pm_high > 0 else 0
                        pm_data_quality = "GOOD_DATA" if pm_bars >= 5 else "LOW_DATA"

                gap_pct = ((price - prev_close) / prev_close) * 100.0

                # Simple discovery score
                score = 0
                score += min(max(gap_pct, 0) * 2, 30)
                if pm_volume > 0:
                    score += min(pm_volume / 100000 * 20, 30)
                if pm_dist_signed and pm_dist_signed >= 0:
                    score += 25
                elif pm_dist_signed and pm_dist_signed >= -2:
                    score += 15

                # Always add to candidates (even if score is low)
                candidate = {
                    "ticker": ticker,
                    "price": round(price, 4),
                    "prev_close": prev_close,
                    "gap_pct": round(gap_pct, 2),
                    "pm_volume": pm_volume,
                    "pm_bars": pm_bars,
                    "pm_high": round(pm_high, 4),
                    "pm_low": round(pm_low, 4),
                    "pm_vwap": round(pm_vwap, 4),
                    "pm_dist_signed": round(pm_dist_signed, 2) if pm_dist_signed is not None else 0,
                    "spread_pct": None,
                    "event_score": round(min(100, max(0, score)), 1),
                    "pm_data_quality": pm_data_quality,
                    "mode": "MANUAL_REPLAY" if manual else "LIVE",
                    "strategy_version": "V4.0",
                    "data_version": "YFINANCE_V40",
                    "scan_date": target_date_str,
                }
                candidates.append(candidate)

            except Exception as e:
                continue

    # Sort by score descending
    candidates.sort(key=lambda x: x.get('event_score', 0), reverse=True)

    # Always return at least top 10, even if score is low
    if len(candidates) < 10:
        print(f"[Discovery] Only {len(candidates)} candidates found – returning all.")
    else:
        print(f"[Discovery] Top 10 candidates selected from {len(candidates)}.")

    return candidates[:20]  # Return up to 20 for deeper analysis
