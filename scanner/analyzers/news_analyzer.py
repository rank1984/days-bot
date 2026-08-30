"""
מנתח חדשות – שימוש ב-Finnhub API (חינמי) לשליפת כותרות אחרונות
"""
import requests
from utils.config import FINNHUB_API_KEY

def fetch_news(ticker: str) -> list:
    """מחזיר רשימה של 5 כותרות חדשות אחרונות"""
    try:
        url = f"https://finnhub.io/api/v1/news?symbol={ticker}&token={FINNHUB_API_KEY}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            headlines = [item['headline'] for item in data[:5]]
            return headlines
        else:
            return []
    except:
        return []
