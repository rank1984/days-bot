"""
Universe loader – fetches stocks from Alpaca, filters out preferreds and warrants
"""
import sys
import os
from pathlib import Path
import time
from typing import List, Dict

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "utils"))

import alpaca_trade_api as tradeapi
from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY

CACHE_FILE = os.path.join(BASE_DIR, "data", "universe.csv")
CACHE_TTL = 86400  # 24 hours


def load_universe() -> List[Dict]:
    # Check cache age
    if os.path.exists(CACHE_FILE):
        try:
            mtime = os.path.getmtime(CACHE_FILE)
            if (time.time() - mtime) < CACHE_TTL:
                import pandas as pd
                df = pd.read_csv(CACHE_FILE)
                print(f"[Universe] Loaded {len(df)} filtered stocks from cache")
                return df.to_dict('records')
        except Exception as e:
            print(f"[Universe] Cache read error: {e}")

    print("[Universe] Fetching from Alpaca (filtering)...")
    api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url='https://paper-api.alpaca.markets')

    try:
        assets = api.list_assets(status='active')
        print(f"[Universe] Raw stocks fetched: {len(assets)}")

        # Filtering
        bad_suffixes = ('.PR', '.PRA', '.PRB', '.PRC', '.PRD', '.PRE', '.PRF', '.PRG', '.PRH',
                        '.PRI', '.PRJ', '.PRK', '.PRL', '.PRM', '.PRN', '.PRO', '.PRP', '.PRQ',
                        '.PRR', '.PRS', '.PRT', '.PRU', '.PRV', '.PRW', '.PRX', '.PRY', '.PRZ',
                        '.WS', '.WT', '.U', '.RT')
        stocks = []
        for a in assets:
            if not a.tradable:
                continue
            if a.exchange in ('OTC', 'PNK', 'OTCBB'):
                continue
            symbol = a.symbol
            # Skip if symbol ends with any bad suffix
            if any(symbol.endswith(suf) for suf in bad_suffixes):
                continue
            # Skip symbols with / (crypto)
            if '/' in symbol:
                continue
            stocks.append({
                'symbol': symbol,
                'name': a.name,
                'exchange': a.exchange
            })

        print(f"[Universe] After symbol and name filtering: {len(stocks)}")

        # Save cache
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        import pandas as pd
        df = pd.DataFrame(stocks)
        df.to_csv(CACHE_FILE, index=False)
        print(f"[Universe] Saved {len(stocks)} filtered stocks to cache")

        return stocks

    except Exception as e:
        print(f"[Universe] Error: {e}")
        return []
