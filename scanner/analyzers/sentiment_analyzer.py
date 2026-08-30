"""
מנתח סנטימנט – StockTwits + Google Trends
"""
import requests
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
            return round(data[ticker].mean(), 1)
    except:
        pass
    return None

def get_combined_sentiment(ticker: str) -> dict:
    """מחזיר מילון עם סנטימנט StockTwits ופופולריות גוגל"""
    st_sent = get_stocktwits_sentiment(ticker)
    gt_score = get_google_trends_score(ticker)
    # נורמליזציה של google trends ל-[-1,1] בקירוב
    gt_norm = (gt_score / 50) - 1 if gt_score is not None else 0
    combined = 0.0
    if st_sent is not None:
        combined += st_sent * 0.6
    if gt_score is not None:
        combined += gt_norm * 0.4
    return {
        "stocktwits": st_sent,
        "google_trends": gt_score,
        "combined": round(combined, 2)
    }
