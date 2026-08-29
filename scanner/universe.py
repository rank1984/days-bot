"""
DAYS-BOT V3.0 – Universe Loader (Keyless / Free)
================================================
Fetches active tradable US equities directly from Nasdaq's public FTP.
No API keys required.
"""

import pandas as pd
from typing import List


def load_universe() -> List[str]:
    print("[Universe] Fetching keyless universe (Nasdaq public FTP)...")
    
    try:
        # הכתובת הציבורית הרשמית של נאסד"ק לסימולים הנסחרים בארה"ב
        url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqtraded.txt"
        
        df = pd.read_csv(url, sep='|')
        
        # סינון תעודות סל ומניות טסט
        df = df[df['Test Issue'] == 'N']
        df = df[df['ETF'] == 'N']
        
        raw_symbols = df['Symbol'].dropna().tolist()
        
        filtered_universe = []
        for symbol in raw_symbols:
            # סינון סימולים המכילים תווים מיוחדים (Warrants, Preferred וכו')
            if isinstance(symbol, str) and not any(c in symbol for c in ['$', '.', '-']):
                filtered_universe.append(symbol)
                
        print(f"[Universe] Filtered universe count: {len(filtered_universe):,}")
        return filtered_universe

    except Exception as e:
        print(f"[Universe] ❌ Error fetching universe: {e}")
        return []
