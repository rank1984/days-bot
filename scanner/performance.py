"""
performance.py
--------------
מעדכן מחירים בסוף יום: Open, HOD, Close.
שולף נתונים מ-Alpaca.
"""

import requests
from datetime import datetime, timedelta
import pytz

from database.db import get_week_performance, update_performance
from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY

ET      = pytz.timezone("America/New_York")
HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}


def fetch_day_bar(ticker: str, date: str) -> dict:
    """שולף bar יומי מ-Alpaca עבור תאריך נתון."""
    try:
        url    = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
        params = {
            "timeframe": "1Day",
            "start":     date + "T00:00:00Z",
            "end":       date + "T23:59:59Z",
            "feed":      "iex",
            "limit":     1,
        }
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if resp.status_code == 200:
            bars = resp.json().get("bars", [])
            if bars:
                return bars[0]
    except Exception as e:
        print(f"[Performance] Error fetching {ticker}: {e}")
    return {}


def update_daily_performance():
    """
    רץ בסוף יום המסחר.
    מעדכן Open, HOD, Close לכל התראה של היום.
    """
    today    = datetime.now(ET).strftime("%Y-%m-%d")
    pending  = get_week_performance()
    today_alerts = [r for r in pending if r["alert_date"] == today
                    and r["close_price"] is None]

    if not today_alerts:
        print("[Performance] Nothing to update today.")
        return

    print(f"[Performance] Updating {len(today_alerts)} alerts...")

    for alert in today_alerts:
        ticker = alert["ticker"]
        bar    = fetch_day_bar(ticker, today)

        if not bar:
            print(f"[Performance] No bar for {ticker}")
            continue

        update_performance(ticker, today, "open_price", bar.get("o", 0))
        update_performance(ticker, today, "hod",        bar.get("h", 0))
        update_performance(ticker, today, "close_price", bar.get("c", 0))
        print(f"[Performance] {ticker} O:{bar.get('o')} H:{bar.get('h')} C:{bar.get('c')}")
