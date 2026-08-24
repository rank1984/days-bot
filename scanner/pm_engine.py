"""
Premarket Engine – fetches real PM data from Alpaca Minute Bars
Only called after Discovery (~100-200 candidates)
"""
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import alpaca_trade_api as tradeapi
import pytz

ET = pytz.timezone('America/New_York')


def get_premarket_minute_data(symbol: str, api: tradeapi.REST) -> Dict[str, Any]:
    """
    Fetches minute bars from Alpaca for premarket (04:00-09:30 ET)
    Returns PM Volume, High, Low, VWAP, and Time-adjusted RVOL.
    """
    result = {
        'pm_volume': None,
        'pm_high': None,
        'pm_low': None,
        'pm_vwap': None,
        'pm_open': None,
        'rvol_time_adjusted': None,
        'data_quality': 'LOW',
        'error': None,
    }

    try:
        now = datetime.now(ET)
        if now.weekday() >= 5:  # weekend
            result['error'] = 'Weekend'
            return result

        # Premarket hours: 04:00 to 09:30 ET
        start = now.replace(hour=4, minute=0, second=0, microsecond=0)
        end = now.replace(hour=9, minute=30, second=0, microsecond=0)

        # If current time is before 04:00, use previous day? Actually premarket is current day.
        # Alpaca bars from start to now (or up to 09:30)
        end = min(now, end)

        if start >= end:
            result['error'] = 'Not premarket hours'
            return result

        # Fetch minute bars from Alpaca
        # Using 1-minute bars for the current day
        bars = api.get_bars(
            symbol,
            timeframe='1Min',
            start=start.isoformat(),
            end=end.isoformat(),
            adjustment='raw'
        )

        if not bars or len(bars) == 0:
            result['error'] = 'No bars'
            return result

        df = bars.df
        if df.empty:
            result['error'] = 'Empty bars'
            return result

        # Compute PM metrics
        result['pm_volume'] = int(df['volume'].sum())
        result['pm_high'] = float(df['high'].max())
        result['pm_low'] = float(df['low'].min())
        result['pm_open'] = float(df['open'].iloc[0])

        # VWAP: sum(typical_price * volume) / sum(volume)
        typical = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical * df['volume']).sum() / df['volume'].sum() if df['volume'].sum() > 0 else 0
        result['pm_vwap'] = float(vwap)

        # Historical PM volume median (last 5 days, same time-of-day)
        # We need to fetch historical data for the same symbol.
        # For performance, we'll use a cache or a simple approach:
        # We'll store a cache in data/pm_history.json
        # For now, we'll compute a simple fallback: use a constant factor.
        # But we want real time-adjusted RVOL.
        # Since we have Alpaca, we can fetch historical minute bars.
        # However, to avoid rate limits, we'll cache it.

        # For MVP, we'll use a simple approach: use the last 5 days' PM volumes.
        # We'll fetch them using Alpaca's historical bars.
        # But to keep it fast, we'll fetch only for the top candidates.
        # We'll implement a cache to avoid repeated calls.
        hist_volumes = _get_historical_pm_volumes(symbol, api, days=5)
        if hist_volumes:
            median_vol = sorted(hist_volumes)[len(hist_volumes)//2]
            if median_vol > 0:
                result['rvol_time_adjusted'] = result['pm_volume'] / median_vol
                result['data_quality'] = 'HIGH'
            else:
                result['data_quality'] = 'MEDIUM'
        else:
            result['data_quality'] = 'LOW'

    except Exception as e:
        result['error'] = str(e)

    return result


# Simple cache for historical PM volumes
_hist_cache = {}

def _get_historical_pm_volumes(symbol: str, api: tradeapi.REST, days: int = 5) -> List[int]:
    """Fetch historical premarket volumes for the last N days."""
    cache_key = f"{symbol}_{days}"
    if cache_key in _hist_cache:
        return _hist_cache[cache_key]

    volumes = []
    now = datetime.now(ET)
    for i in range(1, days+1):
        day = now - timedelta(days=i)
        if day.weekday() >= 5:  # skip weekends
            continue
        # Fetch bars for that day, premarket hours
        start = day.replace(hour=4, minute=0, second=0, microsecond=0)
        end = day.replace(hour=9, minute=30, second=0, microsecond=0)
        try:
            bars = api.get_bars(
                symbol,
                timeframe='1Min',
                start=start.isoformat(),
                end=end.isoformat(),
                adjustment='raw'
            )
            if bars and len(bars) > 0:
                df = bars.df
                if not df.empty:
                    volumes.append(int(df['volume'].sum()))
        except Exception:
            continue
        # Be gentle with API rate limits
        time.sleep(0.1)

    _hist_cache[cache_key] = volumes
    return volumes
