"""
Universe loader for DAYS-BOT - עם פילטר מקדים משופר
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


def load_universe(max_cache_age_days: int = 7) -> list:
    """
    טוען את רשימת המניות ומסנן סמלים וסוגי ניירות ערך לא רצויים.
    כולל רענון Cache תקופתי.
    """
    cache_file = os.path.join(BASE_DIR, "data", "universe_filtered.csv")
    
    # בדיקת תוקף Cache (לפי ימים)
    if os.path.exists(cache_file):
        file_age_days = (time.time() - os.path.getmtime(cache_file)) / 86400
        if file_age_days < max_cache_age_days:
            try:
                df = pd.read_csv(cache_file)
                print(f"[Universe] Loaded {len(df)} filtered stocks from cache ({file_age_days:.1f} days old)")
                return df.to_dict('records')
            except Exception as e:
                print(f"[Universe] Cache read error: {e}, fetching fresh data...")

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
                'symbol': str(a.symbol),
                'name': str(a.name or ''),
                'exchange': str(a.exchange)
            })
        
        print(f"[Universe] Raw stocks fetched: {len(stocks)}")
        
        # ====== סינון סמלים ושמות לא רצויים ======
        bad_symbol_patterns = ['.WS', '.U', '.RT', 'USDC', 'USDT', '/']
        bad_name_patterns = ['ETF', 'LEVERAGE', '2X', '3X', 'BEAR', 'BULL', 'INDEX', 'FUND', 'ACQUISITION']
        
        filtered = []
        for s in stocks:
            symbol = s['symbol'].upper()
            name = s['name'].upper()
            
            # בדיקת תבניות פסולות בסמול
            if any(p in symbol for p in bad_symbol_patterns):
                continue
            
            # בדיקת תבניות פסולות בשם החברה
            if any(p in name for p in bad_name_patterns):
                continue
                
            filtered.append(s)

        print(f"[Universe] After symbol and name filtering: {len(filtered)}")
        
        # שמירה ל-Cache
        df = pd.DataFrame(filtered)
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        df.to_csv(cache_file, index=False)
        print(f"[Universe] Saved {len(filtered)} filtered stocks to cache")
        
        return filtered
        
    except Exception as e:
        print(f"[Universe] Error fetching universe: {e}")
        return []
