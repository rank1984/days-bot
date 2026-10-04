"""
DAYS-BOT V4.2 – Dynamic Universe Builder

V4.2 changes (P0-FIX-3):
- ADD Alpaca active US equities whitelist validation.
- Every symbol must exist in Alpaca's active assets before being
  added to the universe. This eliminates English-word contamination
  from the news regex (e.g. "IPO", "NIKE", "NASA", "SHORT", ...).
- Whitelist is cached in data/alpaca_whitelist.json (24h TTL).
- If Alpaca whitelist cannot be loaded, the builder FAILS SAFE:
  it returns an empty universe rather than a contaminated one.
"""
import json
import os
import re
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import List, Set

import pandas as pd
import requests

from utils.config import (
    FINNHUB_API_KEY,
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_DATA_URL,
)


BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = BASE_DIR / "data" / "universe_cache.csv"
WHITELIST_PATH = BASE_DIR / "data" / "alpaca_whitelist.json"
WHITELIST_TTL_HOURS = 24

NASDAQ_URL = (
    "https://www.nasdaqtrader.com/dynamic/SymDir/"
    "nasdaqtraded.txt"
)

ALPACA_ASSETS_URL = "https://api.alpaca.markets/v2/assets"


EXCLUDED_SYMBOLS = {
    "SPY", "QQQ", "IWM", "VTI", "VOO", "DIA", "ARKK",
    "UVXY", "SQQQ", "TQQQ",
}

COMMON_WORDS = {
    "THE", "FOR", "AND", "WITH", "THIS", "THAT", "FROM", "WILL",
    "HAVE", "MORE", "NEW", "YORK", "MARKET", "STOCK", "NASDAQ",
    "NYSE", "CEO", "CFO", "NEWS", "INC", "CORP", "COMPANY",
    "IPO", "IT", "JOB", "KILL", "LESS", "LEVEL", "LOCAL",
    "MATCH", "NASA", "NEED", "NIKE", "NOT", "OR", "OVER",
    "POWER", "PRIZE", "RATIO", "READY", "SAID", "SALE",
    "SEES", "SET", "SHORT", "SOLD", "STAFF", "TIMES",
    "TOO", "TWO", "US", "WALL", "WATCH", "WHAT", "WHITE",
    "HIGH", "LOW", "UP", "DOWN", "BUY", "SELL", "HOLD",
    "USD", "ETF", "AI", "CO", "GROUP", "HOLDINGS", "TECH",
    "GLOBAL", "HEALTH", "BIO", "TECH", "ENERGY", "FOOD",
}


# ---------------------------------------------------------------------------
# Alpaca whitelist (P0-FIX-3)
# ---------------------------------------------------------------------------

def _load_alpaca_whitelist_from_cache() -> set | None:
    """Load cached whitelist if it exists and is not expired."""
    if not WHITELIST_PATH.exists():
        return None
    try:
        with open(WHITELIST_PATH, "r") as f:
            data = json.load(f)
        generated = datetime.fromisoformat(data.get("generated_at", ""))
        if datetime.now() - generated > timedelta(hours=WHITELIST_TTL_HOURS):
            return None
        symbols = data.get("symbols", [])
        if not isinstance(symbols, list) or not symbols:
            return None
        return set(symbols)
    except Exception:
        return None


def _save_alpaca_whitelist_to_cache(symbols: set) -> None:
    try:
        WHITELIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(WHITELIST_PATH, "w") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "count": len(symbols),
                "symbols": sorted(symbols),
            }, f)
    except Exception as e:
        print(f"[Universe] Whitelist cache write warning: {e}")


def _fetch_alpaca_whitelist() -> set | None:
    """
    Fetch active US equities from Alpaca.
    Returns None on failure (do not fall back to contaminated list).
    """
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("[Universe] No Alpaca credentials — cannot build whitelist")
        return None

    try:
        resp = requests.get(
            ALPACA_ASSETS_URL,
            headers={
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
                "Accept": "application/json",
            },
            params={
                "status": "active",
                "asset_class": "us_equity",
            },
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"[Universe] Alpaca assets HTTP {resp.status_code}")
            return None

        assets = resp.json()
        if not isinstance(assets, list):
            return None

        symbols = set()
        for a in assets:
            if not isinstance(a, dict):
                continue
            sym = a.get("symbol")
            tradable = a.get("tradable", True)
            exchange = a.get("exchange", "")
            if not sym or not tradable:
                continue
            # Exclude OTC and non-US exchanges if listed
            if exchange in ("OTC", "CRYPTO", "ARCA", ""):
                # Keep ARCA for ETFs? For our strategy, exclude for now.
                # Only keep NASDAQ, NYSE, AMEX, BATS
                if exchange == "" or exchange == "OTC" or exchange == "CRYPTO":
                    continue
            symbols.add(str(sym).strip().upper())

        print(f"[Universe] Alpaca whitelist loaded: {len(symbols)} symbols")
        return symbols

    except Exception as e:
        print(f"[Universe] Alpaca whitelist error: {e}")
        return None


def get_alpaca_whitelist(force_refresh: bool = False) -> set | None:
    """Return whitelist (cached if fresh). Returns None on failure."""
    if not force_refresh:
        cached = _load_alpaca_whitelist_from_cache()
        if cached is not None:
            print(f"[Universe] Alpaca whitelist from cache: {len(cached)} symbols")
            return cached

    fresh = _fetch_alpaca_whitelist()
    if fresh:
        _save_alpaca_whitelist_to_cache(fresh)
    return fresh


# ---------------------------------------------------------------------------
# Symbol cleaning (unchanged — format only)
# ---------------------------------------------------------------------------

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


def _is_valid_symbol(symbol: str, whitelist: set) -> bool:
    """Format OK + in Alpaca whitelist + not a common word."""
    cleaned = _clean_symbol(symbol)
    if cleaned is None:
        return False
    if cleaned in COMMON_WORDS:
        return False
    if whitelist is not None and cleaned not in whitelist:
        return False
    return True


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def get_nasdaq_universe() -> List[str]:
    try:
        response = requests.get(
            NASDAQ_URL,
            timeout=20,
            headers={"User-Agent": "DAYS-BOT/4.2"},
        )
        response.raise_for_status()

        df = pd.read_csv(StringIO(response.text), sep="|", dtype=str)

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
                str(item.get("headline", "")) + " "
                + str(item.get("summary", ""))
            ).upper()
            found = re.findall(r"\b[A-Z]{2,5}\b", text)
            for raw in found:
                symbol = _clean_symbol(raw)
                if symbol and symbol not in COMMON_WORDS:
                    symbols.add(symbol)

        result = sorted(symbols)
        print(f"[Universe] News candidates (pre-whitelist): {len(result)}")
        return result

    except Exception as e:
        print(f"[Universe] News error: {e}")
        return []


def _static_fallback() -> List[str]:
    return [
        "AAPL", "AMD", "AMZN", "BAC", "BBAI", "CCL", "CLSK",
        "DKNG", "F", "HOOD", "INTC", "MARA", "META", "MSTR",
        "MU", "NIO", "NVDA", "PLTR", "RIVN", "SOFI", "TSLA",
        "UBER", "WBD", "XPEV",
    ]


# ---------------------------------------------------------------------------
# Builder (with whitelist enforcement)
# ---------------------------------------------------------------------------

def build_universe(max_symbols: int = 500) -> List[str]:
    print("[Universe] Building clean dynamic universe...")

    whitelist = get_alpaca_whitelist()
    if whitelist is None or len(whitelist) == 0:
        print("[Universe] FAIL-SAFE: whitelist unavailable — returning empty universe")
        return []

    symbols: Set[str] = set()

    base = get_nasdaq_universe()
    symbols.update(base[:3000])

    news_symbols = get_news_symbols()
    symbols.update(news_symbols)

    if len(symbols) < 100:
        symbols.update(_static_fallback())

    # P0-FIX-3: filter every candidate through whitelist
    cleaned = []
    rejected_contamination = 0
    for symbol in symbols:
        if _is_valid_symbol(symbol, whitelist):
            if symbol not in cleaned:
                cleaned.append(symbol)
        else:
            rejected_contamination += 1

        if len(cleaned) >= max_symbols:
            break

    cleaned = sorted(cleaned)
    print(
        f"[Universe] Final: {len(cleaned)} symbols | "
        f"rejected (whitelist/format/word): {rejected_contamination}"
    )

    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"symbol": cleaned}).to_csv(CACHE_PATH, index=False)
    except Exception as e:
        print(f"[Universe] Cache write warning: {e}")

    return cleaned


def load_universe() -> List[str]:
    try:
        universe = build_universe()
        if universe:
            return universe
    except Exception as e:
        print(f"[Universe] Build failed: {e}")

    # Cache fallback — but still validate against whitelist
    whitelist = get_alpaca_whitelist()
    if whitelist is None or not whitelist:
        return []

    try:
        if CACHE_PATH.exists():
            df = pd.read_csv(CACHE_PATH)
            if "symbol" in df.columns:
                symbols = []
                for raw in df["symbol"].dropna():
                    if _is_valid_symbol(raw, whitelist):
                        clean = _clean_symbol(raw)
                        if clean and clean not in symbols:
                            symbols.append(clean)
                if symbols:
                    print(f"[Universe] Loaded {len(symbols)} symbols from cache (whitelisted)")
                    return symbols[:500]
    except Exception as e:
        print(f"[Universe] Cache read warning: {e}")

    return []
