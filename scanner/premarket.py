"""
DAYS-BOT V3.1 – Premarket Scanner (Keyless / yfinance)
======================================================

V3.1 fixes:
- spread_pct = None (not 0)
- PM window uses full timestamps, UTC->ET conversion
- price is taken from data up to now_et only
- spread_status = "UNAVAILABLE"
- opportunity_score replaces event_score (kept for compatibility)
"""

from datetime import datetime, time, timedelta
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
                    prev_closes[ticker] = float(series.iloc[-1])
    else:
        series = daily_data['Close'].dropna()
        if not series.empty and len(universe) > 0:
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

    # PM window: 04:00 ET up to min(now_et, 09:30 ET)
    pm_start = ET.localize(
        datetime.combine(now_et.date(), time(4, 0))
    )
    pm_end = min(
        now_et,
        ET.localize(
            datetime.combine(now_et.date(), time(9, 30))
        )
    )

    # ------------------------------------------------------------
    # STEP 2: DISCOVERY & PM VALIDATION (1-MIN BATCHES)
    # ------------------------------------------------------------

    batch_size = 150
    for i in range(0, len(universe), batch_size):
        batch = universe[i : i + batch_size]

        try:
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

                # --- CRITICAL FIX: Ensure timezone and filter up to now_et ---
                df.index = pd.to_datetime(df.index)
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC")
                df.index = df.index.tz_convert(ET)

                # Keep only bars up to current time (no future data)
                df = df[df.index <= now_et]

                if df.empty:
                    stats["no_data"] += 1
                    continue

                # Current price is the last available close (up to now_et)
                price = float(df['Close'].iloc[-1])

                # --- DISCOVERY ---
                if price < DISCOVERY_MIN_PRICE or price > DISCOVERY_MAX_PRICE:
                    stats["price_fail"] += 1
                    continue
                stats["price_pass"] += 1

                gap_pct = ((price - prev_close) / prev_close) * 100.0

                if gap_pct < DISCOVERY_MIN_GAP or gap_pct > DISCOVERY_MAX_GAP:
                    stats["gap_fail"] += 1
                    continue
                stats["gap_pass"] += 1

                # --- SPREAD: unavailable from yfinance ---
                spread_pct = None
                spread_status = "UNAVAILABLE"
                stats["spread_pass"] += 1
                stats["discovery_pass"] += 1

                # --- PM VALIDATION ---
                # Filter df to PM window using full timestamps
                df_pm = df[(df.index >= pm_start) & (df.index < pm_end)]

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

                # Quality flag
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

                # Hard filters
                if pm_dist_signed is None or pm_dist_signed < -VALIDATION_MAX_PM_DIST:
                    continue

                if pm_vwap <= 0:
                    continue

                vwap_required_price = pm_vwap * (1.0 + VALIDATION_MIN_VWAP_DIST)
                if price < vwap_required_price:
                    continue

                # --- OPPORTUNITY SCORE (was event_score) ---
                score = 0.0
                # Gap contribution
                score += min(max(gap_pct, 0.0) * 2.0, 30.0)
                # Volume contribution
                if pm_volume > 0:
                    score += min((pm_volume / 100_000.0) * 20.0, 30.0)
                # Distance from PM High
                if pm_dist_signed >= 0:
                    score += 25.0
                elif pm_dist_signed >= -2.0:
                    score += 15.0
                elif pm_dist_signed >= -5.0:
                    score += 5.0
                # Spread – only if available and good
                if spread_pct is not None and spread_pct <= 1.0:
                    score += 10.0

                score = round(min(100.0, max(0.0, score)), 1)

                if score >= 70:
                    grade = "A"
                elif score >= 55:
                    grade = "B"
                elif score >= 40:
                    grade = "C"
                else:
                    grade = "WATCH"

                candidate = {
                    "ticker": ticker,
                    "price": price,
                    "prev_close": prev_close,
                    "gap_pct": gap_pct,
                    "spread_pct": spread_pct,
                    "spread_status": spread_status,
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
                    "opportunity_score": score,      # new name
                    "event_score": score,            # kept for backward compatibility
                    "grade": grade,
                    "state": "WATCH",
                    "mode": EXPERIMENT_MODE,
                    "strategy_version": STRATEGY_VERSION,
                    "data_version": "YFINANCE_KEYLESS",
                }

                validated_candidates.append(candidate)

            except Exception as e:
                # Silently skip symbol-specific errors
                continue

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
    print("📊 PREMARKET SCAN V3.1 – KEYLESS MODE (FIXED)")
    print("=" * 70)
    print(f"Discovery candidates: {stats['discovery_pass']:,}")
    print(f"PM validated:         {len(validated_candidates):,}")

    good_data = sum(1 for c in validated_candidates if c.get("pm_data_quality") == "GOOD_DATA")
    low_data = sum(1 for c in validated_candidates if c.get("pm_data_quality") == "LOW_DATA")

    print(f"GOOD_DATA: {good_data:,} | LOW_DATA: {low_data:,}")
    print(f"FINAL: {len(validated_candidates):,}")
    print("=" * 70)

    validated_candidates.sort(
        key=lambda x: (x.get("opportunity_score", 0.0), x.get("gap_pct", 0.0)),
        reverse=True,
    )

    return validated_candidates[:20]
