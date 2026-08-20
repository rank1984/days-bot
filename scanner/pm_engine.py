"""
Premarket Engine – calculates PM High, Low, Volume, VWAP, RVOL from minute bars
"""
import pandas as pd
import pytz
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import yfinance as yf

ET = pytz.timezone('America/New_York')

def get_premarket_minute_data(symbol: str) -> Dict[str, Any]:
    """
    Fetches premarket minute bars (04:00-09:30 ET) and computes:
    - pm_high, pm_low, pm_volume, pm_vwap
    - time-adjusted RVOL (compared to median of last 5 sessions)
    """
    result = {
        'pm_high': 0.0,
        'pm_low': 0.0,
        'pm_volume': 0,
        'pm_vwap': 0.0,
        'pm_open': 0.0,
        'rvol_time_adjusted': 0.0,
        'data_quality': 'LOW',
        'median_pm_volume': 0,
    }
    try:
        # Get today's premarket data
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="1m", prepost=True)
        if df.empty:
            return result

        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert(ET)
        else:
            df.index = df.index.tz_convert(ET)

        premarket = df[(df.index.hour < 9) | ((df.index.hour == 9) & (df.index.minute < 30))]
        if premarket.empty:
            return result

        # Today's PM metrics
        result['pm_high'] = float(premarket['High'].max())
        result['pm_low'] = float(premarket['Low'].min())
        result['pm_volume'] = int(premarket['Volume'].sum())
        result['pm_open'] = float(premarket['Open'].iloc[0])

        # VWAP
        typical = (premarket['High'] + premarket['Low'] + premarket['Close']) / 3
        vwap = (typical * premarket['Volume']).sum() / premarket['Volume'].sum() if premarket['Volume'].sum() > 0 else 0
        result['pm_vwap'] = float(vwap)

        # Historical median PM volume (last 5 days)
        hist_volumes = []
        for i in range(1, 6):
            day = datetime.now(ET) - timedelta(days=i)
            df_hist = ticker.history(start=day.strftime('%Y-%m-%d'), end=(day+timedelta(days=1)).strftime('%Y-%m-%d'), interval='1m', prepost=True)
            if df_hist.empty:
                continue
            if df_hist.index.tz is None:
                df_hist.index = df_hist.index.tz_localize('UTC').tz_convert(ET)
            else:
                df_hist.index = df_hist.index.tz_convert(ET)
            pm_hist = df_hist[(df_hist.index.hour < 9) | ((df_hist.index.hour == 9) & (df_hist.index.minute < 30))]
            if not pm_hist.empty:
                hist_volumes.append(int(pm_hist['Volume'].sum()))

        if hist_volumes:
            median_vol = sorted(hist_volumes)[len(hist_volumes)//2]
            result['median_pm_volume'] = median_vol
            result['rvol_time_adjusted'] = result['pm_volume'] / median_vol if median_vol > 0 else 0.0
            result['data_quality'] = 'HIGH' if result['pm_volume'] > 100_000 else 'MEDIUM'
        else:
            result['data_quality'] = 'LOW'

    except Exception as e:
        print(f"[PMEngine] Error for {symbol}: {e}")
    return result
