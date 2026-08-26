"""
Premarket Engine – fetches real PM data from Alpaca Minute Bars
"""
print("🔥 LOADED PM_ENGINE V2.12.1")

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
        'pm_bars_count': 0,
        'pm_volume_raw': 0,
        'error': None,
        'debug': {},
    }

    try:
        now = datetime.now(ET)
        if now.weekday() >= 5:  # weekend
            result['error'] = 'Weekend'
            return result

        # Premarket hours: 04:00 to 09:30 ET
        start = now.replace(hour=4, minute=0, second=0, microsecond=0)
        end = now.replace(hour=9, minute=30, second=0, microsecond=0)
        end = min(now, end)  # only up to current time

        if start >= end:
            result['error'] = 'Not premarket hours'
            return result

        # Fetch minute bars from Alpaca
        bars = api.get_bars(
            symbol,
            timeframe='1Min',
            start=start.isoformat(),
            end=end.isoformat(),
            adjustment='raw'
        )

        if bars is None:
            result['error'] = 'No bars returned (None)'
            return result

        df = bars.df
        result['debug']['bars_raw_count'] = len(df) if df is not None else 0

        if df is None or df.empty:
            result['error'] = 'Empty bars'
            result['debug']['df_empty'] = True
            return result

        # Compute PM metrics
        result['pm_volume'] = int(df['volume'].sum())
        result['pm_volume_raw'] = int(df['volume'].sum())
        result['pm_bars_count'] = len(df)

        result['pm_high'] = float(df['high'].max())
        result['pm_low'] = float(df['low'].min())
        result['pm_open'] = float(df['open'].iloc[0])

        # VWAP
        typical = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical * df['volume']).sum() / df['volume'].sum() if df['volume'].sum() > 0 else 0
        result['pm_vwap'] = float(vwap)

        # Time-adjusted RVOL (placeholder – will be replaced with real historical data)
        if result['pm_volume'] > 0:
            avg_volume = 50_000  # placeholder, not real RVOL
            if avg_volume > 0:
                result['rvol_time_adjusted'] = result['pm_volume'] / avg_volume
                result['data_quality'] = 'MEDIUM' if result['pm_volume'] > 100_000 else 'LOW'
            else:
                result['rvol_time_adjusted'] = 0.0
        else:
            result['rvol_time_adjusted'] = 0.0

        result['debug']['start_time'] = start.isoformat()
        result['debug']['end_time'] = end.isoformat()
        result['debug']['timezone'] = 'America/New_York'

    except Exception as e:
        result['error'] = str(e)
        result['debug']['exception'] = str(e)

    return result