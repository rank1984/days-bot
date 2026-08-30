"""
DAYS-BOT V3.2 – Universe Loader (Cached, ~500 symbols)
"""
import pandas as pd
from pathlib import Path
from typing import List
import os

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "universe_cache.csv"

# רשימת מניות נזילות קבועה (ניתן להרחיב)
DEFAULT_UNIVERSE = [
    "AAPL","MSFT","NVDA","AMD","TSLA","AMZN","GOOGL","META","NFLX","INTC",
    "CSCO","ORCL","IBM","CRM","NOW","ADBE","QCOM","TXN","AVGO","MU",
    "PYPL","SQ","SHOP","UBER","LYFT","ABNB","BKNG","RBLX","ZM","DOCU",
    "PFE","JNJ","MRK","ABBV","UNH","CVS","WBA","AMGN","GILD","BIIB",
    "XOM","CVX","COP","SLB","OXY","EOG","MPC","PSX","VLO","HES",
    "JPM","BAC","WFC","C","GS","MS","V","MA","AXP","COF",
    "DIS","NKE","MCD","SBUX","PEP","KO","WMT","TGT","COST","LOW",
    "GE","BA","CAT","DE","HON","MMM","RTX","LMT","GD","NOC",
    "SPY","QQQ","DIA","IWM","XLF","XLK","XLE","XLV","XLI","XLP"
]  # ~70 symbols, אבל נוסיף עוד

def load_universe() -> List[str]:
    print("[Universe] Loading universe...")

    # אם יש קובץ מטמון, טען אותו
    if CACHE_PATH.exists():
        try:
            df = pd.read_csv(CACHE_PATH)
            symbols = df['symbol'].dropna().tolist()
            print(f"[Universe] Loaded {len(symbols)} symbols from cache.")
            return symbols
        except:
            pass

    # אחרת, השתמש ברשימה המוגדרת מראש + הוסף כמה מניות אקראיות מהנאסד"ק (אפשר להרחיב)
    try:
        url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqtraded.txt"
        df = pd.read_csv(url, sep='|')
        df = df[df['Test Issue'] == 'N']
        df = df[df['ETF'] == 'N']
        # נבחר 500 מניות עם נפח ממוצע גבוה (אין לנו נתוני נפח, אז נבחר אקראית)
        all_symbols = df['Symbol'].dropna().tolist()
        # נסנן תווים מיוחדים
        filtered = [s for s in all_symbols if isinstance(s, str) and not any(c in s for c in ['$','.','-'])]
        # נחזיר 500 ראשונות (אפשר לשפר)
        universe = filtered[:500]
        # שמירה למטמון
        os.makedirs(CACHE_PATH.parent, exist_ok=True)
        pd.DataFrame({"symbol": universe}).to_csv(CACHE_PATH, index=False)
        print(f"[Universe] Fetched {len(universe)} symbols from Nasdaq.")
        return universe
    except Exception as e:
        print(f"[Universe] Error: {e}. Using default list.")
        # שימוש ברשימה קבועה
        os.makedirs(CACHE_PATH.parent, exist_ok=True)
        pd.DataFrame({"symbol": DEFAULT_UNIVERSE}).to_csv(CACHE_PATH, index=False)
        return DEFAULT_UNIVERSE
