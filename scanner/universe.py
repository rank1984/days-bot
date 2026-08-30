"""
DAYS-BOT V3.1 – Universe Loader with Cache Fallback
====================================================
Fetches from Nasdaq FTP, falls back to local cache if unavailable.
"""

import pandas as pd
from typing import List
from pathlib import Path
import os

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "universe_cache.csv"


def load_universe() -> List[str]:
    print("[Universe] Fetching keyless universe (Nasdaq public FTP)...")

    try:
        url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqtraded.txt"
        df = pd.read_csv(url, sep='|')
        df = df[df['Test Issue'] == 'N']
        df = df[df['ETF'] == 'N']

        raw_symbols = df['Symbol'].dropna().tolist()
        filtered_universe = []
        for symbol in raw_symbols:
            if isinstance(symbol, str) and not any(c in symbol for c in ['$', '.', '-']):
                filtered_universe.append(symbol)

        # Save cache for future fallback
        os.makedirs(CACHE_PATH.parent, exist_ok=True)
        pd.DataFrame({"symbol": filtered_universe}).to_csv(CACHE_PATH, index=False)

        print(f"[Universe] Filtered universe count: {len(filtered_universe):,}")
        return filtered_universe

    except Exception as e:
        print(f"[Universe] ❌ FTP error: {e}")

        # Try to load cache
        if CACHE_PATH.exists():
            try:
                df_cache = pd.read_csv(CACHE_PATH)
                symbols = df_cache['symbol'].dropna().tolist()
                print(f"[Universe] Loaded {len(symbols):,} symbols from cache.")
                return symbols
            except Exception as cache_err:
                print(f"[Universe] Cache read failed: {cache_err}")
        else:
            print("[Universe] No cache file found.")

        # Ultimate fallback: hardcoded list of well-known active stocks (small, just for testing)
        # You can expand this or keep it as a minimal safe set.
        fallback = ["SPY", "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "JPM", "VTI"]
        print(f"[Universe] Using hardcoded fallback ({len(fallback)} symbols).")
        return fallback
