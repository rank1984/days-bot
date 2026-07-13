"""
Universe loader for DAYS-BOT - עם פילטר מקדים
"""
import sys
import os
from pathlib import Path
import pandas as pd
import time

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

from utils.config import *
import alpaca_trade_api as tradeapi


def load_universe() -> list:
    """
    טוען את רשימת המניות, ומסנן מראש לפי מחיר ונפח
    אם יש נתונים מ-Alpaca
    """
    cache_file = os.path.join(BASE_DIR, "data", "universe_filtered.csv")
    
    # אם קיים Cache עם פילטרים – טען אותו
    if os.path.exists(cache_file):
        try:
            df = pd.read_csv(cache_file)
            print(f"[Universe] Loaded {len(df)} filtered stocks from cache")
            return df.to_dict('records')
        except:
            pass
    
    print("[Universe] Fetching from Alpaca (filtering)...")
    api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url='https://paper-api.alpaca.markets')
    
    try:
        assets = api.list_assets(status='active')
        stocks = []
        for a in assets:
            if not a.tradable:
                continue
            if a.exchange == 'OTC':
                continue
            # סינון לפי סמל – דילוג על קריפטו וכו'
            if '/' in a.symbol or 'USDC' in a.symbol or 'USDT' in a.symbol:
                continue
            stocks.append({
                'symbol': a.symbol,
                'name': a.name,
                'exchange': a.exchange
            })
        
        print(f"[Universe] Raw stocks: {len(stocks)}")
        
        # ====== סינון מקדים ======
        # אם יש אפשרות לקבל snapshots עבור כל המניות – נעשה זאת
        # אבל בגלל מגבלת API, נשתמש ב-list_assets בלבד
        # בשלב זה נחזיר את כל המניות, ונסנן ב-premarket
        # עם זאת, נוסיף סינון של OTC ו-Crypto
        
        filtered = [s for s in stocks if s['exchange'] not in ['OTC', 'PNK', 'OTCBB']]
        print(f"[Universe] After exchange filter: {len(filtered)}")
        
        # שמירה ל-Cache
        df = pd.DataFrame(filtered)
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        df.to_csv(cache_file, index=False)
        print(f"[Universe] Saved {len(filtered)} filtered stocks to cache")
        
        return filtered
        
    except Exception as e:
        print(f"[Universe] Error: {e}")
        return []
