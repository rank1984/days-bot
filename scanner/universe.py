"""
DAYS-BOT V3.4
Stable Keyless Universe

Goal:
    Keep Yahoo Finance request volume low.

    Do NOT scan thousands of symbols.

    Universe target:
        ~100-150 liquid US equities.

No API key required.
"""

from typing import List


# ============================================================
# STABLE LIQUID UNIVERSE
# ============================================================

STABLE_UNIVERSE = [

    # Mega / Large Cap
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "GOOG",
    "TSLA",
    "AVGO",
    "AMD",
    "NFLX",
    "ORCL",
    "CRM",
    "ADBE",
    "QCOM",
    "INTC",
    "MU",
    "AMAT",
    "LRCX",
    "TXN",

    # Financial
    "JPM",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "C",
    "V",
    "MA",
    "PYPL",
    "COF",

    # Consumer
    "WMT",
    "COST",
    "TGT",
    "HD",
    "LOW",
    "NKE",
    "MCD",
    "SBUX",
    "KO",
    "PEP",
    "DIS",
    "ABNB",
    "BKNG",
    "UBER",
    "LYFT",
    "DASH",

    # Energy
    "XOM",
    "CVX",
    "COP",
    "SLB",
    "OXY",

    # Healthcare
    "LLY",
    "JNJ",
    "PFE",
    "MRK",
    "ABBV",
    "BMY",
    "UNH",
    "CVS",
    "ISRG",

    # Industrial
    "CAT",
    "DE",
    "BA",
    "GE",
    "HON",
    "UPS",
    "FDX",

    # Semiconductors / AI
    "ARM",
    "SMCI",
    "MRVL",
    "ON",
    "MCHP",
    "ADI",
    "KLAC",

    # Software / Internet
    "PLTR",
    "SNOW",
    "CRWD",
    "PANW",
    "NET",
    "DDOG",
    "MDB",
    "SHOP",
    "SQ",

    # EV / Growth
    "RIVN",
    "LCID",
    "F",
    "GM",

    # Biotech / higher beta
    "MRNA",
    "BNTX",
    "CRSP",
    "GILD",
    "REGN",
    "VRTX",

    # Other liquid names
    "COIN",
    "HOOD",
    "MSTR",
    "SOFI",
    "RBLX",
    "ROKU",
    "SNAP",
    "PINS",
    "SPOT",
    "DKNG",
    "CELH",

    # ETFs excluded by design below,
    # but retained here only if another module needs them.
    # The scanner itself will remove ETFs.
    "SPY",
    "QQQ",
    "IWM",
]


# ============================================================
# KNOWN BAD / NON-TRADABLE / PROBLEMATIC SYMBOLS
# ============================================================

BLACKLIST = {

    # Examples from current Yahoo errors
    "BITF",
    "MPLN",

    # ETFs – scanner should not trade these
    "SPY",
    "QQQ",
    "IWM",
}


# ============================================================
# SYMBOL SANITIZER
# ============================================================

def _valid_symbol(symbol: str) -> bool:

    if not isinstance(
        symbol,
        str
    ):
        return False

    symbol = symbol.strip().upper()

    if not symbol:
        return False

    if symbol in BLACKLIST:
        return False

    # Avoid warrants / preferred / units / weird symbols.
    for char in (
        "$",
        ".",
        "-",
        "/",
        "^",
    ):

        if char in symbol:
            return False

    return True


# ============================================================
# LOADER
# ============================================================

def load_universe() -> List[str]:

    universe = []

    seen = set()

    for symbol in STABLE_UNIVERSE:

        symbol = symbol.strip().upper()

        if symbol in seen:
            continue

        if not _valid_symbol(
            symbol
        ):
            continue

        seen.add(symbol)
        universe.append(symbol)

    print(
        f"[Universe] Created stable universe: "
        f"{len(universe)} symbols"
    )

    return universe
