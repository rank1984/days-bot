import os
from datetime import datetime, time
import pytz
import pandas as pd
from alpaca_trade_api.rest import REST, TimeFrame

from utils.config import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_BASE_URL,
)

ET = pytz.timezone("America/New_York")


def fetch_pm_data(symbol: str, current_price: float = None) -> dict:
    """
    Fetches Premarket minute bars for the 08:00 ET -> 09:30 ET window via IEX feed.
    Calculates PM High, VWAP, Data Quality, and Signed Distance metrics.
    """
    api = REST(
        ALPACA_API_KEY,
        ALPACA_SECRET_KEY,
        ALPACA_BASE_URL,
        api_version="v2",
    )
    
    now_et = datetime.now(ET)

    pm_start_et = ET.localize(
        datetime.combine(now_et.date(), time(8, 0))
    )
    pm_end_et = ET.localize(
        datetime.combine(now_et.date(), time(9, 30))
    )

    # Never read beyond current time
    pm_end_et = min(now_et, pm_end_et)

    if now_et < pm_start_et:
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "pm_data_quality": "NOT_STARTED",
            "error": "PREMARKET_NOT_STARTED",
            "rvol_time_adjusted": None,
        }

    if pm_end_et <= pm_start_et:
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "pm_data_quality": "NO_DATA",
            "error": "NO_PREMARKET_WINDOW",
            "rvol_time_adjusted": None,
        }

    try:
        response = api.get_bars(
            symbol,
            TimeFrame.Minute,
            start=pm_start_et.isoformat(),
            end=pm_end_et.isoformat(),
            adjustment="raw",
            feed="iex",
        )
        df = response.df

        if df is None or df.empty:
            return {
                "pm_volume": 0,
                "pm_bars_count": 0,
                "pm_high": None,
                "pm_vwap": None,
                "pm_dist_signed": None,
                "pm_high_dist": None,
                "pm_data_quality": "NO_DATA",
                "error": "EMPTY_BARS",
                "rvol_time_adjusted": None,
            }

        pm_bars_count = len(df)
        pm_volume = int(df["volume"].sum())

        # Data Quality Classification
        if pm_bars_count >= 10:
            pm_data_quality = "GOOD_DATA"
        elif pm_bars_count >= 1:
            pm_data_quality = "LOW_DATA"
        else:
            pm_data_quality = "NO_DATA"

        pm_high = float(df["high"].max())
        
        # Calculate VWAP
        if pm_volume > 0:
            pm_vwap = float((df["close"] * df["volume"]).sum() / pm_volume)
        else:
            pm_vwap = current_price

        # Signed distance and high distance metrics
        ref_price = current_price if current_price is not None else float(df["close"].iloc[-1])
        
        if pm_high and pm_high > 0:
            pm_dist_signed = ((ref_price - pm_high) / pm_high) * 100.0
            pm_high_dist = max(0.0, -pm_dist_signed)
        else:
            pm_dist_signed = None
            pm_high_dist = None

        return {
            "pm_volume": pm_volume,
            "pm_bars_count": pm_bars_count,
            "pm_high": pm_high,
            "pm_vwap": pm_vwap,
            "pm_dist_signed": pm_dist_signed,
            "pm_high_dist": pm_high_dist,
            "pm_data_quality": pm_data_quality,
            "error": None,
            "rvol_time_adjusted": None,  # Informational placeholder
        }

    except Exception as e:
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "pm_data_quality": "ERROR",
            "error": f"{type(e).__name__}: {e}",
            "rvol_time_adjusted": None,
        }
