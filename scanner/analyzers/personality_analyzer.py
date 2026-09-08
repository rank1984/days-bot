"""
DAYS-BOT V5.0.3 – Stock Personality Analyzer

Checks how the stock historically behaved after
similar positive gaps.

Important:
- Informational only.
- Never blocks a candidate.
- Returns a stable dict contract.
- Uses up to 60 days of 5-minute data because
  Yahoo intraday history is limited.
"""

import yfinance as yf
import pandas as pd


def _default_result():
    return {
        "avg_gap_following": 0.5,
        "avg_30min_return": 0.0,
        "failure_rate": 50.0,
        "sample_size": 0,
        "personality": "NEUTRAL",
    }


def _to_scalar(value, default=0.0):
    """
    Convert pandas/numpy/scalar values safely to float.
    """

    try:
        if value is None:
            return default

        if isinstance(value, pd.Series):
            if value.empty:
                return default
            value = value.iloc[0]

        if isinstance(value, pd.DataFrame):
            if value.empty:
                return default
            value = value.iloc[0, 0]

        value = float(value)

        if pd.isna(value):
            return default

        return value

    except Exception:
        return default


def _flatten_columns(data):
    """
    yfinance can return MultiIndex columns.

    Convert:
        ('Close', 'AAPL')
    into:
        'Close'

    for single-ticker downloads.
    """

    if not isinstance(data.columns, pd.MultiIndex):
        return data

    flattened = []

    for col in data.columns:
        if isinstance(col, tuple):
            # Usually ('Close', 'TICKER')
            flattened.append(str(col[0]))
        else:
            flattened.append(str(col))

    data = data.copy()
    data.columns = flattened

    # Remove duplicate columns if flattening created them.
    data = data.loc[
        :,
        ~data.columns.duplicated()
    ]

    return data


def get_stock_personality(
    ticker: str,
    current_gap: float
) -> dict:
    """
    Returns:

    avg_gap_following:
        1 = historically follows higher
        0 = historically follows lower

    avg_30min_return:
        Average return approximately 30 minutes after
        similar gap events.

    failure_rate:
        Percentage of events with return < -2%.

    sample_size:
        Number of valid historical events.

    personality:
        STRONG_FOLLOWER
        FOLLOWER
        NEUTRAL
        GAP_AND_CRAP
    """

    result = _default_result()

    try:
        current_gap = _to_scalar(
            current_gap,
            0.0
        )

        if current_gap <= 5:
            return result

        # --------------------------------------------------------
        # Yahoo intraday limitation:
        # use recent 60-day 5m history rather than 365 days.
        # --------------------------------------------------------

        data = yf.download(
            ticker,
            period="60d",
            interval="5m",
            progress=False,
            auto_adjust=False,
            prepost=False,
            threads=False,
        )

        if data is None or data.empty:
            return result

        data = _flatten_columns(data)

        required = {
            "Open",
            "Close",
            "Volume",
        }

        if not required.issubset(
            set(data.columns)
        ):
            print(
                f"[Personality] {ticker}: "
                f"missing columns "
                f"{required - set(data.columns)}"
            )
            return result

        # --------------------------------------------------------
        # Clean numeric columns
        # --------------------------------------------------------

        for column in [
            "Open",
            "Close",
            "Volume",
        ]:
            data[column] = pd.to_numeric(
                data[column],
                errors="coerce"
            )

        data = data.dropna(
            subset=[
                "Open",
                "Close",
                "Volume",
            ]
        )

        if len(data) < 50:
            return result

        # --------------------------------------------------------
        # Time normalization
        # --------------------------------------------------------

        if data.index.tz is None:
            data.index = data.index.tz_localize(
                "America/New_York"
            )
        else:
            data.index = data.index.tz_convert(
                "America/New_York"
            )

        # --------------------------------------------------------
        # Build daily opening gaps correctly.
        #
        # Previous day's final regular-session close
        # vs current day's first regular-session open.
        # --------------------------------------------------------

        data["trade_date"] = data.index.date

        daily_groups = []

        dates = sorted(
            data["trade_date"].unique()
        )

        for i in range(1, len(dates)):

            current_date = dates[i]
            previous_date = dates[i - 1]

            current_day = data[
                data["trade_date"] == current_date
            ]

            previous_day = data[
                data["trade_date"] == previous_date
            ]

            if current_day.empty or previous_day.empty:
                continue

            current_open = _to_scalar(
                current_day.iloc[0]["Open"],
                0
            )

            previous_close = _to_scalar(
                previous_day.iloc[-1]["Close"],
                0
            )

            if (
                current_open <= 0
                or previous_close <= 0
            ):
                continue

            gap = (
                (current_open - previous_close)
                / previous_close
                * 100
            )

            # Similar gap window:
            # ±50%, minimum positive gap >5%.
            threshold = abs(current_gap) * 0.5

            if (
                gap >= current_gap - threshold
                and gap <= current_gap + threshold
                and gap > 5
            ):
                daily_groups.append(
                    (
                        current_date,
                        current_open,
                        gap,
                    )
                )

        if not daily_groups:
            return result

        # --------------------------------------------------------
        # Evaluate first ~30 minutes after opening.
        # 6 x 5-minute bars.
        # --------------------------------------------------------

        returns = []
        failures = 0

        for trade_date, open_price, gap in daily_groups:

            day_data = data[
                data["trade_date"] == trade_date
            ].sort_index()

            if len(day_data) < 7:
                continue

            future_price = _to_scalar(
                day_data.iloc[6]["Close"],
                0
            )

            if future_price <= 0:
                continue

            ret = (
                (future_price - open_price)
                / open_price
                * 100
            )

            returns.append(ret)

            if ret < -2:
                failures += 1

        if not returns:
            return result

        avg_ret = sum(returns) / len(returns)

        failure_pct = (
            failures
            / len(returns)
            * 100
        )

        # --------------------------------------------------------
        # Final scalar result
        # --------------------------------------------------------

        result["avg_gap_following"] = (
            1.0 if avg_ret > 0 else 0.0
        )

        result["avg_30min_return"] = round(
            float(avg_ret),
            2
        )

        result["failure_rate"] = round(
            float(failure_pct),
            1
        )

        result["sample_size"] = int(
            len(returns)
        )

        if (
            avg_ret > 3
            and failure_pct < 30
        ):
            result["personality"] = (
                "STRONG_FOLLOWER"
            )

        elif (
            avg_ret > 0
            and failure_pct < 40
        ):
            result["personality"] = (
                "FOLLOWER"
            )

        elif avg_ret > -1:
            result["personality"] = (
                "NEUTRAL"
            )

        else:
            result["personality"] = (
                "GAP_AND_CRAP"
            )

        return result

    except Exception as e:

        print(
            f"[Personality] ❌ Error for "
            f"{ticker}: "
            f"{type(e).__name__}: {e}"
        )

        return result