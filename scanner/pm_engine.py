import os
import pytz
import requests
from datetime import datetime
from utils.config import FINNHUB_API_KEY


def get_premarket_minute_data(symbol: str, api=None) -> dict:
    """
    שולף נתוני 1Min Pre-Market מ-Finnhub (מכסה את כל הבורסות בארה"ב - SIP).
    תומך בכיסוי מלא החל מ-04:00 ET וכולל מניות Micro-Cap.
    
    :param symbol: סימול המניה (למשל 'CRMG')
    :param api: פרמטר אופציונלי לשמירה על תאימות לאחור
    :return: דיקשנרי עם נתוני נפח, בארים, שיא ו-VWAP
    """
    ET = pytz.timezone('America/New_York')
    now_et = datetime.now(ET)

    # הגדרת תחילת חלון הפרימרקט של היום הנוכחי בשעה 04:00 ET
    pm_start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)

    # המרה ל-Timestamps בשניות (כפי שדורש ה-API של Finnhub)
    from_ts = int(pm_start.timestamp())
    to_ts = int(now_et.timestamp())

    # בדיקת תקינות מפתח API
    token = FINNHUB_API_KEY or os.getenv("FINNHUB_API_KEY")
    if not token:
        return {
            "pm_bars_count": 0,
            "pm_volume": 0,
            "pm_high": 0.0,
            "pm_vwap": 0.0,
            "price": 0.0,
            "error": "FINNHUB_API_KEY is missing from environment/config"
        }

    url = "https://finnhub.io/api/v1/stock/candle"
    params = {
        "symbol": symbol.upper(),
        "resolution": "1",
        "from": from_ts,
        "to": to_ts,
        "token": token
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return {
                "pm_bars_count": 0,
                "pm_volume": 0,
                "pm_high": 0.0,
                "pm_vwap": 0.0,
                "price": 0.0,
                "error": f"HTTP Error {response.status_code}"
            }

        data = response.json()

        # Finnhub מחזיר 's': 'ok' כשיש נתונים, או 's': 'no_data' כשאין עסקאות
        if data.get("s") != "ok":
            return {
                "pm_bars_count": 0,
                "pm_volume": 0,
                "pm_high": 0.0,
                "pm_vwap": 0.0,
                "price": 0.0,
                "error": None
            }

        volumes = data.get("v", [])
        highs = data.get("h", [])
        closes = data.get("c", [])

        if not volumes:
            return {
                "pm_bars_count": 0,
                "pm_volume": 0,
                "pm_high": 0.0,
                "pm_vwap": 0.0,
                "price": 0.0,
                "error": None
            }

        total_volume = int(sum(volumes))
        pm_high = float(max(highs)) if highs else 0.0
        latest_price = float(closes[-1]) if closes else 0.0

        # חישוב VWAP משוקלל נפח
        total_pv = sum(p * v for p, v in zip(closes, volumes))
        pm_vwap = round(total_pv / total_volume, 4) if total_volume > 0 else 0.0

        return {
            "pm_bars_count": len(volumes),
            "pm_volume": total_volume,
            "pm_high": pm_high,
            "pm_vwap": pm_vwap,
            "price": latest_price,
            "error": None
        }

    except Exception as e:
        return {
            "pm_bars_count": 0,
            "pm_volume": 0,
            "pm_high": 0.0,
            "pm_vwap": 0.0,
            "price": 0.0,
            "error": str(e)
        }
