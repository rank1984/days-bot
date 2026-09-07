"""
DAYS-BOT V4.3 – Premarket Engine (Alpaca)
Fetches real 1-minute premarket bars from Alpaca.
Returns PM High, Low, VWAP, Volume, Bars count.
"""
import pytz
import requests
from datetime import datetime, timedelta, time
from typing import Optional, Dict
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


def get_premarket_minute_data(ticker: str, target_date_str: str = None) -> Dict:
    """
    Fetch 1-minute premarket bars for the given ticker.
    Returns:
        {
            "pm_high": float,
            "pm_low": float,
            "pm_vwap": float,
            "pm_volume": int,
            "pm_bars_count": int,
            "pm_data_quality": "GOOD_DATA" | "LOW_DATA" | "NO_DATA",
            "error": None or str
        }
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return {"error": "Missing Alpaca API keys"}

    now_et = datetime.now(ET)
    if not target_date_str:
        target_date_str = now_et.strftime("%Y-%m-%d")

    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    current_time = now_et.time()

    # Request 5 days of 1-minute data to cover PM window
    start = now_et - timedelta(days=7)

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
            return {"error": f"Alpaca HTTP {response.status_code}"}

        data = response.json()
        bars = data.get("bars", {}).get(ticker, [])

        if not bars:
            return {"error": "No bars returned"}

        # Filter to target date and PM window
        pm_bars = []
        for bar in bars:
            ts = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
            ts_et = ts.astimezone(ET)
            bar_date = ts_et.date()
            bar_time = ts_et.time()

            if bar_date != target_date:
                continue
            if not (PM_START <= bar_time < PM_END):
                continue
            if bar_time > current_time:
                continue

            pm_bars.append(bar)

        if not pm_bars:
            return {"error": "No PM bars for target date"}

        # Calculate metrics
        highs = [float(b["h"]) for b in pm_bars]
        lows = [float(b["l"]) for b in pm_bars]
        closes = [float(b["c"]) for b in pm_bars]
        volumes = [int(b["v"]) for b in pm_bars]

        pm_high = max(highs)
        pm_low = min(lows)
        pm_volume = sum(volumes)
        pm_bars_count = len(pm_bars)

        # VWAP
        total_value = sum(c * v for c, v in zip(closes, volumes))
        pm_vwap = total_value / pm_volume if pm_volume > 0 else closes[-1]

        quality = "GOOD_DATA" if pm_bars_count >= 10 else "LOW_DATA"

        return {
            "pm_high": round(pm_high, 4),
            "pm_low": round(pm_low, 4),
            "pm_vwap": round(pm_vwap, 4),
            "pm_volume": pm_volume,
            "pm_bars_count": pm_bars_count,
            "pm_data_quality": quality,
            "error": None,
        }

    except Exception as e:
        return {"error": str(e)}
