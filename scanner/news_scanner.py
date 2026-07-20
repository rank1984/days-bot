"""
News scanner using Finnhub API for DAYS-BOT
Calculates catalyst impact scores and keywords for breakout tracking.
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

from utils.config import FINNHUB_API_KEY

class NewsScanner:
    def __init__(self, api_key: str = FINNHUB_API_KEY):
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
    
    def get_news(self, symbol: str) -> List[Dict[str, Any]]:
        """קבלת 5 ידיעות החדשות האחרונות עבור סימול ספציפי (24 שעות אחרונות)"""
        if not self.api_key:
            print("[NewsScanner] ⚠️ Finnhub API Key is missing.")
            return []
        
        # שימוש ב-company-news עבור מניה ספציפית לפי דרישות ה-API של Finnhub
        url = f"{self.base_url}/company-news"
        params = {
            "symbol": symbol,
            "token": self.api_key,
            "from": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "to": datetime.now().strftime("%Y-%m-%d"),
        }
        
        try:
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code != 200:
                return []
            data = resp.json()
            return data[:5]  # החזרת ה-5 המובילות
        except Exception as e:
            print(f"[NewsScanner] Error fetching news for {symbol}: {e}")
            return []
    
    def get_catalyst_news_score(self, symbol: str) -> Tuple[float, str]:
        """
        סורק את כותרות החדשות ומחזיר ציון משוקלל (0-15) לצד טקסט הקטליזטור המזוהה
        """
        news = self.get_news(symbol)
        if not news:
            return 0.0, "—"
        
        # איחוד הכותרות לטקסט אחד לטובת חיפוש מילות מפתח
        headlines_text = " ".join([article.get('headline', '') for article in news]).lower()
        
        score = 0.0
        catalyst = "—"
        
        # בדיקת מילות מפתח וקביעת משקולות
        if 'fda' in headlines_text or 'approval' in headlines_text:
            score += 10.0
            catalyst = "FDA Approval"
        if 'acquisition' in headlines_text or 'merger' in headlines_text:
            score += 8.0
            catalyst = "M&A"
        if 'earnings' in headlines_text or 'revenue' in headlines_text or 'eps' in headlines_text:
            score += 6.0
            catalyst = "Earnings"
        if 'contract' in headlines_text or 'partnership' in headlines_text or 'deal' in headlines_text:
            score += 5.0
            catalyst = "Contract/Partnership"
            
        # אם יש חדשות אך לא תפסנו מילת מפתח קריטית, ניקח את הכותרת הראשונה כקטליזטור כללי
        if score == 0.0 and news:
            catalyst = news[0].get('headline', '—')[:45] + "..."
            
        return min(score, 15.0), catalyst
