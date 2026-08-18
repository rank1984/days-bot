"""
Float Provider – fetches float from yfinance (primary) + FMP (fallback)
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


def get_float_from_yfinance(symbol: str) -> Optional[float]:
    """Primary source – free, no API key required"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        # Try multiple fields that Yahoo provides
        for field in ['floatShares', 'sharesOutstanding', 'impliedSharesOutstanding']:
            val = info.get(field)
            if val and val > 0:
                return float(val)
        return None
    except Exception as e:
        print(f"[FloatProvider] yfinance error for {symbol}: {e}")
        return None


def get_float_from_fmp(symbol: str) -> Optional[float]:
    """Fallback – requires FMP_API_KEY"""
    if not FMP_API_KEY:
        return None
    try:
        url = f"https://financialmodelingprep.com/api/v4/shares_float?symbol={symbol}&apikey={FMP_API_KEY}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                # FMP returns: [{"symbol": "...", "float": ..., "outstanding": ...}]
                float_val = data[0].get('float')
                if float_val and float_val > 0:
                    return float(float_val)
        return None
    except Exception as e:
        print(f"[FloatProvider] FMP error for {symbol}: {e}")
        return None


def get_float_shares(symbol: str) -> Optional[float]:
    """
    Returns float if found, else None.
    Primary: yfinance (free, no key)
    Fallback: FMP (if API key exists)
    """
    cache = _load_cache()
    now = datetime.now()

    # Check cache first
    if symbol in cache:
        entry = cache[symbol]
        if 'timestamp' in entry and 'value' in entry:
            ts = datetime.fromisoformat(entry['timestamp'])
            if (now - ts).total_seconds() < CACHE_TTL:
                return entry['value']  # may be None

    # Try yfinance first (primary, free)
    val = get_float_from_yfinance(symbol)
    if val is not None and val > 0:
        cache[symbol] = {'value': val, 'timestamp': now.isoformat()}
        _save_cache(cache)
        return val

    # Fallback to FMP if available
    val = get_float_from_fmp(symbol)
    if val is not None and val > 0:
        cache[symbol] = {'value': val, 'timestamp': now.isoformat()}
        _save_cache(cache)
        return val

    # Mark as unknown (but keep trying tomorrow)
    cache[symbol] = {'value': None, 'timestamp': now.isoformat()}
    _save_cache(cache)
    return None
