"""
DAYS-BOT V3.4 – Premarket Engine

Rules:

1. LIVE mode:
   - today only
   - 04:00–09:30 ET
   - no historical substitution

2. MANUAL mode:
   - explicit --date supported
   - historical replay supported

3. No PM data = NO CANDIDATE.

4. Never fabricate spread.

5. Yahoo/yfinance is used only as data source.

6. Invalid symbols do not kill the scan.

7. Candidates are sorted deterministically.
"""

from datetime import datetime, time

from typing import List

import pytz
import pandas as pd
import yfinance as yf

from scanner.universe import load_universe

from utils.config import (
    BOT_VERSION,
    STRATEGY_VERSION,
    EXPERIMENT_MODE,
    DISCOVERY_MAX_GAP,
    DISCOVERY_MAX_PRICE,
    DISCOVERY_MIN_GAP,
    DISCOVERY_MIN_PRICE,
    VALIDATION_MAX_PM_DIST,
    VALIDATION_MIN_PM_BARS,
    VALIDATION_MIN_PM_VOLUME_ABS,
    VALIDATION_MIN_VWAP_DIST,
)


ET = pytz.timezone(
    "America/New_York"
)


# ============================================================
# HELPERS
# ============================================================

def _extract_ticker_df(data, ticker):

    if data is None or data.empty:
        return None

    try:

        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            # group_by="ticker"
            if ticker in data.columns.get_level_values(0):

                df = data[ticker].copy()

            else:

                return None

        else:

            df = data.copy()

        if "Close" not in df.columns:
            return None

        df = df.dropna(
            subset=["Close"]
        )

        if df.empty:
            return None

        return df

    except Exception:
        return None


def _normalize_timezone(df):

    if df is None or df.empty:
        return df

    try:

        if df.index.tz is None:

            df.index = df.index.tz_localize(
                "UTC"
            )

        df.index = df.index.tz_convert(
            ET
        )

    except Exception:
        pass

    return df


def _previous_close_from_daily(
    daily_data,
    ticker,
    target_date_str
):

    df = _extract_ticker_df(
        daily_data,
        ticker
    )

    if df is None:
        return None

    try:

        df = df.copy()

        # Normalize daily dates.
        if df.index.tz is not None:
            dates = df.index.tz_convert(
                ET
            ).date

        else:
            dates = df.index.date

        target_date = datetime.strptime(
            target_date_str,
            "%Y-%m-%d"
        ).date()

        # Previous trading session only.
        valid = df.loc[
            [d < target_date for d in dates]
        ]

        if valid.empty:
            return None

        close = valid["Close"].dropna()

        if close.empty:
            return None

        return float(close.iloc[-1])

    except Exception:
        return None


# ============================================================
# MAIN
# ============================================================

def scan_premarket(
    target_date_str: str = None,
    manual: bool = False
) -> List[dict]:

    now_et = datetime.now(
        ET
    )

    if target_date_str is None:

        target_date_str = now_et.strftime(
            "%Y-%m-%d"
        )

    print()
    print("=" * 70)

    print(
        f"[Premarket] {BOT_VERSION} "
        f"| strategy={STRATEGY_VERSION}"
    )

    print(
        f"[Premarket] Date={target_date_str} "
        f"| ET={now_et.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"[Premarket] Mode="
        f"{'MANUAL_REPLAY' if manual else 'LIVE'}"
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # UNIVERSE
    # --------------------------------------------------------

    universe = load_universe()

    if not universe:

        print(
            "[Premarket] ERROR: empty universe."
        )

        return []

    print(
        f"[Premarket] Universe: "
        f"{len(universe)} symbols"
    )

    # --------------------------------------------------------
    # DAILY DATA
    # --------------------------------------------------------

    print(
        "[Premarket] Fetching previous closes..."
    )

    try:

        daily_data = yf.download(
            tickers=" ".join(universe),
            period="10d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True,
            group_by="ticker",
        )

    except Exception as e:

        print(
            f"[Premarket] Daily download failed: {e}"
        )

        return []

    prev_closes = {}

    for ticker in universe:

        close = _previous_close_from_daily(
            daily_data,
            ticker,
            target_date_str
        )

        if close is not None and close > 0:

            prev_closes[ticker] = close

    print(
        f"[Premarket] Previous closes found: "
        f"{len(prev_closes)}"
    )

    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

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

    validated = []

    # --------------------------------------------------------
    # BATCHES
    # --------------------------------------------------------

    batch_size = 25

    pm_start = time(
        4,
        0
    )

    pm_end = time(
        9,
        30
    )

    for start in range(
        0,
        len(universe),
        batch_size
    ):

        batch = universe[
            start:start + batch_size
        ]

        print(
            f"[Premarket] Batch "
            f"{start + 1}-"
            f"{min(start + batch_size, len(universe))}/"
            f"{len(universe)}"
        )

        try:

            pm_data = yf.download(

                tickers=" ".join(batch),

                period="5d",

                interval="1m",

                prepost=True,

                auto_adjust=False,

                progress=False,

                threads=True,

                group_by="ticker",
            )

        except Exception as e:

            print(
                f"[Premarket] Batch error: {e}"
            )

            continue

        for ticker in batch:

            prev_close = prev_closes.get(
                ticker
            )

            if prev_close is None:

                stats[
                    "no_previous_close"
                ] += 1

                continue

            df = _extract_ticker_df(
                pm_data,
                ticker
            )

            if df is None:

                stats[
                    "pm_missing"
                ] += 1

                continue

            df = _normalize_timezone(
                df
            )

            if df.empty:

                stats[
                    "pm_missing"
                ] += 1

                continue

            # ------------------------------------------------
            # TARGET DATE ONLY
            # ------------------------------------------------

            target_date = datetime.strptime(
                target_date_str,
                "%Y-%m-%d"
            ).date()

            try:

                df_target = df[
                    df.index.date == target_date
                ].copy()

            except Exception:

                stats[
                    "pm_missing"
                ] += 1

                continue

            if df_target.empty:

                stats[
                    "pm_missing"
                ] += 1

                continue

            # ------------------------------------------------
            # PM WINDOW
            # ------------------------------------------------

            df_pm = df_target[
                (
                    df_target.index.time
                    >= pm_start
                )
                &
                (
                    df_target.index.time
                    < pm_end
                )
            ].copy()

            if df_pm.empty:

                stats[
                    "pm_missing"
                ] += 1

                continue

            # ------------------------------------------------
            # CURRENT PM PRICE
            # ------------------------------------------------

            price = float(
                df_pm["Close"].iloc[-1]
            )

            if price <= 0:

                stats[
                    "pm_missing"
                ] += 1

                continue

            # ------------------------------------------------
            # PRICE FILTER
            # ------------------------------------------------

            if (
                price < DISCOVERY_MIN_PRICE
                or
                price > DISCOVERY_MAX_PRICE
            ):

                stats[
                    "price_fail"
                ] += 1

                continue

            # ------------------------------------------------
            # GAP
            # ------------------------------------------------

            gap_pct = (
                (price - prev_close)
                /
                prev_close
            ) * 100.0

            if (
                gap_pct < DISCOVERY_MIN_GAP
                or
                gap_pct > DISCOVERY_MAX_GAP
            ):

                stats[
                    "gap_fail"
                ] += 1

                continue

            # ------------------------------------------------
            # PM METRICS
            # ------------------------------------------------

            pm_bars = len(
                df_pm
            )

            pm_volume = int(
                df_pm["Volume"]
                .fillna(0)
                .sum()
            )

            if pm_volume < VALIDATION_MIN_PM_VOLUME_ABS:

                stats[
                    "pm_volume_fail"
                ] += 1

                continue

            if pm_bars < VALIDATION_MIN_PM_BARS:

                stats[
                    "pm_bars_fail"
                ] += 1

                continue

            pm_high = float(
                df_pm["High"].max()
            )

            pm_low = float(
                df_pm["Low"].min()
            )

            total_volume = float(
                df_pm["Volume"]
                .fillna(0)
                .sum()
            )

            if total_volume <= 0:

                stats[
                    "pm_volume_fail"
                ] += 1

                continue

            pm_vwap = float(
                (
                    df_pm["Close"]
                    *
                    df_pm["Volume"]
                ).sum()
                /
                total_volume
            )

            if pm_vwap <= 0:

                stats[
                    "vwap_fail"
                ] += 1

                continue

            # ------------------------------------------------
            # DISTANCE FROM PM HIGH
            # ------------------------------------------------

            pm_dist_signed = (
                (
                    price - pm_high
                )
                /
                pm_high
            ) * 100.0

            pm_high_dist = max(
                0.0,
                pm_dist_signed
            )

            # ------------------------------------------------
            # VWAP FILTER
            # ------------------------------------------------

            vwap_required_price = (
                pm_vwap
                *
                (
                    1.0
                    +
                    VALIDATION_MIN_VWAP_DIST
                )
            )

            if price < vwap_required_price:

                stats[
                    "vwap_fail"
                ] += 1

                continue

            # ------------------------------------------------
            # SPREAD
            # ------------------------------------------------
            # IMPORTANT:
            # Yahoo bulk historical data does NOT provide
            # reliable PM bid/ask.
            #
            # Therefore:
            # None = UNKNOWN
            #
            # Never pretend it is 0%.

            spread_pct = None

            # ------------------------------------------------
            # DATA QUALITY
            # ------------------------------------------------

            pm_data_quality = "GOOD_DATA"

            # ------------------------------------------------
            # SCORE
            # ------------------------------------------------

            score = 0.0

            # Gap
            score += min(
                max(gap_pct, 0.0)
                * 2.0,
                30.0
            )

            # Volume
            score += min(
                (
                    pm_volume
                    /
                    100_000.0
                )
                *
                20.0,
                30.0
            )

            # PMH proximity
            if pm_dist_signed >= 0:

                score += 25.0

            elif pm_dist_signed >= -2:

                score += 15.0

            elif pm_dist_signed >= -5:

                score += 5.0

            # VWAP
            if price > pm_vwap:

                score += 10.0

            # Data quality
            score += 5.0

            score = round(
                min(
                    100.0,
                    max(
                        0.0,
                        score
                    )
                ),
                1
            )

            if score >= 80:

                grade = "A"

            elif score >= 65:

                grade = "B"

            elif score >= 50:

                grade = "C"

            else:

                grade = "WATCH"

            # ------------------------------------------------
            # CANDIDATE
            # ------------------------------------------------

            candidate = {

                "ticker": ticker,

                "price": price,

                "prev_close": prev_close,

                "gap_pct": gap_pct,

                "spread_pct": spread_pct,

                "pm_volume": pm_volume,

                "pm_bars": pm_bars,

                "pm_bars_count": pm_bars,

                "pm_high": pm_high,

                "pm_low": pm_low,

                "pm_vwap": pm_vwap,

                "pm_dist_signed": pm_dist_signed,

                "pm_high_dist": pm_high_dist,

                "pm_data_quality": pm_data_quality,

                "pm_data_error": None,

                "rvol": None,

                "rvol_status": "UNAVAILABLE",

                "event_score": score,

                "score": score,

                "grade": grade,

                "state": "WATCH",

                "decision": "WATCH",

                "mode": (
                    "MANUAL_REPLAY"
                    if manual
                    else "LIVE"
                ),

                "strategy_version":
                    STRATEGY_VERSION,

                "data_version":
                    "YFINANCE_KEYLESS_V34",

                "scan_date":
                    target_date_str,

            }

            validated.append(
                candidate
            )

            stats[
                "validated"
            ] += 1

            print(
                f"[PM PASS] "
                f"{ticker} | "
                f"Gap={gap_pct:+.1f}% | "
                f"Vol={pm_volume:,} | "
                f"PMH={pm_high:.2f} | "
                f"VWAP={pm_vwap:.2f} | "
                f"Score={score:.1f}"
            )

    # --------------------------------------------------------
    # FINAL SORT
    # --------------------------------------------------------

    validated.sort(
        key=lambda x: (
            x.get(
                "event_score",
                0
            ),
            x.get(
                "pm_volume",
                0
            ),
            x.get(
                "gap_pct",
                0
            ),
        ),
        reverse=True
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PREMARKET SUMMARY")
    print("=" * 70)

    for key, value in stats.items():

        print(
            f"{key:<20}: {value}"
        )

    print("=" * 70)

    print(
        f"[Premarket] Final candidates: "
        f"{len(validated)}"
    )

    return validated[:20]
