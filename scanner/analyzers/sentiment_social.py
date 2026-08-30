"""
Social Sentiment Analyzer – StockTwits + Reddit (PRAW)
"""
import requests
import time

def get_stocktwits_sentiment(ticker: str) -> dict:
    """מחזיר מילון: bull_pct, bear_pct, total_messages, sentiment_score (-1..1)"""
    result = {
        "bull_pct": 0,
        "bear_pct": 0,
        "total_messages": 0,
        "sentiment_score": 0
    }
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            messages = data.get('messages', [])
            if messages:
                total = len(messages[:30])
                if total == 0:
                    return result
                positive = sum(1 for m in messages[:30] if m.get('entities', {}).get('sentiment', {}).get('basic') == 'Bullish')
                negative = sum(1 for m in messages[:30] if m.get('entities', {}).get('sentiment', {}).get('basic') == 'Bearish')
                result["bull_pct"] = round(positive / total * 100, 1)
                result["bear_pct"] = round(negative / total * 100, 1)
                result["total_messages"] = total
                result["sentiment_score"] = round((positive - negative) / total, 2)
    except Exception as e:
        print(f"[Sentiment] StockTwits error for {ticker}: {e}")
    return result


def get_reddit_sentiment(ticker: str) -> dict:
    """
    (אופציונלי) בודק את r/wallstreetbets, r/pennystocks, r/smallcapstock
    דורש התקנת PRAW ו-API keys מ-Reddit.
    אם אין – מחזיר נתוני ברירת מחדל.
    """
    # נתחיל עם נתוני דמה – אפשר להרחיב בהמשך
    return {
        "mentions": 0,
        "avg_score": 0,
        "sentiment": 0
    }
