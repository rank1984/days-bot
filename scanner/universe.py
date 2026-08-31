"""
DAYS-BOT V3.4 – Stable Liquid Universe (No FTP, No 429)
"""
from typing import List

# ~110 liquid stocks, manually curated to avoid delisted/rate-limited symbols
STABLE_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA",
    "AVGO", "AMD", "NFLX", "ORCL", "CRM", "ADBE", "QCOM", "INTC",
    "MU", "AMAT", "LRCX", "TXN", "JPM", "BAC", "WFC", "GS", "MS",
    "C", "V", "MA", "PYPL", "COF", "WMT", "COST", "TGT", "HD", "LOW",
    "NKE", "MCD", "SBUX", "KO", "PEP", "DIS", "ABNB", "BKNG", "UBER",
    "LYFT", "DASH", "XOM", "CVX", "COP", "SLB", "OXY", "LLY", "JNJ",
    "PFE", "MRK", "ABBV", "BMY", "UNH", "CVS", "ISRG", "CAT", "DE",
    "BA", "GE", "HON", "UPS", "FDX", "ARM", "SMCI", "MRVL", "ON",
    "MCHP", "ADI", "KLAC", "PLTR", "SNOW", "CRWD", "PANW", "NET",
    "DDOG", "MDB", "SHOP", "RIVN", "LCID", "F", "GM", "MRNA", "BNTX",
    "CRSP", "GILD", "REGN", "VRTX", "COIN", "HOOD", "MSTR", "SOFI",
    "RBLX", "ROKU", "SNAP", "PINS", "SPOT", "DKNG", "CELH"
]

BLACKLIST = {"SPY", "QQQ", "IWM", "BITF", "MPLN"}


def load_universe() -> List[str]:
    universe = []
    seen = set()
    for s in STABLE_UNIVERSE:
        s = s.strip().upper()
        if s in seen or s in BLACKLIST or any(c in s for c in ["$", ".", "-", "/", "^"]):
            continue
        seen.add(s)
        universe.append(s)
    print(f"[Universe] Loaded {len(universe)} liquid symbols.")
    return universe