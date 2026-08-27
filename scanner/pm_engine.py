import os
from datetime import datetime, time
import pytz
import pandas as pd
from alpaca_trade_api.rest import REST, TimeFrame

def get_pm_data(symbol: str, current_price: float) -> dict:
    """
    Retrieves Pre-Market (04:00 - 09:30 ET) 1-minute bars from Alpaca API.
    Fixes timezones, explicitly sets feed='iex', and calculates signed distance.
    """
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL", "https://api.alpaca.markets")

    if not api_key or not secret_key:
        print(f"[PM Engine ERROR] {symbol}: Alpaca credentials missing from environment variables")
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "error": "ALPACA_CREDENTIALS_MISSING"
        }

    api = REST(api_key, secret_key, base_url, api_version='v2')

    # Force US/Eastern Timezone conversion
    et_tz = pytz.timezone("America/New_York")
    now_et = datetime.now(et_tz)

    # Build Pre-Market window for today (04:00 ET to 09:30 ET)
    pm_start_et = et_tz.localize(datetime.combine(now_et.date(), time(4, 0)))
    pm_end_et = et_tz.localize(datetime.combine(now_et.date(), time(9, 30)))

    # Cap window to current time if scanning during Pre-Market hours
    if now_et < pm_end_et:
        pm_end_et = now_et

    start_str = pm_start_et.isoformat()
    end_str = pm_end_et.isoformat()

    try:
        # Mandatory feed='iex' for Alpaca Free/Basic Subscription Tier
        bars = api.get_bars(
            symbol,
            TimeFrame.Minute,
            start=start_str,
            end=end_str,
            adjustment='raw',
            feed='iex'
        ).df

        if bars.empty:
            print(f"[PM Engine INFO] {symbol}: No PM bars returned from Alpaca between {start_str} and {end_str}")
            return {
                "pm_volume": 0,
                "pm_bars_count": 0,
                "pm_high": None,
                "pm_vwap": None,
                "pm_dist_signed": None,
                "pm_high_dist": None,
                "error": "NO_PM_BARS"
            }

        pm_bars_count = len(bars)
        pm_volume = int(bars['volume'].sum())
        pm_high = float(bars['high'].max())

        # Volume-Weighted Average Price (VWAP)
        total_vol = bars['volume'].sum()
        if total_vol > 0:
            pm_vwap = float((bars['close'] * bars['volume']).sum() / total_vol)
        else:
            pm_vwap = float(bars['close'].mean())

        # Distances: signed (actual) vs capped high_dist
        pm_dist_signed = float(((current_price - pm_high) / pm_high) * 100.0) if pm_high else 0.0
        pm_high_dist = max(0.0, pm_dist_signed)

        print(f"[PM RESULT] {symbol} | Bars: {pm_bars_count} | Vol: {pm_volume} | PM High: {pm_high:.2f} | PM VWAP: {pm_vwap:.2f} | Dist Signed: {pm_dist_signed:.2f}%")

        return {
            "pm_volume": pm_volume,
            "pm_bars_count": pm_bars_count,
            "pm_high": pm_high,
            "pm_vwap": pm_vwap,
            "pm_dist_signed": pm_dist_signed,
            "pm_high_dist": pm_high_dist,
            "error": None
        }

    except Exception as e:
        print(f"[PM Engine ERROR] {symbol}: {e}")
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "error": str(e)
        }
