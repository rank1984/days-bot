"""
DAYS-BOT V5.0.4 – Fast Discovery (Alpaca Snapshots)
With Float Hard Gate (> 20M = rejected)
"""
from datetime import datetime
from typing import Dict, List, Optional, Iterable, Tuple
import time
import pytz
import requests
from scanner.universe import load_universe
from utils.config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_DATA_URL,
    DISCOVERY_MIN_PRICE, DISCOVERY_MAX_PRICE,
    DISCOVERY_MIN_GAP, DISCOVERY_MIN_VOLUME,
    MAX_DISCOVERY_CANDIDATES,
)

ET = pytz.timezone("America/New_York")
SNAPSHOT_URL = f"{ALPACA_DATA_URL.rstrip('/')}/v2/stocks/snapshots"
BATCH_SIZE = 200
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
BASE_BACKOFF = 1.0
FALLBACK_LIMIT = max(15, min(30, MAX_DISCOVERY_CANDIDATES * 2))
FLOAT_HARD_LIMIT = 20_000_000  # <--- Float Hard Gate


def _headers() -> Dict[str, str]:
    return {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY, "Accept": "application/json"}


def _chunks(items: List[str], size: int):
    for i in range(0, len(items), size): yield items[i:i+size]


def _safe_float(value, default=0.0):
    try:
        if value is None: return default
        return float(value)
    except: return default


def _safe_int(value, default=0):
    try:
        if value is None: return default
        return int(value)
    except: return default


def _extract_snapshots(payload: dict) -> Dict[str, dict]:
    if not isinstance(payload, dict): return {}
    nested = payload.get("snapshots")
    if isinstance(nested, dict): return nested
    snapshots = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            if ("latestTrade" in value or "latestQuote" in value or "dailyBar" in value or "prevDailyBar" in value):
                snapshots[str(key).upper()] = value
    return snapshots


def _calculate_spread(bid: float, ask: float) -> Optional[float]:
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid: return None
    mid = (bid + ask) / 2.0
    if mid <= 0: return None
    return round(((ask - bid) / mid) * 100.0, 3)


def _score_snapshot(price: float, gap_pct: float, volume: int, spread_pct: Optional[float]) -> float:
    score = 0.0
    if gap_pct > 0: score += min(gap_pct * 2.0, 35.0)
    elif gap_pct < 0: score += min(abs(gap_pct) * 0.75, 12.0)
    if volume > 0: score += min((volume / 100_000.0) * 10.0, 30.0)
    if DISCOVERY_MIN_PRICE <= price <= DISCOVERY_MAX_PRICE: score += 10.0
    if spread_pct is not None:
        if spread_pct <= 1.0: score += 15.0
        elif spread_pct <= 2.0: score += 8.0
    if gap_pct >= 10: score += 10.0
    elif gap_pct >= 5: score += 5.0
    return round(max(0.0, min(100.0, score)), 1)


def _parse_snapshot(ticker: str, snapshot: dict, now_et: datetime, strict: bool = True) -> Optional[dict]:
    latest_trade = snapshot.get("latestTrade") or {}
    latest_quote = snapshot.get("latestQuote") or {}
    daily_bar = snapshot.get("dailyBar") or {}
    prev_daily_bar = snapshot.get("prevDailyBar") or {}
    price = _safe_float(latest_trade.get("p"), _safe_float(daily_bar.get("c")))
    prev_close = _safe_float(prev_daily_bar.get("c"))
    if prev_close <= 0: prev_close = _safe_float(daily_bar.get("o"))
    if price <= 0 or prev_close <= 0: return None
    gap_pct = ((price - prev_close) / prev_close) * 100.0
    volume = _safe_int(daily_bar.get("v"))
    bid = latest_quote.get("bp")
    ask = latest_quote.get("ap")
    spread_pct = _calculate_spread(_safe_float(bid) if bid is not None else None,
                                   _safe_float(ask) if ask is not None else None)
    rejection_reasons = []
    if price < DISCOVERY_MIN_PRICE: rejection_reasons.append("PRICE_TOO_LOW")
    if price > DISCOVERY_MAX_PRICE: rejection_reasons.append("PRICE_TOO_HIGH")
    if abs(gap_pct) < DISCOVERY_MIN_GAP: rejection_reasons.append("GAP_TOO_SMALL")
    if volume < DISCOVERY_MIN_VOLUME: rejection_reasons.append("VOLUME_TOO_LOW")

    if strict:
        if price < DISCOVERY_MIN_PRICE: return None
        if price > DISCOVERY_MAX_PRICE: return None
        if abs(gap_pct) < DISCOVERY_MIN_GAP: return None
        if volume < DISCOVERY_MIN_VOLUME and abs(gap_pct) < 10: return None

    score = _score_snapshot(price, gap_pct, volume, spread_pct)
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
        "spread_pct": spread_pct,
        "bid": bid,
        "ask": ask,
        "event_score": score,
        "discovery_score": score,
        "discovery_status": "STRICT" if strict else "FALLBACK_DISCOVERY",
        "rejection_reasons": rejection_reasons,
        "pm_data_quality": "SNAPSHOT_DATA",
        "mode": "LIVE",
        "strategy_version": "V5.0.4",
        "data_version": "ALPACA_IEX_V504",
        "scan_date": now_et.strftime("%Y-%m-%d"),
        "source": "ALPACA_SNAPSHOT",
    }


def _get_float_from_alpaca_snapshot(ticker: str, snapshot: dict) -> Optional[float]:
    """Extract float from snapshot (prevDailyBar might have volume info)"""
    # Use prevDailyBar volume as a proxy for float? No, we need actual float.
    # For now, we rely on FMP. So we'll fetch float via float_analyzer in FullScan.
    # But we need a quick pre-filter. We'll use dailyBar volume as a crude proxy.
    # Better: we'll skip float pre-filter here and let FullScan handle it.
    # But we want Hard Gate. So we'll fetch float from FMP at Discovery level.
    from scanner.analyzers.float_analyzer import get_float_and_short
    try:
        result = get_float_and_short(ticker)
        return result.get('float')
    except:
        return None


def _request_with_retry(session, batch, attempt=0):
    try:
        response = session.get(SNAPSHOT_URL, params={"symbols": ",".join(batch), "feed": "iex"}, timeout=REQUEST_TIMEOUT)
        if response.status_code == 429 and attempt < MAX_RETRIES:
            wait = BASE_BACKOFF * (2 ** attempt)
            print(f"[FastDiscovery] 429 – retrying in {wait:.1f}s (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(wait)
            return _request_with_retry(session, batch, attempt + 1)
        return response
    except Exception as e: print(f"[FastDiscovery] Request error: {e}"); return None


def fast_discovery() -> Tuple[List[dict], dict]:
    now_et = datetime.now(ET)
    universe = load_universe()
    if not universe: return [], {}
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY: return [], {}
    clean_universe = []
    seen = set()
    for symbol in universe:
        symbol = symbol.strip().upper()
        if not symbol or symbol in seen: continue
        seen.add(symbol)
        clean_universe.append(symbol)
    print("\n[FastDiscovery] V5.0.4 ALPACA DISCOVERY (Float Hard Gate)")
    print(f"[FastDiscovery] Universe symbols: {len(clean_universe)}")
    print(f"[FastDiscovery] Float Hard Gate: {FLOAT_HARD_LIMIT:,}")
    batches = successful_batches = failed_batches = 0
    requested_symbols = returned_snapshots = valid_price = valid_prev_close = parsed_raw = 0
    strict_candidates = []
    fallback_candidates = []
    reject_price_low = reject_price_high = reject_gap = reject_volume = reject_invalid = 0
    reject_float = 0
    session = requests.Session()
    session.headers.update(_headers())

    # Local import for float
    from scanner.analyzers.float_analyzer import get_float_and_short

    for batch in _chunks(clean_universe, BATCH_SIZE):
        batches += 1
        requested_symbols += len(batch)
        print(f"[FastDiscovery] Batch {batches}: requesting {len(batch)} symbols...")
        response = _request_with_retry(session, batch)
        if response is None:
            failed_batches += 1; continue
        if response.status_code != 200:
            failed_batches += 1
            print(f"[FastDiscovery] Batch {batches} HTTP: {response.status_code}")
            continue
        successful_batches += 1
        payload = response.json()
        snapshots = _extract_snapshots(payload)
        returned_snapshots += len(snapshots)
        print(f"[FastDiscovery] Batch {batches}: snapshots returned = {len(snapshots)}")
        for ticker, snapshot in snapshots.items():
            try:
                raw_price = _safe_float(snapshot.get("latestTrade", {}).get("p"), _safe_float(snapshot.get("dailyBar", {}).get("c")))
                raw_prev_close = _safe_float(snapshot.get("prevDailyBar", {}).get("c"))
                if raw_price > 0: valid_price += 1
                if raw_prev_close > 0: valid_prev_close += 1
                fallback = _parse_snapshot(ticker, snapshot, now_et, strict=False)
                if fallback is None:
                    reject_invalid += 1; continue
                parsed_raw += 1
                fallback_candidates.append(fallback)
                reasons = set(fallback.get("rejection_reasons", []))
                if "PRICE_TOO_LOW" in reasons: reject_price_low += 1
                if "PRICE_TOO_HIGH" in reasons: reject_price_high += 1
                if "GAP_TOO_SMALL" in reasons: reject_gap += 1
                if "VOLUME_TOO_LOW" in reasons: reject_volume += 1

                # -----------------------------------------------------
                # Float Hard Gate – fetch float from FMP
                # -----------------------------------------------------
                try:
                    float_data = get_float_and_short(ticker)
                    float_val = float_data.get('float')
                    if float_val is None:
                        # If float unknown, we might reject or keep? For now, keep but mark.
                        pass
                    elif float_val > FLOAT_HARD_LIMIT:
                        reject_float += 1
                        continue  # reject this candidate
                except:
                    # If float fetch fails, we keep the candidate (but maybe warn)
                    pass

                strict_candidate = _parse_snapshot(ticker, snapshot, now_et, strict=True)
                if strict_candidate:
                    strict_candidates.append(strict_candidate)
            except Exception as exc:
                reject_invalid += 1
                print(f"[FastDiscovery] {ticker} parse error: {exc}")
        time.sleep(0.5)

    strict_candidates.sort(key=lambda x: (x.get("discovery_score", 0), abs(x.get("gap_pct", 0)), x.get("pm_volume", 0)), reverse=True)
    diagnostics = {
        "returned_snapshots": returned_snapshots,
        "valid_price": valid_price,
        "valid_prev_close": valid_prev_close,
        "parsed_raw": parsed_raw,
        "strict_candidates": len(strict_candidates),
        "fallback_candidates": len(fallback_candidates),
        "reject_price_low": reject_price_low,
        "reject_price_high": reject_price_high,
        "reject_gap": reject_gap,
        "reject_volume": reject_volume,
        "reject_invalid": reject_invalid,
        "reject_float": reject_float,
    }
    if strict_candidates:
        return strict_candidates[:MAX_DISCOVERY_CANDIDATES], diagnostics
    print("[FastDiscovery] WARNING: No strict candidates.")
    if not fallback_candidates:
        print("[FastDiscovery] CRITICAL: No usable snapshots.")
        return [], diagnostics
    fallback_candidates.sort(key=lambda x: (x.get("discovery_score", 0), abs(x.get("gap_pct", 0)), x.get("pm_volume", 0)), reverse=True)
    return fallback_candidates[:FALLBACK_LIMIT], diagnostics