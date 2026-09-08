"""
DAYS-BOT V5.0.4 – VWAP Engine
Calculates VWAP from 1-minute bars.
Always returns scalars, never pandas Series.
If no data, returns empty dict (vwap = None).
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

ET = pytz.timezone("America/New_York")


def _to_float(value, default=None):
    """Convert pandas Series/DataFrame to scalar float."""
    try:
        if value is None:
            return default
        if isinstance(value, (pd.Series, pd.DataFrame)):
            if value.empty:
                return default
            if hasattr(value, 'iloc'):
                value = value.iloc[-1]
            elif hasattr(value, 'values'):
                value = value.values[-1] if len(value.values) > 0 else default
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_columns(data):
    """
    Handle yfinance MultiIndex columns.
    Convert ('Close', 'AAPL') -> 'Close' for single-ticker downloads.
    """
    if data is None or data.empty:
        return data

    if isinstance(data.columns, pd.MultiIndex):
        # Keep only the first level (price type) and drop ticker level
        data.columns = data.columns.get_level_values(0)
    
    # Drop duplicate columns if any
    data = data.loc[:, ~data.columns.duplicated()]
    return data


def calculate_vwap(ticker: str, lookback_minutes: int = 30) -> dict:
    """
    Calculate VWAP using yfinance 1-minute bars.
    Returns a dict with scalar values.
    If no data: returns empty dict.
    """
    try:
        now_et = datetime.now(ET)
        start = now_et - timedelta(minutes=lookback_minutes + 5)

        data = yf.download(
            ticker,
            period="5d",
            interval="1m",
            prepost=True,
            progress=False,
            auto_adjust=False,
            threads=False,
        )

        if data is None or data.empty:
            return {}

        # Normalize MultiIndex columns
        data = _normalize_columns(data)

        # Normalize timezone
        data.index = pd.to_datetime(data.index)
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC")
        data.index = data.index.tz_convert(ET)

        # Filter to last N minutes
        data = data[data.index >= start]
        if data.empty:
            return {}

        # Ensure we have required columns
        required = {'Close', 'Volume', 'High', 'Low'}
        if not required.issubset(set(data.columns)):
            print(f"[VWAP] Missing columns for {ticker}")
            return {}

        # Convert to float (scalar-safe)
        close = _to_float(data['Close'].iloc[-1]) if not data['Close'].empty else 0
        if close == 0:
            return {}

        volume_sum = _to_float(data['Volume'].sum(), 0)
        if volume_sum == 0:
            return {}

        vwap = _to_float((data['Close'] * data['Volume']).sum() / volume_sum, None)
        if vwap is None or vwap <= 0:
            return {}

        vwap_high = _to_float(data['High'].max(), 0)
        vwap_low = _to_float(data['Low'].min(), 0)

        return {
            "vwap": round(vwap, 4),
            "vwap_high": round(vwap_high, 4),
            "vwap_low": round(vwap_low, 4),
            "vwap_support": round(vwap * 0.995, 4),
            "vwap_resistance": round(vwap * 1.005, 4),
            "lookback_minutes": lookback_minutes,
            "total_volume": int(volume_sum),
            "data_quality": "GOOD",
        }

    except Exception as e:
        print(f"[VWAP] Error for {ticker}: {e}")
        return {}


def calculate_pm_vwap_from_candidate(candidate: dict) -> dict:
    """Fallback: use PM data from candidate (if available)."""
    pm_vwap = _to_float(candidate.get('pm_vwap', 0), None)
    pm_high = _to_float(candidate.get('pm_high', 0), None)
    pm_low = _to_float(candidate.get('pm_low', 0), None)

    if pm_vwap is None or pm_vwap <= 0 or pm_high is None or pm_high <= 0:
        return {}

    return {
        "vwap": round(pm_vwap, 4),
        "vwap_high": round(pm_high, 4),
        "vwap_low": round(pm_low, 4) if pm_low else round(pm_high * 0.98, 4),
        "vwap_support": round(pm_vwap * 0.995, 4),
        "vwap_resistance": round(pm_vwap * 1.005, 4),
        "source": "premarket",
        "data_quality": "PARTIAL",
    }
