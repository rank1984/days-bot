"""
DAYS-BOT V3.4
Stable Liquid Universe Loader

Goals:
- Small fixed universe to avoid yfinance 429
- No FTP dependency during every scan
- Local cache fallback
- Remove ETFs / test issues / special symbols
- Deterministic ordering
"""

from pathlib import Path
from typing import List
import os
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CACHE_PATH = DATA_DIR / "universe_cache.csv"

# Keep this intentionally small.
MAX_UNIVERSE = 150


# Stable liquid universe.
# This is a fallback/seed list, not a market-wide scanner.
DEFAULT_UNIVERSE = [
    "AAPL", "AMD", "AMZN", "BABA", "BAC", "COIN", "COST",
    "CRM", "CVX", "DIS", "GOOG", "GOOGL", "INTC", "JNJ",
    "JPM", "KO", "LI", "META", "MRK", "MSFT", "MSTR",
    "MU", "NFLX", "NIO", "NVDA", "ORCL", "PDD", "PEP",
    "PLTR", "PYPL", "QCOM", "RIVN", "SHOP", "SMCI",
    "SNAP", "SOFI", "T", "TGT", "TSLA", "TSM", "UBER",
    "UNH", "V", "WMT", "XOM",

    # Additional active names
    "ABNB", "ADBE", "AMAT", "BA", "BB", "BIDU", "BITF",
    "BLK", "C", "CCL", "CMCSA", "DAL", "DKNG", "DOCU",
    "F", "FCX", "GILD", "GM", "HOOD", "IBM", "INTU",
    "IONQ", "LCID", "LUMN", "LYFT", "MARA", "MRVL",
    "NET", "NKE", "NU", "ON", "PATH", "PFE", "RBLX",
    "RGTI", "RIVN", "ROKU", "SBUX", "SEDG", "SQ",
    "TAL", "TME", "UAL", "UPST", "VZ", "WBD", "XPEV",

    # Higher-volatility / small-cap candidates
    "ACHR", "APLD", "ASTS", "BBAI", "BE", "CIFR",
    "CLSK", "ENVX", "EVGO", "GRAB", "HIMS", "IREN",
    "JOBY", "LAES", "MARA", "MPLN", "OPEN", "QBTS",
    "RKLB", "RXRX", "SOUN", "TMC", "UUUU", "WULF",

    # Liquid ETFs are intentionally excluded below.
]


def _clean_symbols(symbols: List[str]) -> List[str]:
    cleaned = []

    for symbol in symbols:
        if not isinstance(symbol, str):
            continue

        symbol = symbol.strip().upper()

        if not symbol:
            continue

        # Exclude instruments that tend to cause problems
        # for this strategy.
        if any(ch in symbol for ch in ["$", ".", "-", "/", "^"]):
            continue

        if symbol in {
            "SPY", "QQQ", "IWM", "VTI", "VOO",
            "DIA", "ARKK", "TQQQ", "SQQQ",
        }:
            continue

        if symbol not in cleaned:
            cleaned.append(symbol)

    return cleaned[:MAX_UNIVERSE]


def _load_cache() -> List[str]:
    if not CACHE_PATH.exists():
        return []

    try:
        df = pd.read_csv(CACHE_PATH)

        if "symbol" not in df.columns:
            return []

        symbols = df["symbol"].dropna().astype(str).tolist()
        symbols = _clean_symbols(symbols)

        if symbols:
            print(
                f"[Universe] Cache loaded: "
                f"{len(symbols)} symbols"
            )

        return symbols

    except Exception as exc:
        print(f"[Universe] Cache read failed: {exc}")
        return []


def _save_cache(symbols: List[str]) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        pd.DataFrame({
            "symbol": symbols
        }).to_csv(CACHE_PATH, index=False)

    except Exception as exc:
        print(f"[Universe] Cache write failed: {exc}")


def load_universe() -> List[str]:
    """
    Load a stable, deliberately small universe.

    Priority:
        1. Existing local cache
        2. Default stable universe

    We deliberately do NOT download the full Nasdaq universe
    during every scan.
    """

    cached = _load_cache()

    if cached:
        print(
            f"[Universe] Using cached liquid universe: "
            f"{len(cached)} symbols"
        )
        return cached

    symbols = _clean_symbols(DEFAULT_UNIVERSE)

    _save_cache(symbols)

    print(
        f"[Universe] Created stable universe: "
        f"{len(symbols)} symbols"
    )

    return symbols
