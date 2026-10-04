"""
DAYS-BOT V4.3 – Dynamic Universe Builder

V4.3 changes (P0-FIX-3):
- Alpaca whitelist is OPTIONAL ENHANCEMENT, not required.
- If Alpaca trading API returns 401 (common with data-only keys),
  we fall back to Nasdaq-only universe with aggressive word filtering.
- News symbols are ONLY added when Alpaca whitelist is available,
  because they need whitelist validation to be safe.
- Never returns empty universe if Nasdaq is reachable.
- Tries both live and paper Alpaca API endpoints.
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
)


BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = BASE_DIR / "data" / "universe_cache.csv"
WHITELIST_PATH = BASE_DIR / "data" / "alpaca_whitelist.json"
WHITELIST_TTL_HOURS = 24

NASDAQ_URL = (
    "https://www.nasdaqtrader.com/dynamic/SymDir/"
    "nasdaqtraded.txt"
)

ALPACA_LIVE_ASSETS_URL = "https://api.alpaca.markets/v2/assets"
ALPACA_PAPER_ASSETS_URL = "https://paper-api.alpaca.markets/v2/assets"


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
    "GLOBAL", "HEALTH", "BIO", "ENERGY", "FOOD", "MAJOR",
    "MINOR", "BEST", "GOOD", "BAD", "NEW", "OLD", "YES",
    "NO", "ANY", "ALL", "ONE", "DAY", "WEEK", "MONTH", "YEAR",
    "NOW", "THEN", "HERE", "THERE", "WHEN", "WHERE", "WHY",
    "HOW", "MAY", "CAN", "MUST", "SHALL", "COULD", "WOULD",
    "TOP", "BIG", "SMALL", "MID", "CAP", "RATE", "COST",
    "GAIN", "LOSS", "RISK", "CASH", "BOND", "FUND", "TRUST",
}


# ---------------------------------------------------------------------------
# Symbol format validation
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


def _is_common_word(symbol: str) -> bool:
    return symbol in COMMON_WORDS


# ---------------------------------------------------------------------------
# Alpaca whitelist (OPTIONAL)
# ---------------------------------------------------------------------------

def _load_alpaca_whitelist_from_cache() -> set | None:
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


def _try_alpaca_endpoint(url: str) -> set | None:
    try:
        resp = requests.get(
            url,
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
            print(f"[Universe] {url} → HTTP {resp.status_code}")
            return None

        assets = resp.json()
        if not isinstance(assets, list):
            return None

        symbols = set()
        for a in assets:
            if not isinstance(a, dict):
                continue
            sym = a.get("symbol")
            if not sym or not a.get("tradable", True):
                continue
            ex = a.get("exchange", "")
            if ex in ("OTC", "CRYPTO", ""):
                continue
            symbols.add(str(sym).strip().upper())

        return symbols if symbols else None

    except Exception as e:
        print(f"[Universe] {url} error: {e}")
        return None


def _fetch_alpaca_whitelist() -> set | None:
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("[Universe] No Alpaca credentials — whitelist skipped")
        return None

    # Try live first, then paper
    for url in (ALPACA_LIVE_ASSETS_URL, ALPACA_PAPER_ASSETS_URL):
        result = _try_alpaca_endpoint(url)
        if result:
            print(f"[Universe] Alpaca whitelist loaded from {url}: {len(result)} symbols")
            return result

    print("[Universe] Alpaca whitelist unavailable (both live and paper failed)")
    return None


def get_alpaca_whitelist(force_refresh: bool = False) -> set | None:
    """Return whitelist or None. Never raises. Never blocks discovery."""
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
# Sources
# ---------------------------------------------------------------------------

def get_nasdaq_universe() -> List[str]:
    try:
        response = requests.get(
            NASDAQ_URL,
            timeout=20,
            headers={"User-Agent": "DAYS-BOT/4.3"},
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
                if symbol and not _is_common_word(symbol):
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
# Builder (whitelist is OPTIONAL)
# ---------------------------------------------------------------------------

def build_universe(max_symbols: int = 500) -> List[str]:
    print("[Universe] Building clean dynamic universe...")

    alpaca_whitelist = get_alpaca_whitelist()
    use_alpaca = alpaca_whitelist is not None and len(alpaca_whitelist) > 0

    if use_alpaca:
        print(f"[Universe] Mode: Nasdaq + News + Alpaca whitelist ({len(alpaca_whitelist)} symbols)")
    else:
        print("[Universe] Mode: Nasdaq-only (Alpaca whitelist unavailable)")
        print("[Universe] News symbols will NOT be added (require whitelist for safety)")

    # 1. Nasdaq base (always required)
    base = get_nasdaq_universe()
    if not base:
        print("[Universe] Nasdaq unavailable — using static fallback")
        return _static_fallback()

    symbols: Set[str] = set()
    symbols.update(base[:3000])

    # 2. News symbols ONLY if whitelist is available
    if use_alpaca:
        news_symbols = get_news_symbols()
        symbols.update(news_symbols)
    else:
        print("[Universe] Skipping news symbols (no whitelist to validate them)")

    # 3. Filter
    cleaned: List[str] = []
    rejected_format = 0
    rejected_word = 0
    rejected_whitelist = 0

    for symbol in symbols:
        clean = _clean_symbol(symbol)
        if clean is None:
            rejected_format += 1
            continue

        if _is_common_word(clean):
            rejected_word += 1
            continue

        if use_alpaca and clean not in alpaca_whitelist:
            rejected_whitelist += 1
            continue

        if clean not in cleaned:
            cleaned.append(clean)

        if len(cleaned) >= max_symbols:
            break

    cleaned = sorted(cleaned)
    print(
        f"[Universe] Final: {len(cleaned)} symbols | "
        f"rejected: format={rejected_format}, common_word={rejected_word}, "
        f"not_in_whitelist={rejected_whitelist}"
    )

    if not cleaned:
        print("[Universe] WARNING: empty after filtering — using static fallback")
        return _static_fallback()

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

    # Cache fallback
    try:
        if CACHE_PATH.exists():
            df = pd.read_csv(CACHE_PATH)
            if "symbol" in df.columns:
                symbols = []
                for raw in df["symbol"].dropna():
                    clean = _clean_symbol(raw)
                    if clean and not _is_common_word(clean) and clean not in symbols:
                        symbols.append(clean)
                if symbols:
                    print(f"[Universe] Loaded {len(symbols)} symbols from cache")
                    return symbols[:500]
    except Exception as e:
        print(f"[Universe] Cache read warning: {e}")

    print("[Universe] Emergency fallback")
    return _static_fallback()
