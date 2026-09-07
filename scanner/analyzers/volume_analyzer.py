"""
DAYS-BOT V4.3 – Volume Analyzer (RVOL)
Uses Alpaca historical intraday data for time-adjusted RVOL.
"""
import pytz
import requests
from datetime import datetime, timedelta
from typing import Optional
from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_DATA_URL

ET = pytz.timezone("America/New_York")
BARS_URL = f"{ALPACA_DATA_URL.rstrip('/')}/v2/stocks/bars"


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json",
    }


def _get_historical_pm_volume(ticker: str, lookback_days: int = 5) -> Optional[float]:
    """
    Get historical premarket volume for the same time window.
    Uses Alpaca 1-minute bars.
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None

    now_et = datetime.now(ET)
    current_time = now_et.time()
    target_date = now_et.date()

    # We need data from the last N days (including today)
    end = now_et
    start = now_et - timedelta(days=lookback_days + 1)

    try:
        response = requests.get(
            BARS_URL,
            headers=_headers(),
            params={
                "symbols": ticker,
                "timeframe": "1Min",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "adjustment": "raw",
                "feed": "iex",
                "limit": 10000,
            },
            timeout=15,
        )

        if response.status_code != 200:
            print(f"[RVOL] Alpaca bars error: {response.status_code}")
            return None

        data = response.json()
        bars = data.get("bars", {}).get(ticker, [])

        if not bars:
            return None

        # Group by date and sum PM volume up to current time
        daily_volumes = {}
        for bar in bars:
            ts = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
            ts_et = ts.astimezone(ET)
            bar_time = ts_et.time()
            bar_date = ts_et.date()

            # Only PM window (04:00-09:30) and up to current time
            if bar_time < datetime.strptime("04:00", "%H:%M").time():
                continue
            if bar_time >= datetime.strptime("09:30", "%H:%M").time():
                continue
            if bar_time > current_time:
                continue

            if bar_date not in daily_volumes:
                daily_volumes[bar_date] = 0
            daily_volumes[bar_date] += int(bar.get("v", 0))

        # Exclude today
        historical = [v for d, v in daily_volumes.items() if d != target_date]

        if len(historical) < 2:
            print(f"[RVOL] Insufficient historical days: {len(historical)}")
            return None

        avg_volume = sum(historical) / len(historical)
        return avg_volume

    except Exception as e:
        print(f"[RVOL] Error: {e}")
        return None


def calculate_rvol(candidate: dict) -> dict:
    """
    Calculate time-adjusted RVOL using Alpaca historical data.
    Returns: {"rvol": float, "status": str, "method": str, "reference_volume": int, "pm_volume": int}
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

    # Try Alpaca historical data first
    historical_avg = _get_historical_pm_volume(ticker)

    if historical_avg is not None and historical_avg > 0:
        rvol = round(pm_volume / historical_avg, 2)
        return {
            "rvol": rvol,
            "status": "TIME_ADJUSTED",
            "method": "Alpaca 1-min bars, same time window",
            "pm_volume": pm_volume,
            "reference_volume": round(historical_avg)
        }

    # Fallback: use yfinance daily average volume (but warn)
    try:
        import yfinance as yf
        data = yf.download(ticker, period="1mo", interval="1d", progress=False)
        if not data.empty:
            avg_daily = data['Volume'].iloc[-30:].mean()
            if avg_daily > 0:
                rvol = round(pm_volume / avg_daily, 2)
                return {
                    "rvol": rvol,
                    "status": "PREMARKET_FALLBACK",
                    "method": "PM volume / avg daily volume (30d)",
                    "pm_volume": pm_volume,
                    "reference_volume": round(avg_daily)
                }
    except Exception:
        pass

    return {
        "rvol": None,
        "status": "UNAVAILABLE",
        "method": "No historical PM data available",
        "pm_volume": pm_volume,
        "reference_volume": 0
    }