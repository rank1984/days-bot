"""
מנתח סנטימנט – שימוש ב-StockTwits API (חינמי) + Google Trends (pytrends)
"""
import requests
import time
# לניווט בגוגל טרנדים – צריך להתקין: pip install pytrends
from pytrends.request import TrendReq

def get_stocktwits_sentiment(ticker: str) -> float:
    """מחזיר סנטימנט מ-StockTwits (בין -1 ל-1)"""
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            messages = data.get('messages', [])
            if messages:
                # ניקח 20 הודעות אחרונות ונספור חיוביות/שליליות
                positive = sum(1 for m in messages[:20] if m.get('entities', {}).get('sentiment', {}).get('basic') == 'Bullish')
                negative = sum(1 for m in messages[:20] if m.get('entities', {}).get('sentiment', {}).get('basic') == 'Bearish')
                total = positive + negative
                if total > 0:
                    return round((positive - negative) / total, 2)
    except:
        pass
    return None

def get_google_trends_score(ticker: str) -> float:
    """מחזיר ערך בין 0 ל-100 – פופולריות בחיפוש ב-24 שעות"""
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        pytrends.build_payload([ticker], timeframe='now 1-d')
        data = pytrends.interest_over_time()
        if not data.empty:
            # ממוצע הפופולריות ב-24 שעות
            return round(data[ticker].mean(), 1)
    except:
        pass
    return None

def get_combined_sentiment(ticker: str) -> dict:
    """מחזיר מילון עם סנטימנט StockTwits ופופולריות גוגל"""
    st_sent = get_stocktwits_sentiment(ticker)
    gt_score = get_google_trends_score(ticker)
    return {
        "stocktwits": st_sent,
        "google_trends": gt_score,
        "combined": (st_sent if st_sent else 0) * 0.6 + (gt_score/100 if gt_score else 0) * 0.4
    }
