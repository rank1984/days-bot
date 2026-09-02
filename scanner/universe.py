"""
DAYS-BOT V4.1 – Dynamic Universe Builder

Purpose:
- Build a clean stock universe.
- Do NOT use yfinance for discovery.
- Nasdaq symbol directory is used only as a symbol source.
- Finnhub news symbols are optional enrichment.
- Alpaca is responsible for actual market-data discovery.

The universe is intentionally limited because the expensive analyzers
run only on the best candidates.
"""

import re
from pathlib import Path
from typing import List, Set

import pandas as pd
import requests

from utils.config import FINNHUB_API_KEY


BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = BASE_DIR / "data" / "universe_cache.csv"

NASDAQ_URL = (
    "https://www.nasdaqtrader.com/dynamic/SymDir/"
    "nasdaqtraded.txt"
)

EXCLUDED_SYMBOLS = {
    "SPY",
    "QQQ",
    "IWM",
    "VTI",
    "VOO",
    "DIA",
    "ARKK",
    "UVXY",
    "SQQQ",
    "TQQQ",
}

COMMON_WORDS = {
    "THE",
    "FOR",
    "AND",
    "WITH",
    "THIS",
    "THAT",
    "FROM",
    "WILL",
    "HAVE",
    "MORE",
    "NEW",
    "YORK",
    "MARKET",
    "STOCK",
    "NASDAQ",
    "NYSE",
    "CEO",
    "CFO",
    "NEWS",
    "INC",
    "CORP",
    "COMPANY",
}


def _clean_symbol(symbol: str) -> str | None:
    if not symbol:
        return None

    s = str(symbol).strip().upper()

    if not s:
        return None

    if len(s) < 1 or len(s) > 5:
        return None

    if s in EXCLUDED_SYMBOLS:
        return None

    if any(c in s for c in [".", "$", "-", "/", "^", " "]):
        return None

    if not re.fullmatch(r"[A-Z]+", s):
        return None

    return s


def get_nasdaq_universe() -> List[str]:
    """
    Get clean US-listed symbols from Nasdaq Trader.

    This is a SYMBOL DIRECTORY only.
    It is NOT market-data discovery.
    """

    try:
        response = requests.get(
            NASDAQ_URL,
            timeout=20,
            headers={"User-Agent": "DAYS-BOT/4.1"},
        )

        response.raise_for_status()

        from io import StringIO

        df = pd.read_csv(
            StringIO(response.text),
            sep="|",
            dtype=str,
        )

        if "Test Issue" in df.columns:
            df = df[df["Test Issue"] == "N"]

        if "ETF" in df.columns:
            df = df[df["ETF"] == "N"]

        if "NextShares" in df.columns:
            df = df[df["NextShares"] == "N"]

        symbols = []

        for raw in df.get("Symbol", []):
            symbol = _clean_symbol(raw)

            if symbol:
                symbols.append(symbol)

        symbols = list(dict.fromkeys(symbols))

        print(f"[Universe] Nasdaq base: {len(symbols)} symbols")

        return symbols

    except Exception as e:
        print(f"[Universe] Nasdaq error: {e}")
        return []


def get_news_symbols() -> List[str]:
    """
    Optional Finnhub news enrichment.

    Failure here must never break discovery.
    """

    if not FINNHUB_API_KEY:
        return []

    try:
        url = (
            "https://finnhub.io/api/v1/news"
            f"?category=general&token={FINNHUB_API_KEY}"
        )

        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()

        symbols: Set[str] = set()

        for item in data[:50]:
            text = (
                str(item.get("headline", ""))
                + " "
                + str(item.get("summary", ""))
            ).upper()

            found = re.findall(r"\b[A-Z]{2,5}\b", text)

            for raw in found:
                symbol = _clean_symbol(raw)

                if symbol and symbol not in COMMON_WORDS:
                    symbols.add(symbol)

        result = sorted(symbols)

        print(f"[Universe] News symbols: {len(result)}")

        return result

    except Exception as e:
        print(f"[Universe] News error: {e}")
        return []


def _static_fallback() -> List[str]:
    """
    Emergency fallback.

    These symbols are NOT trade recommendations.
    They only prevent a completely empty universe.
    """

    return [
        "AAPL",
        "AMD",
        "AMZN",
        "BAC",
        "BBAI",
        "CCL",
        "CLSK",
        "DKNG",
        "F",
        "HOOD",
        "INTC",
        "MARA",
        "META",
        "MSTR",
        "MU",
        "NIO",
        "NVDA",
        "PLTR",
        "RIVN",
        "SOFI",
        "TSLA",
        "UBER",
        "WBD",
        "XPEV",
    ]


def build_universe(max_symbols: int = 500) -> List[str]:
    print("[Universe] Building clean dynamic universe...")

    symbols: Set[str] = set()

    base = get_nasdaq_universe()

    # Take a broad but bounded sample.
    symbols.update(base[:3000])

    news_symbols = get_news_symbols()
    symbols.update(news_symbols)

    if len(symbols) < 100:
        symbols.update(_static_fallback())

    cleaned = []

    for symbol in symbols:
        clean = _clean_symbol(symbol)

        if clean and clean not in cleaned:
            cleaned.append(clean)

        if len(cleaned) >= max_symbols:
            break

    cleaned = sorted(cleaned)

    print(
        f"[Universe] Final dynamic universe: "
        f"{len(cleaned)} symbols"
    )

    try:
        CACHE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        pd.DataFrame(
            {"symbol": cleaned}
        ).to_csv(
            CACHE_PATH,
            index=False,
        )

    except Exception as e:
        print(f"[Universe] Cache write warning: {e}")

    return cleaned


def load_universe() -> List[str]:
    """
    Build fresh universe.
    If external source fails, use cache.
    If cache fails, use static fallback.
    """

    try:
        universe = build_universe()

        if universe:
            return universe

    except Exception as e:
        print(f"[Universe] Build failed: {e}")

    try:
        if CACHE_PATH.exists():
            df = pd.read_csv(CACHE_PATH)

            if "symbol" in df.columns:
                symbols = []

                for raw in df["symbol"].dropna():
                    symbol = _clean_symbol(raw)

                    if symbol:
                        symbols.append(symbol)

                symbols = list(dict.fromkeys(symbols))

                if symbols:
                    print(
                        f"[Universe] Loaded "
                        f"{len(symbols)} symbols from cache"
                    )
                    return symbols[:500]

    except Exception as e:
        print(f"[Universe] Cache read warning: {e}")

    fallback = _static_fallback()

    print(
        f"[Universe] Emergency fallback: "
        f"{len(fallback)} symbols"
    )

    return fallback
