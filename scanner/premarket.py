"""
DAYS-BOT V3.4
Stable Premarket Scanner

Design:
- Small universe
- yfinance only
- Small batches
- Retry/backoff
- No fake spread
- Premarket 04:00-09:30 ET
- Discovery first
- PM validation second
"""

from datetime import datetime, time
from typing import List
import time as time_module

import pandas as pd
import pytz
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
    VALIDATION_MIN_PM_BARS,
    VALIDATION_MIN_PM_VOLUME_ABS,
    VALIDATION_MIN_VWAP_DIST,
)


ET = pytz.timezone("America/New_York")

PM_START = time(4, 0)
PM_END = time(9, 30)

BATCH_SIZE = 25
MAX_RETRIES = 3


def _download_batch(
    tickers: List[str],
    interval: str,
    period: str,
    prepost: bool = False,
):
    """
    Download one small batch with exponential backoff.
    """

    ticker_string = " ".join(tickers)

    for attempt in range(MAX_RETRIES):
        try:
            data = yf.download(
                ticker_string,
                period=period,
                interval=interval,
                prepost=prepost,
                group_by="ticker",
                progress=False,
                threads=False,
                auto_adjust=False,
            )

            if data is not None and not data.empty:
                return data

        except Exception as exc:
            wait = 2 ** attempt

            print(
                f"[Yahoo] Batch failed "
                f"(attempt {attempt + 1}/{MAX_RETRIES}): "
                f"{exc}"
            )

            if attempt < MAX_RETRIES - 1:
                time_module.sleep(wait)

    return None


def _extract_ticker_df(data, ticker: str):
    if data is None or data.empty:
        return None

    try:
        if isinstance(data.columns, pd.MultiIndex):
            level0 = data.columns.get_level_values(0)

            if ticker not in level0:
                return None

            df = data[ticker].copy()

        else:
            df = data.copy()

        if "Close" not in df.columns:
            return None

        df = df.dropna(subset=["Close"])

        if df.empty:
            return None

        return df

    except Exception:
        return None


def _normalize_index_to_et(df: pd.DataFrame) -> pd.DataFrame:
    """
    Make sure timestamps are timezone-aware and represented in ET.
    """

    result = df.copy()

    try:
        if result.index.tz is None:
            result.index = result.index.tz_localize("UTC")

        result.index = result.index.tz_convert(ET)

    except Exception:
        return pd.DataFrame()

    return result


def _get_previous_closes(universe: List[str]):
    """
    Fetch daily history in small batches instead of one giant request.
    """

    result = {}

    print(
        f"[Premarket] Fetching previous closes "
        f"for {len(universe)} symbols..."
    )

    for i in range(0, len(universe), BATCH_SIZE):
        batch = universe[i:i + BATCH_SIZE]

        data = _download_batch(
            batch,
            interval="1d",
            period="5d",
            prepost=False,
        )

        if data is None:
            continue

        for ticker in batch:
            df = _extract_ticker_df(data, ticker)

            if df is None or df.empty:
                continue

            try:
                close = df["Close"].dropna()

                if not close.empty:
                    result[ticker] = float(close.iloc[-1])

            except Exception:
                continue

        # Tiny pause reduces burst pressure.
        time_module.sleep(0.5)

    print(
        f"[Premarket] Previous closes found: "
        f"{len(result)}"
    )

    return result


def _calculate_pm_metrics(df_pm: pd.DataFrame):
    if df_pm.empty:
        return None

    volume = pd.to_numeric(
        df_pm["Volume"],
        errors="coerce"
    ).fillna(0)

    close = pd.to_numeric(
        df_pm["Close"],
        errors="coerce"
    )

    high = pd.to_numeric(
        df_pm["High"],
        errors="coerce"
    )

    low = pd.to_numeric(
        df_pm["Low"],
        errors="coerce"
    )

    volume_sum = float(volume.sum())

    if volume_sum <= 0:
        return None

    pm_high = float(high.max())
    pm_low = float(low.min())

    pm_vwap = float(
        (close * volume).sum() / volume_sum
    )

    return {
        "pm_volume": int(volume_sum),
        "pm_bars_count": int(len(df_pm)),
        "pm_high": pm_high,
        "pm_low": pm_low,
        "pm_vwap": pm_vwap,
    }


def scan_premarket(target_date_str: str = None) -> List[dict]:

    now_et = datetime.now(ET)

    if target_date_str is None:
        target_date_str = now_et.strftime("%Y-%m-%d")

    print()
    print("=" * 70)
    print(
        f"[Premarket] {BOT_VERSION} "
        f"| {STRATEGY_VERSION} "
        f"| KEYLESS YFINANCE"
    )
    print(
        f"[Premarket] Date={target_date_str} "
        f"| ET={now_et.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("=" * 70)

    universe = load_universe()

    if not universe:
        print("[Premarket] ❌ Empty universe.")
        return []

    prev_closes = _get_previous_closes(universe)

    candidates = []

    stats = {
        "universe": len(universe),
        "no_previous_close": 0,
        "price_fail": 0,
        "gap_fail": 0,
        "pm_missing": 0,
        "pm_volume_fail": 0,
        "pm_bars_fail": 0,
        "vwap_fail": 0,
        "validated": 0,
    }

    for i in range(0, len(universe), BATCH_SIZE):

        batch = universe[i:i + BATCH_SIZE]

        print(
            f"[Premarket] Batch "
            f"{i + 1}-{min(i + BATCH_SIZE, len(universe))}"
            f"/{len(universe)}"
        )

        pm_data = _download_batch(
            batch,
            interval="1m",
            period="1d",
            prepost=True,
        )

        if pm_data is None:
            print("[Premarket] Batch returned no data.")
            continue

        for ticker in batch:

            prev_close = prev_closes.get(ticker)

            if prev_close is None or prev_close <= 0:
                stats["no_previous_close"] += 1
                continue

            df = _extract_ticker_df(pm_data, ticker)

            if df is None:
                stats["pm_missing"] += 1
                continue

            df = _normalize_index_to_et(df)

            if df.empty:
                stats["pm_missing"] += 1
                continue

            # We only use the requested trading date.
            try:
                df = df[
                    df.index.strftime("%Y-%m-%d")
                    == target_date_str
                ]
            except Exception:
                continue

            if df.empty:
                stats["pm_missing"] += 1
                continue

            # Latest available market price.
            price = float(df["Close"].iloc[-1])

            if (
                price < DISCOVERY_MIN_PRICE
                or price > DISCOVERY_MAX_PRICE
            ):
                stats["price_fail"] += 1
                continue

            gap_pct = (
                (price - prev_close)
                / prev_close
                * 100.0
            )

            if (
                gap_pct < DISCOVERY_MIN_GAP
                or gap_pct > DISCOVERY_MAX_GAP
            ):
                stats["gap_fail"] += 1
                continue

            # Premarket window.
            df_pm = df[
                (df.index.time >= PM_START)
                & (df.index.time < PM_END)
            ]

            if df_pm.empty:
                stats["pm_missing"] += 1
                continue

            metrics = _calculate_pm_metrics(df_pm)

            if metrics is None:
                stats["pm_volume_fail"] += 1
                continue

            pm_volume = metrics["pm_volume"]
            pm_bars = metrics["pm_bars_count"]

            if pm_volume < VALIDATION_MIN_PM_VOLUME_ABS:
                stats["pm_volume_fail"] += 1
                continue

            if pm_bars < VALIDATION_MIN_PM_BARS:
                stats["pm_bars_fail"] += 1
                continue

            pm_high = metrics["pm_high"]
            pm_low = metrics["pm_low"]
            pm_vwap = metrics["pm_vwap"]

            if pm_high <= 0 or pm_vwap <= 0:
                stats["vwap_fail"] += 1
                continue

            pm_dist_signed = (
                (price - pm_high)
                / pm_high
                * 100.0
            )

            if pm_dist_signed < -VALIDATION_MAX_PM_DIST:
                continue

            vwap_required_price = (
                pm_vwap
                * (1.0 + VALIDATION_MIN_VWAP_DIST)
            )

            if price < vwap_required_price:
                stats["vwap_fail"] += 1
                continue

            # ------------------------------------------------
            # EVENT SCORE
            # ------------------------------------------------

            event_score = 0.0

            event_score += min(
                max(gap_pct, 0.0) * 2.0,
                30.0
            )

            event_score += min(
                (pm_volume / 100_000.0) * 20.0,
                30.0
            )

            if pm_dist_signed >= 0:
                event_score += 25.0

            elif pm_dist_signed >= -2.0:
                event_score += 15.0

            elif pm_dist_signed >= -5.0:
                event_score += 5.0

            # IMPORTANT:
            # No fake spread bonus.
            # yfinance bulk data does not provide reliable L1.
            spread_pct = None

            event_score = round(
                min(max(event_score, 0.0), 100.0),
                1
            )

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

                "pm_volume": pm_volume,
                "pm_bars": pm_bars,
                "pm_bars_count": pm_bars,

                "pm_high": pm_high,
                "pm_low": pm_low,
                "pm_vwap": pm_vwap,

                "pm_dist_signed": pm_dist_signed,
                "pm_high_dist": max(
                    0.0,
                    pm_dist_signed
                ),

                "spread_pct": spread_pct,

                "pm_data_quality": "GOOD_DATA",
                "pm_data_error": None,

                "rvol": None,
                "rvol_status": "UNAVAILABLE",

                "event_score": event_score,
                "grade": grade,

                "state": "WATCH",

                "mode": EXPERIMENT_MODE,
                "strategy_version": STRATEGY_VERSION,
                "data_version": DATA_VERSION,
            }

            candidates.append(candidate)
            stats["validated"] += 1

            print(
                f"[PM PASS] {ticker}"
                f" | Price={price:.2f}"
                f" | Gap={gap_pct:.1f}%"
                f" | Vol={pm_volume:,}"
                f" | PMH={pm_high:.2f}"
                f" | VWAP={pm_vwap:.2f}"
                f" | Score={event_score}"
            )

        time_module.sleep(0.75)

    # ------------------------------------------------------------
    # FINAL SORT
    # ------------------------------------------------------------

    candidates.sort(
        key=lambda x: (
            x.get("event_score", 0.0),
            x.get("pm_volume", 0),
            x.get("gap_pct", 0.0),
        ),
        reverse=True,
    )

    print()
    print("=" * 70)
    print("PREMARKET SUMMARY")
    print("=" * 70)

    for key, value in stats.items():
        print(f"{key:20}: {value}")

    print("=" * 70)
    print(
        f"[Premarket] Final candidates: "
        f"{len(candidates)}"
    )

    # Keep enough candidates for deep analysis.
    return candidates[:20]
