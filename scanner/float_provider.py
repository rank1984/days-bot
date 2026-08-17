"""
Float Provider – fetches float_shares from FMP or Polygon with caching
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

from utils.config import FMP_API_KEY, POLYGON_API_KEY

CACHE_FILE = os.path.join(BASE_DIR, "data", "float_cache.json")
CACHE_TTL = 86400  # 24 hours

def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def get_float_from_fmp(symbol: str) -> Optional[float]:
    if not FMP_API_KEY:
        return None
    try:
        url = f"https://financialmodelingprep.com/api/v3/stock-shares-outstanding/{symbol}?apikey={FMP_API_KEY}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                return data[0].get('sharesOutstanding', 0)
    except Exception:
        pass
    return None

def get_float_from_polygon(symbol: str) -> Optional[float]:
    if not POLYGON_API_KEY:
        return None
    try:
        url = f"https://api.polygon.io/v3/reference/tickers/{symbol}?apiKey={POLYGON_API_KEY}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('results'):
                return data['results'].get('float_shares')
    except Exception:
        pass
    return None

def get_float_shares(symbol: str) -> Optional[float]:
    print(f"[FloatProvider] Fetching float for {symbol}...")
    
    cache = _load_cache()
    now = datetime.now()
    
    if symbol in cache:
        entry = cache[symbol]
        if 'timestamp' in entry and 'value' in entry:
            ts = datetime.fromisoformat(entry['timestamp'])
            if (now - ts).total_seconds() < CACHE_TTL:
                val = entry['value']
                if val is not None and val > 0:
                    print(f"[FloatProvider] Found float for {symbol} (cached): {val}")
                    return val
                else:
                    print(f"[FloatProvider] No float found for {symbol} (cached None)")
                    return None

    # Try FMP first
    val = get_float_from_fmp(symbol)
    if val is not None and val > 0:
        cache[symbol] = {'value': val, 'timestamp': now.isoformat()}
        _save_cache(cache)
        print(f"[FloatProvider] Found float for {symbol}: {val}")
        return val
    
    # Try Polygon
    val = get_float_from_polygon(symbol)
    if val is not None and val > 0:
        cache[symbol] = {'value': val, 'timestamp': now.isoformat()}
        _save_cache(cache)
        print(f"[FloatProvider] Found float for {symbol}: {val}")
        return val
    
    # Mark as unknown
    cache[symbol] = {'value': None, 'timestamp': now.isoformat()}
    _save_cache(cache)
    print(f"[FloatProvider] No float found for {symbol}")
    return None
