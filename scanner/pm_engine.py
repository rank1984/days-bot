"""
PM_ENGINE V2.12.2 – PREMARKET DATA ENGINE (FULL CALCULATIONS INTACT)
"""
from datetime import datetime
import pytz

ET = pytz.timezone('America/New_York')


def get_premarket_minute_data(symbol: str, api) -> dict:
    """
    Fetches premarket minute bars for symbol using Alpaca REST API (feed='iex').
    Returns fully computed PM metrics expected by scanner modules.
    """
    try:
        now_et = datetime.now(ET)
        today_str = now_et.strftime("%Y-%m-%d")

        start_dt = f"{today_str}T04:00:00-04:00"
        end_dt = now_et.isoformat()

        # Clean 1Min call without parameter duplication
        bars = api.get_bars(
            symbol,
            "1Min",
            start=start_dt,
            end=end_dt,
            feed='iex'
        )

        bar_list = list(bars)
        if not bar_list:
            return {
                'error': None,
                'pm_volume': 0,
                'pm_high': 0.0,
                'pm_vwap': 0.0,
                'pm_bars_count': 0,
                'pm_high_dist': 999.0,
                'rvol_time_adjusted': None
            }

        # Full PM metrics calculations
        pm_volume = sum(b.v for b in bar_list)
        pm_high = max(b.h for b in bar_list)
        
        # Weighted VWAP calculation
        sum_pv = sum(b.v * ((b.h + b.l + b.c) / 3.0) for b in bar_list)
        pm_vwap = (sum_pv / pm_volume) if pm_volume > 0 else 0.0

        current_price = bar_list[-1].c
        pm_high_dist = ((pm_high - current_price) / current_price) * 100.0 if current_price > 0 else 999.0

        return {
            'error': None,
            'pm_volume': pm_volume,
            'pm_high': pm_high,
            'pm_vwap': pm_vwap,
            'pm_bars_count': len(bar_list),
            'pm_high_dist': pm_high_dist,
            'rvol_time_adjusted': None
        }

    except Exception as e:
        return {
            'error': str(e),
            'pm_volume': 0,
            'pm_high': 0.0,
            'pm_vwap': 0.0,
            'pm_bars_count': 0,
            'pm_high_dist': 999.0,
            'rvol_time_adjusted': None
        }
