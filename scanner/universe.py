"""
DAYS-BOT V3.0 – Universe Loader (Keyless / Free)
"""

import pandas as pd
from typing import List

def load_universe() -> List[str]:
    """
    Fetches active tradable US equities directly from Nasdaq's public FTP.
    No API keys required. Filters out ETFs and test symbols.
    """
    print("[Universe] Fetching keyless universe (Nasdaq public FTP)...")
    
    try:
        # הכתובת הציבורית של נאסד"ק לרשימת כל הסימולים הנסחרים
        url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqtraded.txt"
        
        # קריאת הנתונים לתוך DataFrame
        df = pd.read_csv(url, sep='|')
        
        # סינון: רק מניות אמיתיות (ללא תעודות סל וללא מניות טסט)
        df = df[df['Test Issue'] == 'N']
        df = df[df['ETF'] == 'N']
        
        # הוצאת הסימולים לרשימה
        raw_symbols = df['Symbol'].dropna().tolist()
        
        filtered_universe = []
        for symbol in raw_symbols:
            # נסנן החוצה סימולים עם תווים מיוחדים (Warrants, Preferred shares)
            if isinstance(symbol, str) and not any(c in symbol for c in ['$', '.', '-']):
                filtered_universe.append(symbol)
                
        print(f"[Universe] Filtered universe count: {len(filtered_universe):,}")
        return filtered_universe

    except Exception as e:
        print(f"[Universe] ❌ Error fetching universe: {e}")
        return []
