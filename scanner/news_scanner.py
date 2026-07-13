"""
News scanner using Finnhub API
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any

from utils.config import FINNHUB_API_KEY

class NewsScanner:
    def __init__(self, api_key: str = FINNHUB_API_KEY):
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
    
    def get_news(self, symbol: str) -> List[Dict[str, Any]]:
        """Get latest news for a symbol"""
        if not self.api_key:
            return []
        
        # Finnhub free tier allows limited requests
        url = f"{self.base_url}/news"
        params = {
            "symbol": symbol,
            "token": self.api_key,
            "from": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "to": datetime.now().strftime("%Y-%m-%d"),
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data[:5]  # return top 5
        except Exception as e:
            print(f"[NewsScanner] Error for {symbol}: {e}")
            return []
    
    def get_catalyst(self, symbol: str) -> str:
        """Get catalyst headline for a symbol"""
        news = self.get_news(symbol)
        if not news:
            return "—"
        
        # Return first headline with catalyst keywords
        keywords = ["fda", "approval", "contract", "acquisition", "merger", 
                   "earnings", "revenue", "partnership", "breakthrough"]
        for article in news:
            headline = article.get("headline", "").lower()
            if any(k in headline for k in keywords):
                return article.get("headline", "—")
        
        return news[0].get("headline", "—")[:50] + "..."
