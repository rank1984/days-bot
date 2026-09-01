"""
DAYS-BOT V3.5 – Universe (400 liquid stocks)
No FTP, no 429, just stable list.
"""
from typing import List

# 400 liquid US stocks (S&P 400 + active names)
STABLE_UNIVERSE = [
    # Mega/Large Cap
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
    "RBLX", "ROKU", "SNAP", "PINS", "SPOT", "DKNG", "CELH", "DASH",
    "WBD", "PARA", "UBER", "LYFT", "GRAB", "DIDI", "BABA", "JD", "PDD",
    "BIDU", "TME", "NTES", "SE", "SHOP", "CPRT", "ADSK", "CDNS", "SNPS",
    "ANSS", "DT", "TYL", "PTC", "PLTR", "SNOW", "CRWD", "ZS", "NET",
    "DDOG", "MDB", "OKTA", "FTNT", "PANW", "JNPR", "FFIV", "AKAM", "VRSN",
    # Financials
    "SCHW", "IBKR", "ET", "HOOD", "SOFI", "UPST", "AFRM", "V", "MA", "AXP",
    "DFS", "SYF", "COF", "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "BX",
    "KKR", "APO", "CG", "ARES", "TPG", "LAZ", "EVR", "PJT", "HLI", "BAM",
    # Healthcare
    "ABT", "TMO", "DHR", "SYK", "MDT", "BDX", "BSX", "EW", "ZTS", "IDXX",
    "HCA", "UHS", "THC", "CYH", "AMN", "ENSG", "ACHC", "EHC", "CHE", "OPCH",
    "BIO", "RGEN", "REPL", "SRPT", "SAGE", "AXSM", "IONS", "ALNY", "NBIX",
    "EXEL", "INCY", "REGN", "VRTX", "BIIB", "GILD", "AMGN", "MRNA", "BNTX",
    "NVAX", "NOVAVAX", "PFE", "MRK", "ABBV", "BMY", "JNJ", "LLY", "SNY", "AZN",
    # Technology (more)
    "DELL", "HPQ", "HPE", "IBM", "CSCO", "JNPR", "NTAP", "PSTG", "WDC", "STX",
    "SEAGATE", "WDC", "SMCI", "DELL", "HPE", "IBM", "CSCO", "JNPR", "NTAP", "PSTG",
    "WDC", "STX", "SEAGATE", "WDC", "SMCI", "DELL", "HPE", "IBM", "CSCO", "JNPR",
    # Consumer
    "TGT", "WMT", "COST", "HD", "LOW", "NKE", "MCD", "SBUX", "KO", "PEP",
    "DIS", "ABNB", "BKNG", "UBER", "LYFT", "DASH", "GRAB", "SE", "SHOP",
    "CPRT", "ADSK", "CDNS", "SNPS", "ANSS", "DT", "TYL", "PTC", "PLTR",
    "SNOW", "CRWD", "ZS", "NET", "DDOG", "MDB", "OKTA", "FTNT", "PANW",
    "JNPR", "FFIV", "AKAM", "VRSN",
    # Industrials
    "CAT", "DE", "BA", "GE", "HON", "UPS", "FDX", "EXPD", "CHRW", "LUV",
    "DAL", "UAL", "AAL", "ALK", "JBLU", "SAVE", "SKYW", "MESA", "AIRT",
    "AAL", "DAL", "UAL", "LUV", "ALK", "JBLU", "SAVE", "SKYW", "MESA", "AIRT",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY", "EOG", "MPC", "PSX", "VLO", "HES",
    "APA", "DVN", "FANG", "CTRA", "EQT", "RRC", "AR", "SWN", "CHK", "CLR",
    # ETFs excluded intentionally
]

BLACKLIST = {"SPY", "QQQ", "IWM", "BITF", "MPLN", "SQ"}


def load_universe() -> List[str]:
    universe = []
    seen = set()
    for s in STABLE_UNIVERSE:
        s = s.strip().upper()
        if not s or s in seen or s in BLACKLIST:
            continue
        if any(c in s for c in ["$", ".", "-", "/", "^"]):
            continue
        seen.add(s)
        universe.append(s)
    print(f"[Universe] Loaded {len(universe)} liquid symbols.")
    return universe
