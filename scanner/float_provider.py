"""
Float Provider – fetches float_shares from FMP API with caching
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from utils.config import FMP_API_KEY

CACHE_FILE = os.path.join(BASE_DIR, "data", "float_cache.json")
CACHE_TTL = 86400  # 24 hours

def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def get_float_shares(symbol: str) -> Optional[float]:
    """
    מחזיר float_shares עבור סימבול, או None אם לא זמין
    """
    cache = _load_cache()
    now = datetime.now()
    
    # בדיקת Cache
    if symbol in cache:
        entry = cache[symbol]
        if 'timestamp' in entry and 'value' in entry:
            ts = datetime.fromisoformat(entry['timestamp'])
            if (now - ts).total_seconds() < CACHE_TTL:
                return entry['value']
    
    # אם אין FMP API Key – מחזיר None
    if not FMP_API_KEY:
        return None
    
    try:
        url = f"https://financialmodelingprep.com/api/v3/stock-shares-outstanding/{symbol}?apikey={FMP_API_KEY}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                float_val = data[0].get('sharesOutstanding', 0)
                if float_val > 0:
                    cache[symbol] = {'value': float_val, 'timestamp': now.isoformat()}
                    _save_cache(cache)
                    return float_val
    except Exception as e:
        print(f"[FloatProvider] Error fetching float for {symbol}: {e}")
    
    # סימון כלא זמין (למנוע קריאות חוזרות)
    cache[symbol] = {'value': None, 'timestamp': now.isoformat()}
    _save_cache(cache)
    return None
