"""
Data fetcher using Polygon.io for premarket data
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time

from utils.config import POLYGON_API_KEY

class PolygonDataFetcher:
    def __init__(self, api_key: str = POLYGON_API_KEY):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.session = requests.Session()
        self.session.params = {"apiKey": self.api_key}
    
    def get_premarket_snapshot(self, symbols: List[str]) -> Dict[str, Any]:
        """Get premarket data for a list of symbols"""
        url = f"{self.base_url}/v2/snapshot/locale/us/markets/stocks/tickers"
        params = {
            "tickers": ",".join(symbols[:100]),  # Polygon limits
        }
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results = {}
            for ticker in data.get("tickers", []):
                t = ticker.get("ticker", {})
                # Premarket data
                pre = ticker.get("premarket", {})
                results[t] = {
                    "symbol": t,
                    "price": pre.get("last", 0),
                    "volume": pre.get("volume", 0),
                    "high": pre.get("high", 0),
                    "low": pre.get("low", 0),
                    "vwap": pre.get("vwap", 0),
                    "change": pre.get("change", 0),
                    "change_pct": pre.get("change_percent", 0),
                    "prev_close": ticker.get("prevClose", 0),
                    "last_updated": datetime.now().isoformat(),
                }
            return results
        except Exception as e:
            print(f"[Polygon] Error: {e}")
            return {}
    
    def get_daily_bars(self, symbol: str, days: int = 30):
        """Get historical daily bars for backtesting"""
        end = datetime.now()
        start = end - timedelta(days=days)
        url = f"{self.base_url}/v2/aggs/ticker/{symbol}/range/1/day/{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}"
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except Exception as e:
            print(f"[Polygon] Error getting bars for {symbol}: {e}")
            return []
