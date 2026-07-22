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
    טוען את רשימת המניות ומסנן סמלים לא רצויים
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
            if a.exchange in ['OTC', 'PNK', 'OTCBB']:
                continue
            stocks.append({
                'symbol': a.symbol,
                'name': a.name,
                'exchange': a.exchange
            })
        
        print(f"[Universe] Raw stocks: {len(stocks)}")
        
        # ====== סינון סמלים לא רצויים ======
        bad_patterns = ['.WS', '.U', '.RT', 'USDC', 'USDT', '/', 'ETF', 'LEVERAGE', '2X', '3X']
        filtered = []
        for s in stocks:
            symbol = s['symbol']
            if any(p in symbol for p in bad_patterns):
                continue
            filtered.append(s)

        print(f"[Universe] After symbol filter: {len(filtered)}")
        
        # שמירה ל-Cache
        df = pd.DataFrame(filtered)
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        df.to_csv(cache_file, index=False)
        print(f"[Universe] Saved {len(filtered)} filtered stocks to cache")
        
        return filtered
        
    except Exception as e:
        print(f"[Universe] Error: {e}")
        return []
