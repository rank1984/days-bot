import os
from datetime import datetime, time
import pytz
import pandas as pd
from alpaca_trade_api.rest import REST, TimeFrame

def get_premarket_minute_data(symbol: str, current_price: float = None) -> dict:
    """
    Retrieves Pre-Market (04:00 - 09:30 ET) 1-minute bars using Alpaca SIP Feed.
    Calculates Typical-Price VWAP, signed/absolute distance from PM High, and PM metrics.
    """
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL", "https://api.alpaca.markets")

    if not api_key or not secret_key:
        print(f"[PM ENGINE ERROR] {symbol}: Alpaca credentials missing from environment variables")
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "rvol": None,
            "rvol_method": "UNAVAILABLE",
            "error": "ALPACA_CREDENTIALS_MISSING"
        }

    api = REST(api_key, secret_key, base_url, api_version='v2')

    et_tz = pytz.timezone("America/New_York")
    now_et = datetime.now(et_tz)

    pm_start_et = et_tz.localize(datetime.combine(now_et.date(), time(4, 0)))
    pm_end_et = et_tz.localize(datetime.combine(now_et.date(), time(9, 30)))

    if now_et < pm_end_et:
        pm_end_et = now_et

    start_str = pm_start_et.isoformat()
    end_str = pm_end_et.isoformat()

    print(f"[PM ENGINE] {symbol} | window={start_str} -> {end_str} | feed=SIP")

    try:
        # Fetch directly using SIP feed
        bars_response = api.get_bars(
            symbol,
            TimeFrame.Minute,
            start=start_str,
            end=end_str,
            adjustment='raw',
            feed='sip'
        )
        bars = bars_response.df

        if bars.empty:
            print(f"[PM ENGINE INFO] {symbol}: No PM bars returned from Alpaca SIP feed")
            return {
                "pm_volume": 0,
                "pm_bars_count": 0,
                "pm_high": None,
                "pm_vwap": None,
                "pm_dist_signed": None,
                "pm_high_dist": None,
                "rvol": None,
                "rvol_method": "UNAVAILABLE",
                "error": "NO_PM_BARS"
            }

        pm_bars_count = len(bars)
        pm_volume = int(bars['volume'].sum())
        pm_high = float(bars['high'].max())

        # Volume-Weighted Average Price using Typical Price: (High + Low + Close) / 3
        total_vol = bars['volume'].sum()
        if total_vol > 0:
            typical_price = (bars['high'] + bars['low'] + bars['close']) / 3.0
            pm_vwap = float((typical_price * bars['volume']).sum() / total_vol)
        else:
            pm_vwap = float(bars['close'].mean())

        # Distance calculation
        price_for_dist = current_price if (current_price is not None and current_price > 0) else float(bars['close'].iloc[-1])
        pm_dist_signed = (((price_for_dist - pm_high) / pm_high) * 100.0) if pm_high else None
        pm_high_dist = abs(pm_dist_signed) if pm_dist_signed is not None else None

        print(f"[PM RESULT] {symbol} | Bars: {pm_bars_count} | Vol: {pm_volume} | PM High: {pm_high:.2f} | PM VWAP: {pm_vwap:.2f} | Abs Dist: {pm_high_dist:.2f}%")

        return {
            "pm_volume": pm_volume,
            "pm_bars_count": pm_bars_count,
            "pm_high": pm_high,
            "pm_vwap": pm_vwap,
            "pm_dist_signed": pm_dist_signed,
            "pm_high_dist": pm_high_dist,
            "rvol": None,
            "rvol_method": "UNAVAILABLE",
            "error": None
        }

    except Exception as e:
        print(f"[PM ENGINE ERROR] {symbol}: SIP feed failed: {e}")
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "rvol": None,
            "rvol_method": "UNAVAILABLE",
            "error": f"SIP_FEED_ERROR: {e}"
        }

# Alias for compatibility across all imports
get_pm_data = get_premarket_minute_data
