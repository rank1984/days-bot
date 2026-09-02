"""
DAYS-BOT V4.1 – Dynamic Universe Builder

Purpose:
- Build a clean, usable US equity universe.
- DO NOT use yfinance here.
- Nasdaq Trader = symbol directory.
- Finnhub news = dynamic additions.
- Cached universe = emergency fallback.

Important:
This module does NOT determine movers.
It only builds the universe that Discovery will scan.
"""

import re
import requests
import pandas as pd

from datetime import datetime
from pathlib import Path
from typing import List, Set

from utils.config import FINNHUB_API_KEY


BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = BASE_DIR / "data" / "universe_cache.csv"

NASDAQ_URL = (
    "https://www.nasdaqtrader.com/"
    "dynamic/SymDir/nasdaqtraded.txt"
)

EXCLUDED_ETFS = {
    "SPY", "QQQ", "IWM", "VTI", "VOO", "DIA", "ARKK",
    "TQQQ", "SQQQ", "UVXY", "SOXL", "SOXS"
}

COMMON_FALSE_POSITIVES = {
    "THE", "FOR", "AND", "WITH", "THIS", "THAT", "FROM",
    "WILL", "HAVE", "MORE", "NEW", "YORK", "MARKET",
    "STOCK", "NASDAQ", "NYSE", "CEO", "CFO", "IPO",
    "AI", "USA", "SEC", "FDA", "US", "UK"
}


# ============================================================
# CLEAN SYMBOL
# ============================================================

def _clean_symbol(symbol: str) -> str | None:
    if not symbol:
        return None

    s = str(symbol).strip().upper()

    if not s:
        return None

    if len(s) < 1 or len(s) > 5:
        return None

    if any(c in s for c in ["$", ".", "-", "/", "^", " "]):
        return None

    if not re.fullmatch(r"[A-Z]{1,5}", s):
        return None

    if s in EXCLUDED_ETFS:
        return None

    return s


# ============================================================
# NASDAQ SYMBOL DIRECTORY
# ============================================================

def get_nasdaq_universe() -> List[str]:
    """
    Download Nasdaq Trader symbol directory.

    We intentionally do NOT use FTP and do not use yfinance.
    """

    try:
        response = requests.get(
            NASDAQ_URL,
            timeout=15,
            headers={
                "User-Agent": "DAYS-BOT/4.1"
            }
        )

        response.raise_for_status()

        text = response.text

        # Nasdaq file is pipe-separated.
        from io import StringIO

        df = pd.read_csv(
            StringIO(text),
            sep="|",
            dtype=str
        )

        # Remove possible footer row.
        if "Symbol" not in df.columns:
            raise ValueError("Nasdaq file missing Symbol column")

        df = df[df["Symbol"].notna()]

        if "Test Issue" in df.columns:
            df = df[df["Test Issue"].fillna("N") == "N"]

        if "ETF" in df.columns:
            df = df[df["ETF"].fillna("N") == "N"]

        symbols = []

        for raw in df["Symbol"]:
            symbol = _clean_symbol(raw)

            if symbol:
                symbols.append(symbol)

        symbols = sorted(set(symbols))

        print(f"[Universe] Nasdaq clean symbols: {len(symbols)}")

        return symbols

    except Exception as e:
        print(f"[Universe] Nasdaq error: {e}")
        return []


# ============================================================
# FINNHUB NEWS SYMBOLS
# ============================================================

def get_news_symbols() -> List[str]:
    """
    Extract symbols from Finnhub news.

    News symbols are additions, not the entire universe.
    """

    if not FINNHUB_API_KEY:
        print("[Universe] Finnhub key missing – news layer skipped")
        return []

    try:
        url = (
            "https://finnhub.io/api/v1/news"
            f"?category=general&token={FINNHUB_API_KEY}"
        )

        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "DAYS-BOT/4.1"}
        )

        if response.status_code != 200:
            print(
                f"[Universe] Finnhub HTTP {response.status_code}"
            )
            return []

        data = response.json()

        symbols: Set[str] = set()

        for item in data[:50]:
            headline = item.get("headline", "") or ""
            summary = item.get("summary", "") or ""

            # Prefer Finnhub-provided related symbols if present.
            related = item.get("related", "")

            if related:
                for s in str(related).split(","):
                    cleaned = _clean_symbol(s)
                    if cleaned:
                        symbols.add(cleaned)

            # Secondary extraction from headline/summary.
            text = f"{headline} {summary}"

            found = re.findall(
                r"\b[A-Z]{1,5}\b",
                text
            )

            for s in found:
                if s in COMMON_FALSE_POSITIVES:
                    continue

                cleaned = _clean_symbol(s)

                if cleaned:
                    symbols.add(cleaned)

        result = sorted(symbols)

        print(f"[Universe] News symbols: {len(result)}")

        return result

    except Exception as e:
        print(f"[Universe] News error: {e}")
        return []


# ============================================================
# CACHE
# ============================================================

def load_cached_universe() -> List[str]:
    try:
        if not CACHE_PATH.exists():
            return []

        df = pd.read_csv(CACHE_PATH)

        if "symbol" not in df.columns:
            return []

        symbols = []

        for raw in df["symbol"].dropna():
            symbol = _clean_symbol(raw)

            if symbol:
                symbols.append(symbol)

        symbols = list(dict.fromkeys(symbols))

        print(
            f"[Universe] Loaded {len(symbols)} symbols from cache"
        )

        return symbols

    except Exception as e:
        print(f"[Universe] Cache load error: {e}")
        return []


def save_universe(symbols: List[str]) -> None:
    try:
        CACHE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        pd.DataFrame({
            "symbol": symbols
        }).to_csv(
            CACHE_PATH,
            index=False
        )

    except Exception as e:
        print(f"[Universe] Cache save error: {e}")


# ============================================================
# STATIC FALLBACK
# ============================================================

def get_static_fallback() -> List[str]:
    """
    Emergency symbols only.

    This is NOT the main scanner universe.
    """

    return [
        "AAPL", "MSFT", "NVDA", "AMZN", "META",
        "GOOGL", "TSLA", "AMD", "NFLX", "ORCL",
        "QCOM", "INTC", "MU", "AMAT",
        "SMCI", "MRVL", "ON", "PLTR",
        "SNOW", "CRWD", "NET", "DDOG",
        "MDB", "SHOP", "RIVN",
        "COIN", "HOOD", "MSTR",
        "SOFI", "RBLX", "ROKU", "SNAP",
        "DKNG", "CELH", "BABA", "JD",
        "PDD", "BIDU", "SE", "GRAB"
    ]


# ============================================================
# MAIN BUILDER
# ============================================================

def build_universe(
    max_symbols: int = 300
) -> List[str]:

    print("[Universe] Building V4.1 universe...")

    all_symbols: Set[str] = set()

    # --------------------------------------------------------
    # 1. Nasdaq directory
    # --------------------------------------------------------

    base = get_nasdaq_universe()

    # Keep a reasonably large clean pool.
    # Discovery will rank it using market data.
    for symbol in base[:1500]:
        all_symbols.add(symbol)

    # --------------------------------------------------------
    # 2. News additions
    # --------------------------------------------------------

    news = get_news_symbols()

    for symbol in news[:150]:
        all_symbols.add(symbol)

    # --------------------------------------------------------
    # 3. Clean
    # --------------------------------------------------------

    cleaned = []

    for symbol in all_symbols:
        symbol = _clean_symbol(symbol)

        if symbol and symbol not in cleaned:
            cleaned.append(symbol)

    # Deterministic ordering.
    cleaned = sorted(cleaned)

    # --------------------------------------------------------
    # 4. Cache
    # --------------------------------------------------------

    if len(cleaned) >= 100:
        result = cleaned[:max_symbols]

        save_universe(result)

        print(
            f"[Universe] Final V4.1 universe: "
            f"{len(result)} symbols"
        )

        return result

    # --------------------------------------------------------
    # 5. Cache fallback
    # --------------------------------------------------------

    cached = load_cached_universe()

    if cached:
        return cached[:max_symbols]

    # --------------------------------------------------------
    # 6. Static fallback
    # --------------------------------------------------------

    fallback = get_static_fallback()

    print(
        f"[Universe] Using static fallback: "
        f"{len(fallback)} symbols"
    )

    return fallback[:max_symbols]


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def load_universe(
    max_symbols: int = 300
) -> List[str]:

    try:
        return build_universe(max_symbols)

    except Exception as e:
        print(f"[Universe] Build failed: {e}")

        cached = load_cached_universe()

        if cached:
            return cached[:max_symbols]

        fallback = get_static_fallback()

        return fallback[:max_symbols]