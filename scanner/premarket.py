"""
DAYS-BOT V3.0 – Premarket Scanner (Keyless / yfinance)
======================================================

Experiment rules:
1. Discovery is the hard candidate generator (using yfinance).
2. PM data comes from Yahoo Finance (1m bars, prepost=True).
3. PM bars are QUALITY metadata, not a hard gate.
4. RVOL is informational only.
5. Spread is mocked to 0 (yfinance doesn't provide reliable premarket L1 bid/ask).
6. Signed PM distance is preserved.
7. Every candidate receives experiment metadata.
8. No live trading is executed here.
"""

from datetime import datetime, time
from typing import List
import pytz
import pandas as pd
import yfinance as yf

from scanner.universe import load_universe
from utils.config import (
    BOT_VERSION,
    DATA_VERSION,
    DISCOVERY_MAX_GAP,
    DISCOVERY_MAX_PRICE,
    DISCOVERY_MIN_GAP,
    DISCOVERY_MIN_PRICE,
    EXPERIMENT_MODE,
    STRATEGY_VERSION,
    VALIDATION_MAX_PM_DIST,
    VALIDATION_MAX_SPREAD,
    VALIDATION_MIN_PM_BARS,
    VALIDATION_MIN_PM_VOLUME_ABS,
    VALIDATION_MIN_VWAP_DIST,
)

ET = pytz.timezone("America/New_York")


def scan_premarket(target_date_str: str = None) -> List[dict]:
    now_et = datetime.now(ET)

    if target_date_str is None:
        target_date_str = now_et.strftime("%Y-%m-%d")

    print()
    print("=" * 70)
    print(
        f"[Premarket] {BOT_VERSION} "
        f"| mode={EXPERIMENT_MODE} "
        f"| strategy={STRATEGY_VERSION} "
        f"| data=YFINANCE_KEYLESS"
    )
    print(
        f"[Premarket] Date={target_date_str} "
        f"| Now ET={now_et.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("=" * 70)

    # ------------------------------------------------------------
    # UNIVERSE
    # ------------------------------------------------------------

    universe = load_universe()

    if not universe:
        print("[Premarket] ❌ Universe is empty.")
        return []

    # ------------------------------------------------------------
    # STEP 1: PRE-FETCH PREVIOUS CLOSES (FAST DAILY BATCH)
    # ------------------------------------------------------------
    print("[Premarket] Fetching previous daily closes for discovery...")
    # Fetch 5 days to ensure we get the last valid close even after a long weekend
    daily_data = yf.download(
        " ".join(universe), 
        period="5d", 
        interval="1d", 
        progress=False,
        threads=True
    )
    
    prev_closes = {}
    if isinstance(daily_data.columns, pd.MultiIndex):
        for ticker in universe:
            if ticker in daily_data['Close']:
                series = daily_data['Close'][ticker].dropna()
                if not series.empty:
                    # We take the second to last element if today's market is open, 
                    # but if we are in PM, the last valid close is yesterday's.
                    prev_closes[ticker] = float(series.iloc[-1])
    else:
        # Edge case if universe has only 1 symbol
        series = daily_data['Close'].dropna()
        if not series.empty:
            prev_closes[universe[0]] = float(series.iloc[-1])

    print(f"[Premarket] Found previous closes for {len(prev_closes):,} symbols.")

    # ------------------------------------------------------------
    # DISCOVERY STATS
    # ------------------------------------------------------------

    stats = {
        "total": len(universe),
        "no_data": 0,
        "price_pass": 0,
        "price_fail": 0,
        "gap_pass": 0,
        "gap_fail": 0,
        "spread_pass": 0,
        "discovery_pass": 0,
    }

    validated_candidates = []
    
    pm_start_time = time(4, 0)
    pm_end_time = time(9, 30)

    # ------------------------------------------------------------
    # STEP 2: DISCOVERY & PM VALIDATION (1-MIN BATCHES)
    # ------------------------------------------------------------
    
    batch_size = 150
    for i in range(0, len(universe), batch_size):
        batch = universe[i : i + batch_size]
        
        try:
            # Download 1-minute data including premarket
            pm_data = yf.download(
                " ".join(batch), 
                period="1d", 
                interval="1m", 
                prepost=True, 
                group_by="ticker", 
                progress=False,
                threads=True
            )
        except Exception as e:
            print(f"[Discovery] Batch error {i}-{i + len(batch)}: {e}")
            continue

        for ticker in batch:
            prev_close = prev_closes.get(ticker)
            if not prev_close:
                stats["no_data"] += 1
                continue

            try:
                # Extract ticker dataframe
                if isinstance(pm_data.columns, pd.MultiIndex):
                    if ticker not in pm_data.columns.get_level_values(0):
                        stats["no_data"] += 1
                        continue
                    df = pm_data[ticker].dropna(subset=['Close'])
                else:
                    df = pm_data.dropna(subset=['Close'])

                if df.empty:
                    stats["no_data"] += 1
                    continue

                # --- DISCOVERY ---
                # Current price is the close of the latest 1-min bar
                price = float(df['Close'].iloc[-1])

                if price < DISCOVERY_MIN_PRICE or price > DISCOVERY_MAX_PRICE:
                    stats["price_fail"] += 1
                    continue
                stats["price_pass"] += 1

                gap_pct = ((price - prev_close) / prev_close) * 100.0

                if gap_pct < DISCOVERY_MIN_GAP or gap_pct > DISCOVERY_MAX_GAP:
                    stats["gap_fail"] += 1
                    continue
                stats["gap_pass"] += 1

                # yfinance does not provide bid/ask spread during bulk download
                spread_pct = 0.0
                stats["spread_pass"] += 1
                stats["discovery_pass"] += 1

                # --- PM VALIDATION ---
                # Filter dataframe for Premarket times (04:00 - 09:30 ET)
                df_pm = df[(df.index.time >= pm_start_time) & (df.index.time < pm_end_time)]

                if df_pm.empty:
                    continue

                pm_bars_count = len(df_pm)
                pm_volume = int(df_pm['Volume'].sum())

                if pm_volume == 0:
                    continue

                pm_high = float(df_pm['High'].max())
                pm_low = float(df_pm['Low'].min())
                total_volume = df_pm['Volume'].sum()

                if total_volume > 0:
                    pm_vwap = float((df_pm['Close'] * df_pm['Volume']).sum() / total_volume)
                else:
                    pm_vwap = float(df_pm['Close'].mean())

                if pm_high > 0:
                    pm_dist_signed = ((price - pm_high) / pm_high) * 100.0
                else:
                    pm_dist_signed = None

                pm_high_dist = max(0.0, pm_dist_signed) if pm_dist_signed is not None else None

                if pm_bars_count >= VALIDATION_MIN_PM_BARS and pm_volume >= VALIDATION_MIN_PM_VOLUME_ABS:
                    pm_data_quality = "GOOD_DATA"
                elif pm_bars_count > 0:
                    pm_data_quality = "LOW_DATA"
                else:
                    pm_data_quality = "NO_DATA"

                print(
                    f"[PM RESULT] {ticker}"
                    f" | Bars={pm_bars_count}"
                    f" | Vol={pm_volume:,}"
                    f" | High={pm_high:.2f}"
                    f" | VWAP={pm_vwap:.2f}"
                    f" | DistSigned={pm_dist_signed:.2f}%"
                    f" | quality={pm_data_quality}"
                )

                if pm_dist_signed is None or pm_dist_signed < -VALIDATION_MAX_PM_DIST:
                    continue

                if pm_vwap <= 0:
                    continue

                vwap_required_price = pm_vwap * (1.0 + VALIDATION_MIN_VWAP_DIST)
                if price < vwap_required_price:
                    continue

                # --- SCORING ---
                event_score = 0.0
                event_score += min(max(gap_pct, 0.0) * 2.0, 30.0)
                if pm_volume > 0:
                    event_score += min((pm_volume / 100_000.0) * 20.0, 30.0)

                if pm_dist_signed >= 0:
                    event_score += 25.0
                elif pm_dist_signed >= -2.0:
                    event_score += 15.0
                elif pm_dist_signed >= -5.0:
                    event_score += 5.0

                if spread_pct <= 1.0:
                    event_score += 10.0

                event_score = round(min(100.0, max(0.0, event_score)), 1)

                if event_score >= 70:
                    grade = "A"
                elif event_score >= 55:
                    grade = "B"
                elif event_score >= 40:
                    grade = "C"
                else:
                    grade = "WATCH"

                candidate = {
                    "ticker": ticker,
                    "price": price,
                    "prev_close": prev_close,
                    "gap_pct": gap_pct,
                    "spread_pct": spread_pct,
                    "pm_volume": pm_volume,
                    "pm_bars": pm_bars_count,
                    "pm_bars_count": pm_bars_count,
                    "pm_high": pm_high,
                    "pm_low": pm_low,
                    "pm_vwap": pm_vwap,
                    "pm_dist_signed": pm_dist_signed,
                    "pm_high_dist": pm_high_dist,
                    "pm_data_quality": pm_data_quality,
                    "pm_data_error": None,
                    "rvol": None,
                    "rvol_status": "UNAVAILABLE",
                    "event_score": event_score,
                    "grade": grade,
                    "state": "WATCH",
                    "mode": EXPERIMENT_MODE,
                    "strategy_version": STRATEGY_VERSION,
                    "data_version": "YFINANCE_KEYLESS",
                }

                validated_candidates.append(candidate)

            except Exception as e:
                # Silently catch symbol-specific parsing errors
                continue

        # Print progress
        print(f"[Discovery] Processed {min(i + batch_size, len(universe)):,}/{len(universe):,}")

    # ------------------------------------------------------------
    # REPORTS
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("📊 DISCOVERY NEAR-MISS REPORT")
    print("=" * 70)
    print(f"Universe:       {stats['total']:,}")
    print(f"No Data:        {stats['no_data']:,}")
    print(f"Price pass:     {stats['price_pass']:,} | fail: {stats['price_fail']:,}")
    print(f"Gap pass:       {stats['gap_pass']:,} | fail: {stats['gap_fail']:,}")
    print(f"Spread pass:    {stats['spread_pass']:,} (Mocked)")
    print(f"Discovery pass: {stats['discovery_pass']:,}")
    print("=" * 70)

    print()
    print("=" * 70)
    print("📊 PREMARKET SCAN V3.0 – KEYLESS MODE")
    print("=" * 70)
    print(f"Discovery candidates: {stats['discovery_pass']:,}")
    print(f"PM validated:         {len(validated_candidates):,}")

    good_data = sum(1 for c in validated_candidates if c.get("pm_data_quality") == "GOOD_DATA")
    low_data = sum(1 for c in validated_candidates if c.get("pm_data_quality") == "LOW_DATA")

    print(f"GOOD_DATA: {good_data:,} | LOW_DATA: {low_data:,}")
    print(f"FINAL: {len(validated_candidates):,}")
    print("=" * 70)

    validated_candidates.sort(
        key=lambda x: (x.get("event_score", 0.0), x.get("gap_pct", 0.0)),
        reverse=True,
    )

    return validated_candidates[:20]
