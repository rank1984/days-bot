"""
VWAP Engine – חישוב VWAP חכם לשימוש ב-Entry/Targets
"""
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz

ET = pytz.timezone("America/New_York")


def calculate_vwap(ticker: str, lookback_minutes: int = 30) -> dict:
    """
    מחשב VWAP לפי X דקות אחרונות (כולל פרה-מרקט)
    מחזיר: vwap, high_vwap, low_vwap, vwap_support, vwap_resistance
    """
    try:
        now_et = datetime.now(ET)
        start = now_et - timedelta(minutes=lookback_minutes)

        data = yf.download(ticker, period="1d", interval="1m", prepost=True, progress=False)
        if data.empty:
            return {}

        data.index = pd.to_datetime(data.index)
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC")
        data.index = data.index.tz_convert(ET)

        data = data[data.index >= start]
        if data.empty:
            return {}

        # VWAP
        total_value = (data['Close'] * data['Volume']).sum()
        total_volume = data['Volume'].sum()
        if total_volume == 0:
            return {}

        vwap = total_value / total_volume

        # רמות תמיכה/התנגדות
        high_vwap = data['High'].max()
        low_vwap = data['Low'].min()

        # VWAP ± 0.5%
        vwap_support = vwap * 0.995
        vwap_resistance = vwap * 1.005

        return {
            "vwap": round(vwap, 4),
            "vwap_high": round(high_vwap, 4),
            "vwap_low": round(low_vwap, 4),
            "vwap_support": round(vwap_support, 4),
            "vwap_resistance": round(vwap_resistance, 4),
            "lookback_minutes": lookback_minutes,
            "total_volume": int(total_volume)
        }

    except Exception as e:
        print(f"[VWAP] Error for {ticker}: {e}")
        return {}


def calculate_pm_vwap_from_candidate(candidate: dict) -> dict:
    """
    מקבל מועמד עם pm_high, pm_low, pm_vwap, מחזיר רמות
    """
    pm_vwap = candidate.get('pm_vwap', 0)
    pm_high = candidate.get('pm_high', 0)
    pm_low = candidate.get('pm_low', 0)

    if pm_vwap <= 0 or pm_high <= 0:
        return {}

    return {
        "vwap": round(pm_vwap, 4),
        "vwap_high": round(pm_high, 4),
        "vwap_low": round(pm_low, 4),
        "vwap_support": round(pm_vwap * 0.995, 4),
        "vwap_resistance": round(pm_vwap * 1.005, 4),
        "pm_range": round(pm_high - pm_low, 4),
        "source": "premarket"
    }
