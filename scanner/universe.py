"""
Universe loader for DAYS-BOT
"""
import sys
import os
from pathlib import Path

# הוסף את ספריית הבסיס ו-utils לנתיב
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import List, Dict, Any

from utils.config import *
import alpaca_trade_api as tradeapi


def load_universe() -> List[Dict[str, Any]]:
    """
    Load and filter universe of stocks
    """
    print("[Universe] Loading universe...")
    
    # Try to load from cache first
    cache_file = os.path.join(BASE_DIR, "data", "universe.csv")
    if os.path.exists(cache_file):
        try:
            df = pd.read_csv(cache_file)
            print(f"[Universe] Loaded {len(df)} stocks from cache")
            return df.to_dict('records')
        except Exception as e:
            print(f"[Universe] Cache error: {e}")
    
    # If no cache, fetch from Alpaca
    print("[Universe] Fetching from Alpaca...")
    api = tradeapi.REST(
        ALPACA_API_KEY, 
        ALPACA_SECRET_KEY, 
        base_url='https://paper-api.alpaca.markets'
    )
    
    try:
        # Get all assets
        assets = api.list_assets(status='active')
        stocks = [
            a for a in assets 
            if a.tradable 
            and a.exchange != 'OTC'
            and '/' not in a.symbol  # דילוג על קריפטו (BTC/USD)
            and 'USDC' not in a.symbol
            and 'USDT' not in a.symbol
        ]
        
        print(f"[Universe] Found {len(stocks)} active stocks")
        
        # Convert to dict
        universe = [{'symbol': s.symbol, 'name': s.name, 'exchange': s.exchange} for s in stocks]
        
        # Save cache
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        df = pd.DataFrame(universe)
        df.to_csv(cache_file, index=False)
        print(f"[Universe] Saved {len(universe)} stocks to cache")
        
        return universe
        
    except Exception as e:
        print(f"[Universe] ❌ Error: {e}")
        return []
