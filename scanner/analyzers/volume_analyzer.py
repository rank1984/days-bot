"""
DAYS-BOT V5.0 – Volume Analyzer (RVOL)
RVOL is INFORMATIONAL only – does NOT affect Data Completeness or Trade decisions.
"""
import pytz
import requests
from datetime import datetime, timedelta, time
from typing import Optional
from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_DATA_URL

ET = pytz.timezone("America/New_York")
BARS_URL = f"{ALPACA_DATA_URL.rstrip('/')}/v2/stocks/bars"

PM_START = time(4, 0)
PM_END = time(9, 30)


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json",
    }


def _get_historical_pm_volume(ticker: str, lookback_days: int = 10) -> Optional[float]:
    """
    Get historical premarket volume for the same time window.
    Uses Alpaca 1-minute bars with IEX feed.
    Returns None if insufficient data (most stocks have no PM history).
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None

    now_et = datetime.now(ET)
    target_date = now_et.date()
    current_time = now_et.time()
    start = now_et - timedelta(days=lookback_days + 1)

    try:
        response = requests.get(
            BARS_URL,
            headers=_headers(),
            params={
                "symbols": ticker,
                "timeframe": "1Min",
                "start": start.isoformat(),
                "end": now_et.isoformat(),
                "adjustment": "raw",
                "feed": "iex",
                "limit": 10000,
            },
            timeout=15,
        )

        if response.status_code != 200:
            return None

        data = response.json()
        bars = data.get("bars", {}).get(ticker, [])

        if not bars:
            return None

        # Group by date and sum PM volume
        daily_volumes = {}
        for bar in bars:
            ts = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
            ts_et = ts.astimezone(ET)
            bar_time = ts_et.time()
            bar_date = ts_et.date()

            # Only PM window (04:00-09:30)
            if not (PM_START <= bar_time < PM_END):
                continue
            # For today only: only up to current time
            if bar_date == target_date and bar_time > current_time:
                continue

            daily_volumes[bar_date] = daily_volumes.get(bar_date, 0) + int(bar.get("v", 0))

        # Exclude today
        historical = [v for d, v in daily_volumes.items() if d != target_date]

        if len(historical) < 2:
            return None

        # Use median to avoid outliers
        from statistics import median
        return median(historical)

    except Exception:
        return None


def calculate_rvol(candidate: dict) -> dict:
    """
    Calculate RVOL – INFORMATIONAL ONLY.
    Returns UNAVAILABLE if no historical PM data (which is the case for most stocks).
    """
    ticker = candidate.get('ticker')
    pm_volume = candidate.get('pm_volume', 0)

    if not ticker or pm_volume <= 0:
        return {
            "rvol": None,
            "status": "UNAVAILABLE",
            "method": "NO_DATA",
            "pm_volume": pm_volume,
            "reference_volume": 0
        }

    historical_median = _get_historical_pm_volume(ticker, lookback_days=10)

    if historical_median is not None and historical_median > 0:
        rvol = round(pm_volume / historical_median, 2)
        return {
            "rvol": rvol,
            "status": "TIME_ADJUSTED",
            "method": "Alpaca 1-min bars, same time window (median, 10 days)",
            "pm_volume": pm_volume,
            "reference_volume": round(historical_median)
        }

    # If no historical PM data, return UNAVAILABLE (not a fallback)
    return {
        "rvol": None,
        "status": "UNAVAILABLE",
        "method": "No historical PM data available",
        "pm_volume": pm_volume,
        "reference_volume": 0
    }
