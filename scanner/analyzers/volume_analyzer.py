"""
DAYS-BOT V4.3 – Volume Analyzer (RVOL)
Calculates RVOL with proper status:
- TIME_ADJUSTED: compares PM volume to historical PM volume at same time
- PREMARKET_FALLBACK: compares PM volume to average daily volume (only if no historical data)
- UNAVAILABLE: when no data exists
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

ET = pytz.timezone("America/New_York")


def calculate_rvol(candidate: dict) -> dict:
    """
    Calculate RVOL with status.

    Returns:
        {
            "rvol": float or None,
            "status": "TIME_ADJUSTED" | "PREMARKET_FALLBACK" | "UNAVAILABLE",
            "method": str,
            "pm_volume": int,
            "reference_volume": int,
        }
    """
    ticker = candidate.get('ticker', '')
    pm_volume = candidate.get('pm_volume', 0)

    if not ticker or pm_volume <= 0:
        return {
            "rvol": None,
            "status": "UNAVAILABLE",
            "method": "NO_DATA",
            "pm_volume": pm_volume,
            "reference_volume": 0
        }

    try:
        now_et = datetime.now(ET)
        # We need historical 1-min data to get PM volume at same time
        # We'll fetch last 5 days of 1-min data
        end = now_et
        start = now_et - timedelta(days=5)

        data = yf.download(ticker, period="5d", interval="1m", prepost=True, progress=False)
        if data.empty:
            return _fallback_rvol(candidate, pm_volume, reason="No historical intraday data")

        # Normalize timezone
        data.index = pd.to_datetime(data.index)
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC")
        data.index = data.index.tz_convert(ET)

        # Current time window (same time as today's PM)
        current_time = now_et.time()
        # We want to compare to the same time window on previous trading days
        # Filter data for the same time window (e.g., 04:00-current_time)
        current_hour = current_time.hour
        current_minute = current_time.minute

        # For each day, calculate PM volume up to current time
        # We'll group by date and sum volume for each day
        data['date'] = data.index.date
        data['time'] = data.index.time

        # Filter to PM window (04:00-09:30)
        pm_data = data[(data.index.time >= datetime.strptime("04:00", "%H:%M").time()) &
                       (data.index.time <= current_time)]

        if pm_data.empty:
            return _fallback_rvol(candidate, pm_volume, reason="No PM data in historical window")

        # Group by date and sum volume for each day
        daily_pm_volumes = pm_data.groupby('date')['Volume'].sum()

        # Exclude today (if present)
        today = now_et.date()
        historical_volumes = [v for d, v in daily_pm_volumes.items() if d != today]

        if not historical_volumes or len(historical_volumes) < 2:
            return _fallback_rvol(candidate, pm_volume, reason="Insufficient historical PM data")

        avg_historical_pm_volume = sum(historical_volumes) / len(historical_volumes)

        if avg_historical_pm_volume > 0:
            rvol = round(pm_volume / avg_historical_pm_volume, 2)
            return {
                "rvol": rvol,
                "status": "TIME_ADJUSTED",
                "method": f"Last {len(historical_volumes)} days PM volume up to {current_time.strftime('%H:%M')} ET",
                "pm_volume": pm_volume,
                "reference_volume": round(avg_historical_pm_volume, 0)
            }
        else:
            return _fallback_rvol(candidate, pm_volume, reason="Historical PM volume is zero")

    except Exception as e:
        print(f"[RVOL] Error for {ticker}: {e}")
        return _fallback_rvol(candidate, pm_volume, reason=f"Exception: {e}")


def _fallback_rvol(candidate: dict, pm_volume: int, reason: str = None) -> dict:
    """
    Fallback: use daily average volume from 30 days.
    """
    ticker = candidate.get('ticker', '')
    try:
        data = yf.download(ticker, period="1mo", interval="1d", progress=False)
        if data.empty:
            return {
                "rvol": None,
                "status": "UNAVAILABLE",
                "method": f"No daily data (reason: {reason})",
                "pm_volume": pm_volume,
                "reference_volume": 0
            }

        avg_daily_volume = data['Volume'].iloc[-30:].mean() if len(data) >= 30 else data['Volume'].mean()
        if avg_daily_volume > 0:
            rvol = round(pm_volume / avg_daily_volume, 2)
            return {
                "rvol": rvol,
                "status": "PREMARKET_FALLBACK",
                "method": f"PM volume / avg daily volume (30d). Reason: {reason}",
                "pm_volume": pm_volume,
                "reference_volume": round(avg_daily_volume, 0)
            }
        else:
            return {
                "rvol": None,
                "status": "UNAVAILABLE",
                "method": f"Avg daily volume is zero (reason: {reason})",
                "pm_volume": pm_volume,
                "reference_volume": 0
            }

    except Exception as e:
        return {
            "rvol": None,
            "status": "UNAVAILABLE",
            "method": f"Fallback error: {e}",
            "pm_volume": pm_volume,
            "reference_volume": 0
        }
