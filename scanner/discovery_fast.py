"""
DAYS-BOT V4.1 – Fast Discovery Engine

Primary market-data source:
    Alpaca Market Data API / IEX

Purpose:
- Scan a clean universe quickly.
- Find daily movers.
- Find price + previous close.
- Calculate gap.
- Calculate basic liquidity.
- NEVER fail the entire scan because one symbol fails.

This module is recommendation-only.
It does NOT execute orders.
"""

import requests
import time

from datetime import datetime, timedelta
from typing import List, Dict, Any

import pytz

from scanner.universe import load_universe
from utils.config import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_DATA_URL,
    DISCOVERY_MIN_PRICE,
    DISCOVERY_MAX_PRICE,
    DISCOVERY_MIN_GAP,
    DISCOVERY_MAX_GAP,
    DISCOVERY_MIN_VOLUME,
)


ET = pytz.timezone("America/New_York")


# ============================================================
# ALPACA SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "User-Agent": "DAYS-BOT/4.1",
})


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value, default=None):
    try:
        if value is None:
            return default

        return float(value)

    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default

        return int(float(value))

    except Exception:
        return default


def _chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _alpaca_available() -> bool:
    return bool(
        ALPACA_API_KEY and
        ALPACA_SECRET_KEY
    )


# ============================================================
# SNAPSHOT REQUEST
# ============================================================

def _get_snapshots(
    symbols: List[str]
) -> Dict[str, Any]:

    if not _alpaca_available():
        print("[FastDiscovery] Alpaca credentials missing")
        return {}

    if not symbols:
        return {}

    url = f"{ALPACA_DATA_URL}/v2/stocks/snapshots"

    params = {
        "symbols": ",".join(symbols),
        "feed": "iex",
    }

    try:
        response = SESSION.get(
            url,
            params=params,
            timeout=15
        )

        if response.status_code != 200:
            print(
                "[FastDiscovery] Alpaca snapshot HTTP "
                f"{response.status_code}: "
                f"{response.text[:200]}"
            )
            return {}

        data = response.json()

        return data if isinstance(data, dict) else {}

    except Exception as e:
        print(
            f"[FastDiscovery] Snapshot error: {e}"
        )
        return {}


# ============================================================
# DISCOVERY
# ============================================================

def fast_discovery(
    universe: List[str] | None = None
) -> List[dict]:

    if universe is None:
        universe = load_universe(
            max_symbols=300
        )

    if not universe:
        print("[FastDiscovery] Empty universe")
        return []

    print(
        "[FastDiscovery] "
        f"Scanning {len(universe)} symbols via Alpaca IEX..."
    )

    if not _alpaca_available():
        print(
            "[FastDiscovery] ERROR: "
            "ALPACA_API_KEY / ALPACA_SECRET_KEY missing"
        )
        return []

    candidates = []

    chunks = list(
        _chunked(universe, 200)
    )

    for chunk_index, batch in enumerate(chunks, start=1):

        print(
            f"[FastDiscovery] Batch "
            f"{chunk_index}/{len(chunks)} "
            f"({len(batch)} symbols)"
        )

        snapshots = _get_snapshots(batch)

        if not snapshots:
            continue

        for ticker, snapshot in snapshots.items():

            try:
                latest_trade = (
                    snapshot.get("latestTrade") or {}
                )

                latest_quote = (
                    snapshot.get("latestQuote") or {}
                )

                daily_bar = (
                    snapshot.get("dailyBar") or {}
                )

                previous_bar = (
                    snapshot.get("prevDailyBar") or {}
                )

                price = _safe_float(
                    latest_trade.get("p")
                )

                if price is None:
                    price = _safe_float(
                        daily_bar.get("c")
                    )

                prev_close = _safe_float(
                    previous_bar.get("c")
                )

                if prev_close is None:
                    prev_close = _safe_float(
                        daily_bar.get("o")
                    )

                if price is None or prev_close is None:
                    continue

                if prev_close <= 0:
                    continue

                gap_pct = (
                    (price - prev_close)
                    / prev_close
                ) * 100.0

                # ------------------------------------------------
                # Daily volume
                # ------------------------------------------------

                volume = _safe_int(
                    daily_bar.get("v")
                )

                # ------------------------------------------------
                # Dollar volume
                # ------------------------------------------------

                dollar_volume = (
                    price * volume
                )

                # ------------------------------------------------
                # Quote / spread
                # ------------------------------------------------

                bid = _safe_float(
                    latest_quote.get("bp")
                )

                ask = _safe_float(
                    latest_quote.get("ap")
                )

                spread_pct = None

                if (
                    bid is not None and
                    ask is not None and
                    bid > 0 and
                    ask >= bid
                ):
                    mid = (bid + ask) / 2.0

                    if mid > 0:
                        spread_pct = (
                            (ask - bid) / mid
                        ) * 100.0

                # ------------------------------------------------
                # Price gate
                # ------------------------------------------------

                if price < DISCOVERY_MIN_PRICE:
                    continue

                if price > DISCOVERY_MAX_PRICE:
                    continue

                # ------------------------------------------------
                # Volume gate
                # ------------------------------------------------

                if volume < DISCOVERY_MIN_VOLUME:
                    continue

                # ------------------------------------------------
                # Gap gate
                # ------------------------------------------------

                if gap_pct < DISCOVERY_MIN_GAP:
                    continue

                if gap_pct > DISCOVERY_MAX_GAP:
                    continue

                # ------------------------------------------------
                # Quick score
                # ------------------------------------------------

                score = 0.0

                # Gap contribution: 0–35
                score += min(
                    max(gap_pct, 0.0) * 2.0,
                    35.0
                )

                # Volume contribution: 0–25
                volume_score = min(
                    volume / 100_000.0 * 5.0,
                    25.0
                )

                score += volume_score

                # Dollar volume: 0–20
                dollar_score = min(
                    dollar_volume / 5_000_000.0 * 5.0,
                    20.0
                )

                score += dollar_score

                # Spread: 0–10
                if spread_pct is None:
                    score += 3.0
                elif spread_pct <= 1.0:
                    score += 10.0
                elif spread_pct <= 2.0:
                    score += 7.0
                elif spread_pct <= 3.0:
                    score += 3.0

                # Strong gap bonus: 0–10
                if gap_pct >= 10:
                    score += 10
                elif gap_pct >= 7:
                    score += 7
                elif gap_pct >= 5:
                    score += 4

                score = round(
                    min(max(score, 0), 100),
                    1
                )

                candidate = {
                    "ticker": ticker.upper(),
                    "price": price,
                    "prev_close": prev_close,

                    "gap_pct": round(
                        gap_pct,
                        2
                    ),

                    "pm_volume": volume,

                    "daily_volume": volume,

                    "dollar_volume": round(
                        dollar_volume,
                        2
                    ),

                    "bid": bid,
                    "ask": ask,

                    "spread_pct": (
                        round(spread_pct, 3)
                        if spread_pct is not None
                        else None
                    ),

                    "pm_high": price,
                    "pm_low": price,
                    "pm_vwap": price,

                    "pm_dist_signed": 0.0,

                    "event_score": score,

                    "pm_data_quality": (
                        "DAILY_DISCOVERY"
                    ),

                    "market_data_source": "ALPACA_IEX",

                    "mode": "LIVE",

                    "strategy_version": "V4.1",
                    "data_version": "ALPACA_IEX_V41",

                    "scan_date": (
                        datetime.now(ET)
                        .strftime("%Y-%m-%d")
                    ),

                    "source": "FAST_DISCOVERY",
                }

                candidates.append(candidate)

            except Exception as e:
                # One bad ticker NEVER kills the scan.
                continue

        # Small pause protects API.
        if chunk_index < len(chunks):
            time.sleep(0.15)

    candidates.sort(
        key=lambda x: (
            x.get("event_score", 0),
            x.get("gap_pct", 0),
            x.get("dollar_volume", 0),
        ),
        reverse=True
    )

    print(
        f"[FastDiscovery] Found "
        f"{len(candidates)} candidates"
    )

    return candidates[:30]