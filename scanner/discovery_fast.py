"""
DAYS-BOT V4.2 – Fast Discovery

Primary discovery layer using Alpaca Stock Snapshots.

IMPORTANT:
- No yfinance.
- Never silently converts a valid Alpaca response into zero symbols.
- Supports both known Alpaca snapshot response shapes.
- Provides detailed diagnostics.
- Uses strict candidates first.
- If strict filtering produces zero candidates, returns a controlled
  fallback list of real market movers marked as FALLBACK_DISCOVERY.

This module is discovery only.
It does NOT decide whether a stock is a trade.
"""

from datetime import datetime
from typing import Dict, List, Optional, Iterable

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

SNAPSHOT_URL = f"{ALPACA_DATA_URL.rstrip('/')}/v2/stocks/snapshots"

BATCH_SIZE = 200
REQUEST_TIMEOUT = 15

# Fallback is deliberately larger than the normal candidate limit.
# It gives the downstream engine something to inspect when the strict
# discovery thresholds are too aggressive.
FALLBACK_LIMIT = max(
    15,
    min(30, MAX_DISCOVERY_CANDIDATES * 2),
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _headers() -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Accept": "application/json",
    }


def _chunks(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_snapshots(payload: dict) -> Dict[str, dict]:
    """
    Alpaca's stocks snapshots response is normally:

        {
            "AAPL": {...},
            "MSFT": {...}
        }

    Some wrappers may expose:

        {
            "snapshots": {
                "AAPL": {...}
            }
        }

    Support both so a response shape cannot silently produce zero data.
    """

    if not isinstance(payload, dict):
        return {}

    nested = payload.get("snapshots")

    if isinstance(nested, dict):
        return nested

    # Normal Alpaca response:
    # keep only entries that look like snapshot objects.
    snapshots = {}

    for key, value in payload.items():
        if isinstance(value, dict):
            if (
                "latestTrade" in value
                or "latestQuote" in value
                or "dailyBar" in value
                or "prevDailyBar" in value
            ):
                snapshots[str(key).upper()] = value

    return snapshots


def _calculate_spread(
    bid: float,
    ask: float,
) -> float:
    if bid <= 0 or ask <= 0 or ask < bid:
        return 0.0

    mid = (bid + ask) / 2.0

    if mid <= 0:
        return 0.0

    return ((ask - bid) / mid) * 100.0


# ---------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------

def _score_snapshot(
    price: float,
    gap_pct: float,
    volume: int,
    spread_pct: float,
) -> float:
    """
    Discovery score only.

    This is NOT the final trading score.
    """

    score = 0.0

    # Positive gap
    if gap_pct > 0:
        score += min(gap_pct * 2.0, 35.0)

    # Absolute movement also matters for fallback discovery.
    elif gap_pct < 0:
        score += min(abs(gap_pct) * 0.75, 12.0)

    # Volume
    if volume > 0:
        score += min(
            (volume / 100_000.0) * 10.0,
            30.0,
        )

    # Preferred price range
    if DISCOVERY_MIN_PRICE <= price <= DISCOVERY_MAX_PRICE:
        score += 10.0

    # Spread
    if spread_pct <= 1.0:
        score += 15.0
    elif spread_pct <= 2.0:
        score += 8.0

    # Momentum bonus
    if gap_pct >= 10:
        score += 10.0
    elif gap_pct >= 5:
        score += 5.0

    return round(
        max(0.0, min(100.0, score)),
        1,
    )


# ---------------------------------------------------------------------
# Snapshot parser
# ---------------------------------------------------------------------

def _parse_snapshot(
    ticker: str,
    snapshot: dict,
    now_et: datetime,
    strict: bool = True,
) -> Optional[dict]:
    """
    Parse one Alpaca snapshot.

    When strict=False, do not enforce discovery thresholds.
    This is used only for fallback diagnostics/discovery.
    """

    latest_trade = snapshot.get("latestTrade") or {}
    latest_quote = snapshot.get("latestQuote") or {}

    daily_bar = snapshot.get("dailyBar") or {}
    prev_daily_bar = snapshot.get("prevDailyBar") or {}

    # ---------------------------------------------------------------
    # Current price
    # ---------------------------------------------------------------

    price = _safe_float(
        latest_trade.get("p"),
        _safe_float(daily_bar.get("c")),
    )

    # ---------------------------------------------------------------
    # Previous close
    # ---------------------------------------------------------------

    prev_close = _safe_float(
        prev_daily_bar.get("c")
    )

    # Fallback only if prevDailyBar is unavailable.
    if prev_close <= 0:
        prev_close = _safe_float(
            daily_bar.get("o")
        )

    # We cannot calculate a meaningful gap without both.
    if price <= 0 or prev_close <= 0:
        return None

    # ---------------------------------------------------------------
    # Gap
    # ---------------------------------------------------------------

    gap_pct = (
        (price - prev_close)
        / prev_close
        * 100.0
    )

    # ---------------------------------------------------------------
    # Volume
    # ---------------------------------------------------------------

    volume = _safe_int(
        daily_bar.get("v")
    )

    # ---------------------------------------------------------------
    # Quote / spread
    # ---------------------------------------------------------------

    bid = _safe_float(
        latest_quote.get("bp")
    )

    ask = _safe_float(
        latest_quote.get("ap")
    )

    spread_pct = _calculate_spread(
        bid,
        ask,
    )

    dollar_volume = price * volume

    # ---------------------------------------------------------------
    # Rejection reason
    # ---------------------------------------------------------------

    rejection_reasons = []

    if price < DISCOVERY_MIN_PRICE:
        rejection_reasons.append("PRICE_TOO_LOW")

    if price > DISCOVERY_MAX_PRICE:
        rejection_reasons.append("PRICE_TOO_HIGH")

    if abs(gap_pct) < DISCOVERY_MIN_GAP:
        rejection_reasons.append("GAP_TOO_SMALL")

    if volume < DISCOVERY_MIN_VOLUME:
        rejection_reasons.append("VOLUME_TOO_LOW")

    # ---------------------------------------------------------------
    # Strict filtering
    # ---------------------------------------------------------------

    if strict:
        if price < DISCOVERY_MIN_PRICE:
            return None

        if price > DISCOVERY_MAX_PRICE:
            return None

        if abs(gap_pct) < DISCOVERY_MIN_GAP:
            return None

        # Exceptional movers can survive low volume.
        if volume < DISCOVERY_MIN_VOLUME:
            if abs(gap_pct) < 10:
                return None

    score = _score_snapshot(
        price=price,
        gap_pct=gap_pct,
        volume=volume,
        spread_pct=spread_pct,
    )

    if strict:
        discovery_status = "STRICT"
    else:
        discovery_status = "FALLBACK_DISCOVERY"

    return {
        "ticker": ticker.upper(),

        "price": round(price, 4),
        "prev_close": round(prev_close, 4),

        "gap_pct": round(gap_pct, 2),

        # Keep legacy field names because the existing downstream
        # modules expect them.
        "pm_volume": volume,
        "pm_bars": 0,
        "pm_high": price,
        "pm_low": price,
        "pm_vwap": price,
        "pm_dist_signed": 0.0,

        "spread_pct": round(spread_pct, 3),
        "bid": bid,
        "ask": ask,

        "dollar_volume": round(
            dollar_volume,
            2,
        ),

        "event_score": score,

        "discovery_score": score,
        "discovery_status": discovery_status,

        "rejection_reasons": rejection_reasons,

        "pm_data_quality": "SNAPSHOT_DATA",
        "mode": "LIVE",

        "strategy_version": "V4.2",
        "data_version": "ALPACA_IEX_V42",

        "scan_date": now_et.strftime("%Y-%m-%d"),

        "source": "ALPACA_SNAPSHOT",
    }


# ---------------------------------------------------------------------
# Diagnostics printer
# ---------------------------------------------------------------------

def _print_top_candidates(
    candidates: List[dict],
    title: str = "TOP CANDIDATES",
):
    print()
    print("=" * 74)
    print(f"[FastDiscovery] {title}")
    print("=" * 74)

    for i, c in enumerate(candidates[:10], 1):
        ticker = c.get("ticker", "???")
        score = c.get("discovery_score", 0)
        gap = c.get("gap_pct", 0)
        volume = c.get("pm_volume", 0)
        status = c.get("discovery_status", "UNKNOWN")

        print(
            f"{i:2d}. {ticker:6s} "
            f"score={score:5.1f} "
            f"gap={gap:+6.2f}% "
            f"vol={volume:>10,} "
            f"status={status}"
        )


def _print_diagnostics(
    batches: int,
    successful_batches: int,
    failed_batches: int,
    requested_symbols: int,
    returned_snapshots: int,
    valid_price: int,
    valid_prev_close: int,
    parsed_raw: int,
    strict_candidates: int,
    fallback_candidates: int,
    reject_price_low: int,
    reject_price_high: int,
    reject_gap: int,
    reject_volume: int,
    reject_invalid: int,
):

    print()
    print("=" * 74)
    print("[FastDiscovery] DIAGNOSTICS")
    print("=" * 74)

    print(
        f"Batches:                     {batches}"
    )

    print(
        f"Successful batches:          {successful_batches}"
    )

    print(
        f"Failed batches:              {failed_batches}"
    )

    print(
        f"Requested symbols:           {requested_symbols}"
    )

    print(
        f"Returned snapshots:          {returned_snapshots}"
    )

    print(
        f"Valid price:                 {valid_price}"
    )

    print(
        f"Valid prev_close:            {valid_prev_close}"
    )

    print(
        f"Parsed raw:                  {parsed_raw}"
    )

    print(
        f"Strict candidates:           {strict_candidates}"
    )

    print(
        f"Fallback candidates:         {fallback_candidates}"
    )

    print("-" * 74)

    print(
        f"Rejected: price_low          {reject_price_low}"
    )

    print(
        f"Rejected: price_high         {reject_price_high}"
    )

    print(
        f"Rejected: gap                {reject_gap}"
    )

    print(
        f"Rejected: volume             {reject_volume}"
    )

    print(
        f"Rejected: invalid            {reject_invalid}"
    )


# ---------------------------------------------------------------------
# Main discovery
# ---------------------------------------------------------------------

def fast_discovery() -> List[dict]:
    """
    Scan the configured universe through Alpaca snapshots.

    Flow:

        Universe
           ↓
        Alpaca
           ↓
        Raw snapshots
           ↓
        Parse
           ↓
        Strict candidates
           ↓
        Fallback if needed
    """

    now_et = datetime.now(ET)

    universe = load_universe()

    if not universe:
        print("[FastDiscovery] ERROR: Empty universe")
        return []

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print(
            "[FastDiscovery] ERROR: Missing "
            "ALPACA_API_KEY or ALPACA_SECRET_KEY"
        )
        return []

    # Remove duplicates while preserving order.
    clean_universe = []

    seen = set()

    for symbol in universe:
        symbol = str(symbol).strip().upper()

        if not symbol:
            continue

        if symbol in seen:
            continue

        seen.add(symbol)
        clean_universe.append(symbol)

    print()
    print("=" * 74)
    print("[FastDiscovery] V4.2 ALPACA DISCOVERY")
    print("=" * 74)

    print(
        f"[FastDiscovery] Universe symbols: "
        f"{len(clean_universe)}"
    )

    print(
        f"[FastDiscovery] Batch size: "
        f"{BATCH_SIZE}"
    )

    print(
        f"[FastDiscovery] Endpoint: "
        f"{SNAPSHOT_URL}"
    )

    print(
        f"[FastDiscovery] Feed: IEX"
    )

    # -----------------------------------------------------------------
    # Counters
    # -----------------------------------------------------------------

    batches = 0
    successful_batches = 0
    failed_batches = 0

    requested_symbols = 0
    returned_snapshots = 0
    valid_price = 0
    valid_prev_close = 0
    parsed_raw = 0

    strict_candidates = []

    # Store raw parsed candidates for fallback.
    fallback_candidates = []

    reject_price_low = 0
    reject_price_high = 0
    reject_gap = 0
    reject_volume = 0
    reject_invalid = 0

    session = requests.Session()
    session.headers.update(_headers())

    # -----------------------------------------------------------------
    # Alpaca requests
    # -----------------------------------------------------------------

    for batch in _chunks(
        clean_universe,
        BATCH_SIZE,
    ):
        batches += 1
        requested_symbols += len(batch)

        print(
            f"[FastDiscovery] Batch "
            f"{batches}: requesting "
            f"{len(batch)} symbols..."
        )

        try:
            response = session.get(
                SNAPSHOT_URL,
                params={
                    "symbols": ",".join(batch),
                    "feed": "iex",
                },
                timeout=REQUEST_TIMEOUT,
            )

            print(
                f"[FastDiscovery] Batch "
                f"{batches} HTTP: "
                f"{response.status_code}"
            )

            if response.status_code != 200:
                failed_batches += 1

                print(
                    "[FastDiscovery] Alpaca error: "
                    f"{response.text[:500]}"
                )

                continue

            successful_batches += 1

            try:
                payload = response.json()
            except ValueError as exc:
                failed_batches += 1

                print(
                    "[FastDiscovery] JSON decode error: "
                    f"{exc}"
                )

                continue

            snapshots = _extract_snapshots(
                payload
            )

            batch_returned = len(snapshots)
            returned_snapshots += batch_returned

            print(
                f"[FastDiscovery] Batch "
                f"{batches}: snapshots returned = "
                f"{batch_returned}"
            )

            # CRITICAL DIAGNOSTIC:
            # If Alpaca returned data, print first symbols.
            if batch_returned > 0:
                sample_symbols = list(
                    snapshots.keys()
                )[:5]

                print(
                    "[FastDiscovery] Sample symbols: "
                    + ", ".join(sample_symbols)
                )

            for ticker, snapshot in snapshots.items():

                try:
                    # -------------------------------------------------
                    # Raw data diagnostics
                    # -------------------------------------------------

                    latest_trade = (
                        snapshot.get("latestTrade")
                        or {}
                    )

                    daily_bar = (
                        snapshot.get("dailyBar")
                        or {}
                    )

                    raw_price = _safe_float(
                        latest_trade.get("p"),
                        _safe_float(
                            daily_bar.get("c")
                        ),
                    )

                    raw_prev_close = _safe_float(
                        (
                            snapshot.get("prevDailyBar")
                            or {}
                        ).get("c")
                    )

                    if raw_price > 0:
                        valid_price += 1

                    if raw_prev_close > 0:
                        valid_prev_close += 1

                    # -------------------------------------------------
                    # Parse unrestricted version first
                    # -------------------------------------------------

                    fallback = _parse_snapshot(
                        ticker=ticker,
                        snapshot=snapshot,
                        now_et=now_et,
                        strict=False,
                    )

                    if fallback is None:
                        reject_invalid += 1
                        continue

                    parsed_raw += 1

                    fallback_candidates.append(
                        fallback
                    )

                    # -------------------------------------------------
                    # Count rejection reasons
                    # -------------------------------------------------

                    reasons = set(
                        fallback.get(
                            "rejection_reasons",
                            [],
                        )
                    )

                    if "PRICE_TOO_LOW" in reasons:
                        reject_price_low += 1

                    if "PRICE_TOO_HIGH" in reasons:
                        reject_price_high += 1

                    if "GAP_TOO_SMALL" in reasons:
                        reject_gap += 1

                    if "VOLUME_TOO_LOW" in reasons:
                        reject_volume += 1

                    # -------------------------------------------------
                    # Strict version
                    # -------------------------------------------------

                    strict_candidate = _parse_snapshot(
                        ticker=ticker,
                        snapshot=snapshot,
                        now_et=now_et,
                        strict=True,
                    )

                    if strict_candidate:
                        strict_candidates.append(
                            strict_candidate
                        )

                except Exception as exc:
                    reject_invalid += 1

                    print(
                        f"[FastDiscovery] "
                        f"{ticker} parse error: {exc}"
                    )

        except requests.RequestException as exc:
            failed_batches += 1

            print(
                f"[FastDiscovery] Batch "
                f"{batches} request error: "
                f"{exc}"
            )

        except Exception as exc:
            failed_batches += 1

            print(
                f"[FastDiscovery] Batch "
                f"{batches} unexpected error: "
                f"{exc}"
            )

    # -----------------------------------------------------------------
    # Sort strict candidates
    # -----------------------------------------------------------------

    strict_candidates.sort(
        key=lambda x: (
            x.get("discovery_score", 0),
            abs(x.get("gap_pct", 0)),
            x.get("pm_volume", 0),
        ),
        reverse=True,
    )

    # -----------------------------------------------------------------
    # If strict candidates exist, use them.
    # -----------------------------------------------------------------

    if strict_candidates:

        result = strict_candidates[
            :MAX_DISCOVERY_CANDIDATES
        ]

        print()
        print(
            "[FastDiscovery] STRICT candidates: "
            f"{len(strict_candidates)}"
        )

        print(
            "[FastDiscovery] Returning: "
            f"{len(result)}"
        )

        _print_top_candidates(
            result,
            title="TOP STRICT CANDIDATES",
        )

        _print_diagnostics(
            batches=batches,
            successful_batches=successful_batches,
            failed_batches=failed_batches,
            requested_symbols=requested_symbols,
            returned_snapshots=returned_snapshots,
            valid_price=valid_price,
            valid_prev_close=valid_prev_close,
            parsed_raw=parsed_raw,
            strict_candidates=len(strict_candidates),
            fallback_candidates=len(fallback_candidates),
            reject_price_low=reject_price_low,
            reject_price_high=reject_price_high,
            reject_gap=reject_gap,
            reject_volume=reject_volume,
            reject_invalid=reject_invalid,
        )

        print("=" * 74)

        return result

    # -----------------------------------------------------------------
    # NO STRICT CANDIDATES
    #
    # Do NOT return [] silently.
    #
    # Use real parsed market data and return the strongest movers,
    # explicitly marked FALLBACK_DISCOVERY.
    # -----------------------------------------------------------------

    print()
    print(
        "[FastDiscovery] WARNING: "
        "No strict candidates."
    )

    if not fallback_candidates:
        print(
            "[FastDiscovery] CRITICAL: "
            "No usable snapshots were parsed."
        )

        _print_diagnostics(
            batches=batches,
            successful_batches=successful_batches,
            failed_batches=failed_batches,
            requested_symbols=requested_symbols,
            returned_snapshots=returned_snapshots,
            valid_price=valid_price,
            valid_prev_close=valid_prev_close,
            parsed_raw=parsed_raw,
            strict_candidates=len(strict_candidates),
            fallback_candidates=len(fallback_candidates),
            reject_price_low=reject_price_low,
            reject_price_high=reject_price_high,
            reject_gap=reject_gap,
            reject_volume=reject_volume,
            reject_invalid=reject_invalid,
        )

        print("=" * 74)

        return []

    fallback_candidates.sort(
        key=lambda x: (
            x.get("discovery_score", 0),
            abs(x.get("gap_pct", 0)),
            x.get("pm_volume", 0),
        ),
        reverse=True,
    )

    fallback_result = fallback_candidates[
        :FALLBACK_LIMIT
    ]

    print()
    print(
        "[FastDiscovery] Using fallback discovery: "
        f"{len(fallback_result)} real market movers"
    )

    _print_top_candidates(
        fallback_result,
        title="FALLBACK CANDIDATES (REAL MARKET DATA)",
    )

    _print_diagnostics(
        batches=batches,
        successful_batches=successful_batches,
        failed_batches=failed_batches,
        requested_symbols=requested_symbols,
        returned_snapshots=returned_snapshots,
        valid_price=valid_price,
        valid_prev_close=valid_prev_close,
        parsed_raw=parsed_raw,
        strict_candidates=len(strict_candidates),
        fallback_candidates=len(fallback_candidates),
        reject_price_low=reject_price_low,
        reject_price_high=reject_price_high,
        reject_gap=reject_gap,
        reject_volume=reject_volume,
        reject_invalid=reject_invalid,
    )

    print("=" * 74)

    return fallback_result
