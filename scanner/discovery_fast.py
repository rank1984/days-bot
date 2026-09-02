"""
DAYS-BOT V4.1 – Fast Discovery

Uses Alpaca Market Data snapshots instead of yfinance.

Goal:
- Quickly find actual movers.
- Avoid yfinance 429 / crumb / delisted errors.
- Return candidates even when some fields are missing.
"""

from datetime import datetime
from typing import Dict, List

import pytz
import requests

from scanner.universe import load_universe
from utils.config import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_DATA_URL,
    DISCOVERY_MIN_PRICE,
    DISCOVERY_MAX_PRICE,
    DISCOVERY_MIN_GAP,
    DISCOVERY_MIN_VOLUME,
    MAX_DISCOVERY_CANDIDATES,
)


ET = pytz.timezone("America/New_York")

SNAPSHOT_URL = (
    f"{ALPACA_DATA_URL}/v2/stocks/snapshots"
)

BATCH_SIZE = 200


def _headers() -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }


def _chunks(items: List[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _safe_float(value, default=0.0):
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
        return int(value)
    except Exception:
        return default


def _score_snapshot(
    price: float,
    gap_pct: float,
    volume: int,
    spread_pct: float,
) -> float:

    score = 0.0

    # Gap
    if gap_pct > 0:
        score += min(gap_pct * 2.0, 35.0)

    # Volume
    if volume > 0:
        score += min(
            (volume / 100_000.0) * 10.0,
            30.0,
        )

    # Price
    if DISCOVERY_MIN_PRICE <= price <= DISCOVERY_MAX_PRICE:
        score += 10.0

    # Spread
    if spread_pct <= 1.0:
        score += 15.0
    elif spread_pct <= 2.0:
        score += 8.0

    # Stronger gap bonus
    if gap_pct >= 10:
        score += 10.0
    elif gap_pct >= 5:
        score += 5.0

    return round(
        max(0.0, min(100.0, score)),
        1,
    )


def _parse_snapshot(
    ticker: str,
    snapshot: dict,
    now_et: datetime,
) -> dict | None:

    latest_trade = snapshot.get("latestTrade") or {}
    latest_quote = snapshot.get("latestQuote") or {}

    daily_bar = snapshot.get("dailyBar") or {}
    prev_daily_bar = snapshot.get("prevDailyBar") or {}

    price = _safe_float(
        latest_trade.get("p"),
        _safe_float(daily_bar.get("c")),
    )

    prev_close = _safe_float(
        prev_daily_bar.get("c")
    )

    if prev_close <= 0:
        prev_close = _safe_float(
            daily_bar.get("o")
        )

    if price <= 0 or prev_close <= 0:
        return None

    gap_pct = (
        (price - prev_close)
        / prev_close
        * 100.0
    )

    volume = _safe_int(
        daily_bar.get("v")
    )

    bid = _safe_float(
        latest_quote.get("bp")
    )

    ask = _safe_float(
        latest_quote.get("ap")
    )

    spread_pct = 0.0

    if bid > 0 and ask > 0 and ask >= bid:
        mid = (bid + ask) / 2.0

        if mid > 0:
            spread_pct = (
                (ask - bid)
                / mid
                * 100.0
            )

    # Hard discovery filters.
    if price < DISCOVERY_MIN_PRICE:
        return None

    if price > DISCOVERY_MAX_PRICE:
        return None

    if abs(gap_pct) < DISCOVERY_MIN_GAP:
        return None

    if volume < DISCOVERY_MIN_VOLUME:
        # Keep the candidate if the gap is exceptional.
        if abs(gap_pct) < 10:
            return None

    score = _score_snapshot(
        price=price,
        gap_pct=gap_pct,
        volume=volume,
        spread_pct=spread_pct,
    )

    return {
        "ticker": ticker,
        "price": price,
        "prev_close": prev_close,
        "gap_pct": round(gap_pct, 2),
        "pm_volume": volume,
        "pm_bars": 0,
        "pm_high": price,
        "pm_low": price,
        "pm_vwap": price,
        "pm_dist_signed": 0.0,
        "spread_pct": round(spread_pct, 3),
        "bid": bid,
        "ask": ask,
        "event_score": score,
        "pm_data_quality": "SNAPSHOT_DATA",
        "mode": "LIVE",
        "strategy_version": "V4.1",
        "data_version": "ALPACA_IEX_V41",
        "scan_date": now_et.strftime("%Y-%m-%d"),
        "source": "ALPACA_SNAPSHOT",
    }


def fast_discovery() -> List[dict]:

    now_et = datetime.now(ET)

    universe = load_universe()

    if not universe:
        print("[FastDiscovery] Empty universe")
        return []

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print(
            "[FastDiscovery] Missing ALPACA_API_KEY "
            "or ALPACA_SECRET_KEY"
        )
        return []

    print(
        f"[FastDiscovery] Scanning "
        f"{len(universe)} symbols via Alpaca..."
    )

    candidates = []

    session = requests.Session()
    session.headers.update(_headers())

    for batch in _chunks(universe, BATCH_SIZE):

        try:
            response = session.get(
                SNAPSHOT_URL,
                params={
                    "symbols": ",".join(batch),
                    "feed": "iex",
                },
                timeout=20,
            )

            if response.status_code != 200:
                print(
                    "[FastDiscovery] Alpaca HTTP "
                    f"{response.status_code}: "
                    f"{response.text[:200]}"
                )
                continue

            payload = response.json()

            snapshots = payload.get(
                "snapshots",
                {},
            )

            for ticker, snapshot in snapshots.items():

                try:
                    candidate = _parse_snapshot(
                        ticker,
                        snapshot,
                        now_et,
                    )

                    if candidate:
                        candidates.append(candidate)

                except Exception as e:
                    print(
                        f"[FastDiscovery] "
                        f"{ticker} parse error: {e}"
                    )

        except Exception as e:
            print(
                f"[FastDiscovery] Request error: {e}"
            )

    candidates.sort(
        key=lambda x: (
            x.get("event_score", 0),
            abs(x.get("gap_pct", 0)),
            x.get("pm_volume", 0),
        ),
        reverse=True,
    )

    print(
        f"[FastDiscovery] Found "
        f"{len(candidates)} candidates"
    )

    return candidates[:MAX_DISCOVERY_CANDIDATES]
