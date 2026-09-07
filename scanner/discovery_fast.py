"""
DAYS-BOT V4.3 – Fast Discovery
- Spread: if bid/ask missing, set to UNAVAILABLE (not 0.00%)
- pm_data_quality: preserved from snapshot
"""
from datetime import datetime
from typing import Dict, List, Optional, Iterable
import time
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
MAX_RETRIES = 3
BASE_BACKOFF = 1.0

FALLBACK_LIMIT = max(15, min(30, MAX_DISCOVERY_CANDIDATES * 2))


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
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("snapshots")
    if isinstance(nested, dict):
        return nested
    snapshots = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            if ("latestTrade" in value or "latestQuote" in value or "dailyBar" in value or "prevDailyBar" in value):
                snapshots[str(key).upper()] = value
    return snapshots


def _calculate_spread(bid: float, ask: float) -> Optional[float]:
    """Return spread percentage or None if invalid data"""
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return None
    return round(((ask - bid) / mid) * 100.0, 3)


def _score_snapshot(price: float, gap_pct: float, volume: int, spread_pct: Optional[float]) -> float:
    score = 0.0
    if gap_pct > 0:
        score += min(gap_pct * 2.0, 35.0)
    elif gap_pct < 0:
        score += min(abs(gap_pct) * 0.75, 12.0)
    if volume > 0:
        score += min((volume / 100_000.0) * 10.0, 30.0)
    if DISCOVERY_MIN_PRICE <= price <= DISCOVERY_MAX_PRICE:
        score += 10.0
    if spread_pct is not None:
        if spread_pct <= 1.0:
            score += 15.0
        elif spread_pct <= 2.0:
            score += 8.0
    if gap_pct >= 10:
        score += 10.0
    elif gap_pct >= 5:
        score += 5.0
    return round(max(0.0, min(100.0, score)), 1)


def _parse_snapshot(ticker: str, snapshot: dict, now_et: datetime, strict: bool = True) -> Optional[dict]:
    latest_trade = snapshot.get("latestTrade") or {}
    latest_quote = snapshot.get("latestQuote") or {}
    daily_bar = snapshot.get("dailyBar") or {}
    prev_daily_bar = snapshot.get("prevDailyBar") or {}

    price = _safe_float(latest_trade.get("p"), _safe_float(daily_bar.get("c")))
    prev_close = _safe_float(prev_daily_bar.get("c"))
    if prev_close <= 0:
        prev_close = _safe_float(daily_bar.get("o"))
    if price <= 0 or prev_close <= 0:
        return None

    gap_pct = ((price - prev_close) / prev_close) * 100.0
    volume = _safe_int(daily_bar.get("v"))

    bid = latest_quote.get("bp")
    ask = latest_quote.get("ap")
    spread_pct = _calculate_spread(
        _safe_float(bid) if bid is not None else None,
        _safe_float(ask) if ask is not None else None,
    )

    dollar_volume = price * volume

    rejection_reasons = []
    if price < DISCOVERY_MIN_PRICE:
        rejection_reasons.append("PRICE_TOO_LOW")
    if price > DISCOVERY_MAX_PRICE:
        rejection_reasons.append("PRICE_TOO_HIGH")
    if abs(gap_pct) < DISCOVERY_MIN_GAP:
        rejection_reasons.append("GAP_TOO_SMALL")
    if volume < DISCOVERY_MIN_VOLUME:
        rejection_reasons.append("VOLUME_TOO_LOW")

    if strict:
        if price < DISCOVERY_MIN_PRICE:
            return None
        if price > DISCOVERY_MAX_PRICE:
            return None
        if abs(gap_pct) < DISCOVERY_MIN_GAP:
            return None
        if volume < DISCOVERY_MIN_VOLUME and abs(gap_pct) < 10:
            return None

    score = _score_snapshot(price, gap_pct, volume, spread_pct)
    discovery_status = "STRICT" if strict else "FALLBACK_DISCOVERY"

    return {
        "ticker": ticker.upper(),
        "price": round(price, 4),
        "prev_close": round(prev_close, 4),
        "gap_pct": round(gap_pct, 2),
        "pm_volume": volume,
        "pm_bars": 0,
        "pm_high": price,
        "pm_low": price,
        "pm_vwap": price,
        "pm_dist_signed": 0.0,
        "spread_pct": spread_pct,  # may be None
        "bid": bid,
        "ask": ask,
        "dollar_volume": round(dollar_volume, 2),
        "event_score": score,
        "discovery_score": score,
        "discovery_status": discovery_status,
        "rejection_reasons": rejection_reasons,
        "pm_data_quality": "SNAPSHOT_DATA",
        "mode": "LIVE",
        "strategy_version": "V4.2.1",
        "data_version": "ALPACA_IEX_V421",
        "scan_date": now_et.strftime("%Y-%m-%d"),
        "source": "ALPACA_SNAPSHOT",
    }


def _print_top_candidates(candidates: List[dict], title: str = "TOP CANDIDATES"):
    print()
    print("=" * 74)
    print(f"[FastDiscovery] {title}")
    print("=" * 74)
    for i, c in enumerate(candidates[:10], 1):
        ticker = c.get("ticker", "???")
        score = c.get("discovery_score", 0)
        gap = c.get("gap_pct", 0)
        volume = c.get("pm_volume", 0)
        spread = c.get("spread_pct")
        spread_str = f"{spread:.2f}%" if spread is not None else "N/A"
        status = c.get("discovery_status", "UNKNOWN")
        print(f"{i:2d}. {ticker:6s} score={score:5.1f} gap={gap:+6.2f}% vol={volume:>10,} spread={spread_str:>6} status={status}")


def _print_diagnostics(batches, successful_batches, failed_batches, requested_symbols, returned_snapshots,
                        valid_price, valid_prev_close, parsed_raw, strict_candidates, fallback_candidates,
                        reject_price_low, reject_price_high, reject_gap, reject_volume, reject_invalid):
    print()
    print("=" * 74)
    print("[FastDiscovery] DIAGNOSTICS")
    print("=" * 74)
    print(f"Batches:                     {batches}")
    print(f"Successful batches:          {successful_batches}")
    print(f"Failed batches:              {failed_batches}")
    print(f"Requested symbols:           {requested_symbols}")
    print(f"Returned snapshots:          {returned_snapshots}")
    print(f"Valid price:                 {valid_price}")
    print(f"Valid prev_close:            {valid_prev_close}")
    print(f"Parsed raw:                  {parsed_raw}")
    print(f"Strict candidates:           {strict_candidates}")
    print(f"Fallback candidates:         {fallback_candidates}")
    print("-" * 74)
    print(f"Rejected: price_low          {reject_price_low}")
    print(f"Rejected: price_high         {reject_price_high}")
    print(f"Rejected: gap                {reject_gap}")
    print(f"Rejected: volume             {reject_volume}")
    print(f"Rejected: invalid            {reject_invalid}")


def _request_with_retry(session, batch, attempt=0):
    try:
        response = session.get(
            SNAPSHOT_URL,
            params={"symbols": ",".join(batch), "feed": "iex"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 429 and attempt < MAX_RETRIES:
            wait = BASE_BACKOFF * (2 ** attempt)
            print(f"[FastDiscovery] 429 – retrying in {wait:.1f}s (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(wait)
            return _request_with_retry(session, batch, attempt + 1)
        return response
    except Exception as e:
        print(f"[FastDiscovery] Request error: {e}")
        return None


def fast_discovery() -> List[dict]:
    now_et = datetime.now(ET)
    universe = load_universe()
    if not universe:
        print("[FastDiscovery] ERROR: Empty universe")
        return []
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print("[FastDiscovery] ERROR: Missing ALPACA_API_KEY or ALPACA_SECRET_KEY")
        return []

    clean_universe = []
    seen = set()
    for symbol in universe:
        symbol = str(symbol).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        clean_universe.append(symbol)

    print()
    print("=" * 74)
    print("[FastDiscovery] V4.3 ALPACA DISCOVERY")
    print("=" * 74)
    print(f"[FastDiscovery] Universe symbols: {len(clean_universe)}")
    print(f"[FastDiscovery] Batch size: {BATCH_SIZE}")
    print(f"[FastDiscovery] Endpoint: {SNAPSHOT_URL}")
    print(f"[FastDiscovery] Feed: IEX")
    print(f"[FastDiscovery] Max retries: {MAX_RETRIES}")

    batches = 0
    successful_batches = 0
    failed_batches = 0
    requested_symbols = 0
    returned_snapshots = 0
    valid_price = 0
    valid_prev_close = 0
    parsed_raw = 0
    strict_candidates = []
    fallback_candidates = []
    reject_price_low = 0
    reject_price_high = 0
    reject_gap = 0
    reject_volume = 0
    reject_invalid = 0

    session = requests.Session()
    session.headers.update(_headers())

    for batch in _chunks(clean_universe, BATCH_SIZE):
        batches += 1
        requested_symbols += len(batch)
        print(f"[FastDiscovery] Batch {batches}: requesting {len(batch)} symbols...")

        response = _request_with_retry(session, batch)
        if response is None:
            failed_batches += 1
            continue

        if response.status_code != 200:
            failed_batches += 1
            print(f"[FastDiscovery] Batch {batches} HTTP: {response.status_code}")
            print(f"[FastDiscovery] Alpaca error: {response.text[:500]}")
            continue

        successful_batches += 1
        try:
            payload = response.json()
        except ValueError as exc:
            failed_batches += 1
            print(f"[FastDiscovery] JSON decode error: {exc}")
            continue

        snapshots = _extract_snapshots(payload)
        batch_returned = len(snapshots)
        returned_snapshots += batch_returned
        print(f"[FastDiscovery] Batch {batches}: snapshots returned = {batch_returned}")

        if batch_returned > 0:
            sample_symbols = list(snapshots.keys())[:5]
            print("[FastDiscovery] Sample symbols: " + ", ".join(sample_symbols))

        for ticker, snapshot in snapshots.items():
            try:
                raw_price = _safe_float(
                    snapshot.get("latestTrade", {}).get("p"),
                    _safe_float(snapshot.get("dailyBar", {}).get("c"))
                )
                raw_prev_close = _safe_float(snapshot.get("prevDailyBar", {}).get("c"))
                if raw_price > 0:
                    valid_price += 1
                if raw_prev_close > 0:
                    valid_prev_close += 1

                fallback = _parse_snapshot(ticker, snapshot, now_et, strict=False)
                if fallback is None:
                    reject_invalid += 1
                    continue

                parsed_raw += 1
                fallback_candidates.append(fallback)

                reasons = set(fallback.get("rejection_reasons", []))
                if "PRICE_TOO_LOW" in reasons:
                    reject_price_low += 1
                if "PRICE_TOO_HIGH" in reasons:
                    reject_price_high += 1
                if "GAP_TOO_SMALL" in reasons:
                    reject_gap += 1
                if "VOLUME_TOO_LOW" in reasons:
                    reject_volume += 1

                strict_candidate = _parse_snapshot(ticker, snapshot, now_et, strict=True)
                if strict_candidate:
                    strict_candidates.append(strict_candidate)

            except Exception as exc:
                reject_invalid += 1
                print(f"[FastDiscovery] {ticker} parse error: {exc}")

        time.sleep(0.5)

    strict_candidates.sort(key=lambda x: (x.get("discovery_score", 0), abs(x.get("gap_pct", 0)), x.get("pm_volume", 0)), reverse=True)

    if strict_candidates:
        result = strict_candidates[:MAX_DISCOVERY_CANDIDATES]
        print()
        print(f"[FastDiscovery] STRICT candidates: {len(strict_candidates)}")
        print(f"[FastDiscovery] Returning: {len(result)}")
        _print_top_candidates(result, title="TOP STRICT CANDIDATES")
        _print_diagnostics(
            batches, successful_batches, failed_batches, requested_symbols,
            returned_snapshots, valid_price, valid_prev_close, parsed_raw,
            len(strict_candidates), len(fallback_candidates),
            reject_price_low, reject_price_high, reject_gap, reject_volume, reject_invalid
        )
        print("=" * 74)
        return result

    print()
    print("[FastDiscovery] WARNING: No strict candidates.")
    if not fallback_candidates:
        print("[FastDiscovery] CRITICAL: No usable snapshots were parsed.")
        _print_diagnostics(
            batches, successful_batches, failed_batches, requested_symbols,
            returned_snapshots, valid_price, valid_prev_close, parsed_raw,
            len(strict_candidates), len(fallback_candidates),
            reject_price_low, reject_price_high, reject_gap, reject_volume, reject_invalid
        )
        print("=" * 74)
        return []

    fallback_candidates.sort(key=lambda x: (x.get("discovery_score", 0), abs(x.get("gap_pct", 0)), x.get("pm_volume", 0)), reverse=True)
    fallback_result = fallback_candidates[:FALLBACK_LIMIT]
    print(f"[FastDiscovery] Using fallback: {len(fallback_result)} real market movers")
    _print_top_candidates(fallback_result, title="FALLBACK CANDIDATES")
    _print_diagnostics(
        batches, successful_batches, failed_batches, requested_symbols,
        returned_snapshots, valid_price, valid_prev_close, parsed_raw,
        len(strict_candidates), len(fallback_candidates),
        reject_price_low, reject_price_high, reject_gap, reject_volume, reject_invalid
    )
    print("=" * 74)
    return fallback_result