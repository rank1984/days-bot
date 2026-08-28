import pytz
from datetime import datetime, time
from alpaca_trade_api.rest import REST, TimeFrame

from utils.config import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_BASE_URL,
    BOT_VERSION,
)

ET = pytz.timezone("America/New_York")


def fetch_pm_data(symbol: str, current_price: float = None) -> dict:
    """
    Fetches Premarket minute bars strictly for the 08:00 ET -> 09:30 ET window via IEX feed.
    Calculates PM High, VWAP, Data Quality, and Signed Distance metrics.
    """
    now_et = datetime.now(ET)
    now_time = now_et.time()

    # Strict hard checks for window
    if now_time < time(8, 0):
        print(f"[PM Engine] {BOT_VERSION} – Too early for IEX PM experiment: {now_et.strftime('%H:%M:%S')} ET")
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "error": "PREMARKET_NOT_STARTED_8AM",
            "rvol": None,
            "rvol_status": "UNAVAILABLE",
        }

    if now_time >= time(9, 30):
        print(f"[PM Engine] {BOT_VERSION} – Market already open: {now_et.strftime('%H:%M:%S')} ET")
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "error": "MARKET_ALREADY_OPEN",
            "rvol": None,
            "rvol_status": "UNAVAILABLE",
        }

    pm_start_et = ET.localize(datetime.combine(now_et.date(), time(8, 0)))
    pm_end_et = min(now_et, ET.localize(datetime.combine(now_et.date(), time(9, 30))))

    api = REST(
        ALPACA_API_KEY,
        ALPACA_SECRET_KEY,
        ALPACA_BASE_URL,
        api_version="v2",
    )

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
                "error": "EMPTY_BARS",
                "rvol": None,
                "rvol_status": "UNAVAILABLE",
            }

        pm_bars_count = len(df)
        pm_volume = int(df["volume"].sum())
        pm_high = float(df["high"].max())
        
        # Calculate PM VWAP
        if pm_volume > 0:
            pm_vwap = float((df["close"] * df["volume"]).sum() / pm_volume)
        else:
            pm_vwap = current_price

        # Signed distance metrics
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
            "error": None,
            "rvol": None,
            "rvol_status": "UNAVAILABLE",
        }

    except Exception as e:
        return {
            "pm_volume": 0,
            "pm_bars_count": 0,
            "pm_high": None,
            "pm_vwap": None,
            "pm_dist_signed": None,
            "pm_high_dist": None,
            "error": f"{type(e).__name__}: {e}",
            "rvol": None,
            "rvol_status": "UNAVAILABLE",
        }
