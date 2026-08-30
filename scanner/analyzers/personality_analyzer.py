"""
Stock Personality Analyzer – בודק איך המניה התנהגה בעבר אחרי גאפים דומים
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

ET = pytz.timezone("America/New_York")


def get_stock_personality(ticker: str, current_gap: float) -> dict:
    """
    מחזיר:
    - avg_gap_following: 1 = בד"כ ממשיכה, 0 = בד"כ קורסת
    - avg_30min_return: תשואה ממוצעת 30 דקות אחרי פתיחה בגאפ דומה
    - failure_rate: אחוז הפעמים שהמניה ירדה תוך שעה
    - sample_size: מספר האירועים שנמצאו
    """
    result = {
        "avg_gap_following": 0.5,
        "avg_30min_return": 0,
        "failure_rate": 50,
        "sample_size": 0,
        "personality": "NEUTRAL"
    }

    try:
        # שליפת נתוני 5 דקות לשנה האחרונה
        end = datetime.now()
        start = end - timedelta(days=365)

        data = yf.download(ticker, start=start, end=end, interval="5m", progress=False)
        if data.empty or len(data) < 50:
            return result

        # נוסיף עמודת Gap לעומת סגירה קודמת
        data['prev_close'] = data['Close'].shift(1)
        data['gap'] = (data['Open'] - data['prev_close']) / data['prev_close'] * 100

        # נסנן אירועי Gap דומים (בטווח של 50% מהגאפ הנוכחי)
        gap_threshold = current_gap * 0.5
        similar_gaps = data[
            (data['gap'] >= current_gap - gap_threshold) &
            (data['gap'] <= current_gap + gap_threshold) &
            (data['gap'] > 5) &
            (data['Volume'] > 50000)
        ]

        if similar_gaps.empty:
            return result

        # עבור כל אירוע – תשואה אחרי 30 דקות (6 ברים של 5 דקות)
        returns = []
        failures = 0
        for idx in similar_gaps.index:
            pos = data.index.get_loc(idx)
            if pos + 6 >= len(data):
                continue
            future_price = data.iloc[pos + 6]['Close']
            current_price = data.iloc[pos]['Open']
            ret = (future_price - current_price) / current_price * 100
            returns.append(ret)
            if ret < -2:  # ירידה של יותר מ-2% = כישלון
                failures += 1

        if returns:
            avg_ret = sum(returns) / len(returns)
            failure_pct = (failures / len(returns)) * 100

            result["avg_gap_following"] = 1 if avg_ret > 0 else 0
            result["avg_30min_return"] = round(avg_ret, 2)
            result["failure_rate"] = round(failure_pct, 1)
            result["sample_size"] = len(returns)

            if avg_ret > 3 and failure_pct < 30:
                result["personality"] = "STRONG_FOLLOWER"
            elif avg_ret > 0 and failure_pct < 40:
                result["personality"] = "FOLLOWER"
            elif avg_ret > -1:
                result["personality"] = "NEUTRAL"
            else:
                result["personality"] = "GAP_AND_CRAP"

        return result

    except Exception as e:
        print(f"[Personality] Error for {ticker}: {e}")
        return result
