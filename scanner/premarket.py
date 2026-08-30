"""
DAYS-BOT V3.2 – Premarket Scanner (yfinance, batch size 50)
"""
import pandas as pd
from datetime import datetime, time, timedelta
import pytz
from typing import List
import yfinance as yf

from scanner.universe import load_universe
from utils.config import (
    DISCOVERY_MIN_PRICE, DISCOVERY_MAX_PRICE,
    DISCOVERY_MIN_GAP, DISCOVERY_MAX_GAP,
    VALIDATION_MIN_PM_VOLUME_ABS,
    VALIDATION_MAX_PM_DIST,
    VALIDATION_MIN_VWAP_DIST
)

ET = pytz.timezone("America/New_York")


def scan_premarket(target_date_str: str = None) -> List[dict]:
    now_et = datetime.now(ET)
    if target_date_str is None:
        target_date_str = now_et.strftime("%Y-%m-%d")

    print(f"[Premarket V3.2] Scanning at {now_et.strftime('%H:%M:%S')} ET")

    universe = load_universe()
    if not universe:
        return []

    # PM window
    pm_start = ET.localize(datetime.combine(now_et.date(), time(4, 0)))
    pm_end = min(now_et, ET.localize(datetime.combine(now_et.date(), time(9, 30))))

    # שלב 1: סגירות קודמות (5 ימים) – בבתים של 50
    prev_closes = {}
    batch_size = 50
    for i in range(0, len(universe), batch_size):
        batch = universe[i:i+batch_size]
        try:
            data = yf.download(" ".join(batch), period="5d", interval="1d", progress=False, threads=False)
            # אם רק מניה אחת, data הוא Series
            if len(batch) == 1:
                if not data.empty:
                    prev_closes[batch[0]] = data['Close'].iloc[-1]
            else:
                # MultiIndex
                for ticker in batch:
                    if ticker in data['Close']:
                        series = data['Close'][ticker].dropna()
                        if not series.empty:
                            prev_closes[ticker] = float(series.iloc[-1])
        except Exception as e:
            print(f"[Premarket] Batch error (daily) for {batch}: {e}")
            continue

    print(f"[Premarket] Found {len(prev_closes)} previous closes.")

    # שלב 2: PM 1-min data – בבתים של 50
    candidates = []
    for i in range(0, len(universe), batch_size):
        batch = universe[i:i+batch_size]
        try:
            pm_data = yf.download(
                " ".join(batch),
                period="1d",
                interval="1m",
                prepost=True,
                progress=False,
                threads=False
            )
        except Exception as e:
            print(f"[Premarket] PM data error for batch: {e}")
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
                    df = pm_data[ticker].dropna(subset=['Close'])

                if df.empty:
                    continue

                # טיפול ב-TimeZone
                df.index = pd.to_datetime(df.index)
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC")
                df.index = df.index.tz_convert(ET)

                # סינון עד now_et
                df = df[df.index <= now_et]
                if df.empty:
                    continue

                price = float(df['Close'].iloc[-1])

                # Hard Filters
                if price < DISCOVERY_MIN_PRICE or price > DISCOVERY_MAX_PRICE:
                    continue
                gap_pct = ((price - prev_close) / prev_close) * 100
                if gap_pct < DISCOVERY_MIN_GAP or gap_pct > DISCOVERY_MAX_GAP:
                    continue

                # PM window
                df_pm = df[(df.index >= pm_start) & (df.index < pm_end)]
                if df_pm.empty:
                    continue
                pm_volume = int(df_pm['Volume'].sum())
                if pm_volume < VALIDATION_MIN_PM_VOLUME_ABS:
                    continue
                pm_high = float(df_pm['High'].max())
                pm_low = float(df_pm['Low'].min())
                total_vol = df_pm['Volume'].sum()
                if total_vol > 0:
                    pm_vwap = float((df_pm['Close'] * df_pm['Volume']).sum() / total_vol)
                else:
                    pm_vwap = float(df_pm['Close'].mean())

                pm_dist_signed = ((price - pm_high) / pm_high) * 100 if pm_high > 0 else None
                if pm_dist_signed is None or pm_dist_signed < -VALIDATION_MAX_PM_DIST:
                    continue
                if price < pm_vwap * (1 + VALIDATION_MIN_VWAP_DIST):
                    continue

                # Score (פשוט)
                score = 0.0
                score += min(max(gap_pct, 0) * 2, 30)
                score += min((pm_volume / 100_000) * 20, 30)
                if pm_dist_signed >= 0:
                    score += 25
                elif pm_dist_signed >= -2:
                    score += 15
                elif pm_dist_signed >= -5:
                    score += 5
                score = round(min(100, max(0, score)), 1)

                grade = "A" if score >= 70 else "B" if score >= 55 else "C" if score >= 40 else "WATCH"

                candidate = {
                    "ticker": ticker,
                    "price": price,
                    "gap_pct": gap_pct,
                    "pm_volume": pm_volume,
                    "pm_high": pm_high,
                    "pm_low": pm_low,
                    "pm_vwap": pm_vwap,
                    "pm_dist_signed": pm_dist_signed,
                    "opportunity_score": score,
                    "grade": grade,
                    "state": "WATCH",
                    "spread_pct": None,
                    "spread_status": "UNAVAILABLE",
                    "pm_data_quality": "GOOD_DATA",
                    "mode": "V3.2",
                    "strategy_version": "V3.2",
                    "data_version": "YFINANCE"
                }
                candidates.append(candidate)

            except Exception as e:
                # Skip individual symbol errors
                continue

    candidates.sort(key=lambda x: x['opportunity_score'], reverse=True)
    return candidates[:20]
