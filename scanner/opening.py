"""
DAYS-BOT V3.2 – Opening Confirmation (after 09:30 ET)
בודק מועמדים מה-Premarket שפרצו מעל PM High עם נפח ואישור VWAP.
"""
import pandas as pd
from datetime import datetime, timedelta
import pytz
import yfinance as yf
from typing import List, Dict, Any

ET = pytz.timezone("America/New_York")


def check_opening_confirmation(watchlist: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    מקבל רשימת מועמדים (כל אחד עם מפתחות: ticker, pm_high, pm_vwap, price, opportunity_score, ...)
    בודק 5 דקות אחרונות אחרי 09:30 ET:
      - מחיר נוכחי > pm_high (פריצה)
      - נפח ב-5 הדקות האחרונות לפחות פי 1.5 מהממוצע של 5 הדקות (או > 50K)
      - מחיר מעל VWAP של 5 הדקות
    מחזיר רשימה של מועמדים שעברו את האישור, עם שדות נוספים: current_price, breakout_price, confirmed_volume, confirmed_vwap
    """
    if not watchlist:
        return []

    now_et = datetime.now(ET)
    # אם לפני 09:30 – לא בודקים
    if now_et.time() < datetime.strptime("09:30", "%H:%M").time():
        print("[Opening] Before 09:30 ET – skipping confirmation.")
        return []

    print(f"[Opening] Checking {len(watchlist)} candidates at {now_et.strftime('%H:%M:%S')} ET")

    confirmed = []

    for candidate in watchlist:
        ticker = candidate['ticker']
        pm_high = candidate.get('pm_high', 0)
        pm_vwap = candidate.get('pm_vwap', 0)

        if pm_high <= 0 or pm_vwap <= 0:
            continue

        try:
            # נשלוף נתוני 1-minute ל-15 דקות אחרונות (כולל אחרי 09:30)
            data = yf.download(ticker, period="5d", interval="1m", prepost=True, progress=False)
            if data.empty:
                continue

            # נוודא timezone
            data.index = pd.to_datetime(data.index)
            if data.index.tz is None:
                data.index = data.index.tz_localize("UTC")
            data.index = data.index.tz_convert(ET)

            # נסנן רק רלוונטי: מ-09:30 ועד עכשיו
            session_start = ET.localize(datetime.combine(now_et.date(), datetime.strptime("09:30", "%H:%M").time()))
            data = data[data.index >= session_start]
            if data.empty:
                continue

            # ניקח את 5 הדקות האחרונות (או פחות אם אין)
            recent = data.tail(5)
            if len(recent) < 3:
                continue

            current_price = recent['Close'].iloc[-1]
            avg_volume = recent['Volume'].mean()
            last_volume = recent['Volume'].iloc[-1]

            # VWAP ל-5 דקות
            vwap = (recent['Close'] * recent['Volume']).sum() / recent['Volume'].sum() if recent['Volume'].sum() > 0 else recent['Close'].mean()

            # תנאי אישור:
            # 1. מחיר > PM High (פריצה)
            if current_price <= pm_high:
                continue

            # 2. נפח - לפחות פי 1.5 מהממוצע או לפחות 50K
            if last_volume < avg_volume * 1.5 and last_volume < 50000:
                continue

            # 3. מחיר מעל VWAP
            if current_price < vwap * 0.995:
                continue

            # העתקת המועמד והוספת שדות אישור
            confirmed_candidate = candidate.copy()
            confirmed_candidate['current_price'] = round(current_price, 4)
            confirmed_candidate['breakout_price'] = round(pm_high, 4)
            confirmed_candidate['confirmed_volume'] = last_volume
            confirmed_candidate['confirmed_vwap'] = round(vwap, 4)
            confirmed_candidate['confirmation_time'] = now_et.strftime('%H:%M:%S')
            confirmed.append(confirmed_candidate)

            print(f"[Opening] ✅ {ticker} confirmed at ${current_price:.2f} (breakout ${pm_high:.2f})")

        except Exception as e:
            print(f"[Opening] Error checking {ticker}: {e}")
            continue

    print(f"[Opening] Confirmed {len(confirmed)} out of {len(watchlist)}")
    return confirmed
