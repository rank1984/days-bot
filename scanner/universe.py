"""
DAYS-BOT V3.2 – Universe Loader (Small, ~120 stocks)
"""
from typing import List

# רשימה מוגדרת של מניות נזילות (S&P 500 Top + כמה Small Caps)
UNIVERSE = [
    "AAPL","MSFT","NVDA","AMD","TSLA","AMZN","GOOGL","META","NFLX","INTC",
    "CSCO","ORCL","IBM","CRM","NOW","ADBE","QCOM","TXN","AVGO","MU",
    "PYPL","SQ","SHOP","UBER","LYFT","ABNB","BKNG","RBLX","ZM","DOCU",
    "PFE","JNJ","MRK","ABBV","UNH","CVS","WBA","AMGN","GILD","BIIB",
    "XOM","CVX","COP","SLB","OXY","EOG","MPC","PSX","VLO","HES",
    "JPM","BAC","WFC","C","GS","MS","V","MA","AXP","COF",
    "DIS","NKE","MCD","SBUX","PEP","KO","WMT","TGT","COST","LOW",
    "GE","BA","CAT","DE","HON","MMM","RTX","LMT","GD","NOC",
    "SPY","QQQ","DIA","IWM","XLF","XLK","XLE","XLV","XLI","XLP",
    "PLTR","SNOW","CRWD","ZS","DDOG","NET","PANW","FTNT","OKTA","MDB",
    "SE","DASH","CPRT","ADSK","CDNS","SNPS","KLAC","LRCX","AMAT",
    "TMO","DHR","ISRG","SYK","MDT","BDX","BSX","ABT","EW","ZTS"
]  # ~110

def load_universe() -> List[str]:
    print(f"[Universe] Using static list of {len(UNIVERSE)} liquid stocks.")
    return UNIVERSE
