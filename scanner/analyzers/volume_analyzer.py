"""
DAYS-BOT V4.3 – Volume Analyzer (RVOL)
Uses Alpaca historical intraday data for time-adjusted RVOL.

Debug: prints raw date distribution to diagnose "Historical days: 0".
"""
import pytz
import requests
from datetime import datetime, timedelta, time
from typing import Optional
from statistics import median
from collections import Counter
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

    Returns median PM volume from previous trading days.
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("[RVOL] ⚠️ Alpaca API keys missing")
        return None

    now_et = datetime.now(ET)
    target_date = now_et.date()
    current_time = now_et.time()

    start = now_et - timedelta(days=lookback_days + 1)

    try:
        print(f"[RVOL] 📡 Requesting Alpaca bars for {ticker}...")
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

        print(f"[RVOL] 📡 Alpaca response: {response.status_code}")

        if response.status_code != 200:
            print(f"[RVOL] ❌ Alpaca bars error: {response.status_code} - {response.text[:200]}")
            return None

        data = response.json()
        bars = data.get("bars", {}).get(ticker, [])

        print(f"[RVOL] 📊 Received {len(bars)} bars for {ticker}")

        if not bars:
            print(f"[RVOL] ⚠️ No bars for {ticker}")
            return None

        # ============================================================
        # DEBUG: Raw date distribution
        # ============================================================
        date_counts = Counter(
            datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET).date()
            for b in bars
        )
        print(f"[RVOL DEBUG] {ticker} raw bar dates: {dict(date_counts)}")

        # Group by date and sum PM volume up to current time
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

            if bar_date not in daily_volumes:
                daily_volumes[bar_date] = 0
            daily_volumes[bar_date] += int(bar.get("v", 0))

        # Exclude today
        historical = [v for d, v in daily_volumes.items() if d != target_date]

        print(f"[RVOL] 📊 Historical days: {len(historical)}")
        if historical:
            print(f"[RVOL] 📊 Historical volumes: {historical[:5]}...")

        if len(historical) < 2:
            print(f"[RVOL] ⚠️ Insufficient historical days: {len(historical)}")
            return None

        # Use median to avoid outliers
        historical_reference = median(historical)
        print(f"[RVOL] ✅ Median historical PM volume: {historical_reference:.0f}")
        return historical_reference

    except Exception as e:
        print(f"[RVOL] ❌ Error: {e}")
        return None


def _yfinance_fallback(ticker: str, pm_volume: int) -> Optional[dict]:
    """
    Fallback to yfinance daily average volume.
    CRITICAL FIXES:
    - Use 2-month period (approx 60 days) to avoid "must be within 60 days" error.
    - Properly convert Series to Python scalars.
    """
    try:
        import yfinance as yf
        print(f"[RVOL] 📡 Using yfinance fallback for {ticker}")

        # Use 2-month period to stay within 60-day limit
        data = yf.download(ticker, period="2mo", interval="1d", progress=False)

        if data.empty:
            print(f"[RVOL] ⚠️ No yfinance data for {ticker}")
            return None

        vol_series = data['Volume'].dropna()
        if len(vol_series) == 0:
            print(f"[RVOL] ⚠️ No volume data for {ticker}")
            return None

        # Convert to list of Python floats
        volumes = [float(v) for v in vol_series.values]

        if len(volumes) < 5:
            print(f"[RVOL] ⚠️ Not enough volume data points: {len(volumes)}")
            return None

        if len(volumes) >= 30:
            avg_volume = sum(volumes[-30:]) / 30
        else:
            avg_volume = sum(volumes) / len(volumes)

        if avg_volume > 0:
            rvol = round(pm_volume / avg_volume, 2)
            print(f"[RVOL] ⚠️ RVOL = {rvol} (PREMARKET_FALLBACK)")
            return {
                "rvol": rvol,
                "status": "PREMARKET_FALLBACK",
                "method": f"PM volume / avg daily volume ({len(volumes)} days)",
                "pm_volume": pm_volume,
                "reference_volume": round(avg_volume)
            }

    except Exception as e:
        print(f"[RVOL] ❌ yfinance fallback error: {e}")

    return None


def calculate_rvol(candidate: dict) -> dict:
    ticker = candidate.get('ticker')
    pm_volume = candidate.get('pm_volume', 0)

    print(f"[RVOL] 🔍 Calculating RVOL for {ticker} (PM volume: {pm_volume})")

    if not ticker or pm_volume <= 0:
        print(f"[RVOL] ⚠️ No ticker or zero volume for {ticker}")
        return {
            "rvol": None,
            "status": "UNAVAILABLE",
            "method": "NO_DATA",
            "pm_volume": pm_volume,
            "reference_volume": 0
        }

    # Try Alpaca historical data first (10 days lookback)
    historical_median = _get_historical_pm_volume(ticker, lookback_days=10)

    if historical_median is not None and historical_median > 0:
        rvol = round(pm_volume / historical_median, 2)
        print(f"[RVOL] ✅ RVOL = {rvol} (TIME_ADJUSTED)")
        return {
            "rvol": rvol,
            "status": "TIME_ADJUSTED",
            "method": "Alpaca 1-min bars, same time window (median, 10 days)",
            "pm_volume": pm_volume,
            "reference_volume": round(historical_median)
        }

    # Fallback: use yfinance
    fallback = _yfinance_fallback(ticker, pm_volume)
    if fallback:
        return fallback

    print(f"[RVOL] ❌ RVOL UNAVAILABLE for {ticker}")
    return {
        "rvol": None,
        "status": "UNAVAILABLE",
        "method": "No historical PM data available",
        "pm_volume": pm_volume,
        "reference_volume": 0
    }