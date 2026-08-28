import pytz
import requests
from datetime import datetime, time
from alpaca_trade_api.rest import REST

from utils.config import (
    BOT_VERSION,
    STRATEGY_VERSION,
    EXPERIMENT_MODE,
    DATA_VERSION,
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_BASE_URL,
    FINNHUB_API_KEY,
    DISCOVERY_MIN_PRICE,
    DISCOVERY_MAX_PRICE,
    DISCOVERY_MIN_GAP,
    DISCOVERY_MAX_GAP,
    VALIDATION_MAX_SPREAD,
    VALIDATION_MIN_PM_VOLUME_ABS,
    VALIDATION_MIN_PM_BARS,
)
from scanner.universe import load_universe
from scanner.pm_engine import fetch_pm_data

ET = pytz.timezone("America/New_York")


def get_catalyst_from_finnhub(ticker: str, api_key: str) -> dict:
    """Fetches company news catalyst from Finnhub (Soft classification for V2.14)."""
    if not api_key:
        return {"score": None, "status": "UNAVAILABLE", "headline": None}
    try:
        today_str = datetime.now(ET).strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={today_str}&to={today_str}&token={api_key}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data and isinstance(data, list) and len(data) > 0:
                headline = data[0].get("headline", "")
                return {"score": 50, "status": "AVAILABLE", "headline": headline}
    except Exception:
        pass
    return {"score": None, "status": "UNAVAILABLE", "headline": None}


def scan_premarket(target_date_str: str) -> list:
    now_et = datetime.now(ET)

    # Hard Stop 1: Too early (< 08:00 ET)
    if now_et.time() < time(8, 0):
        print(f"[Premarket] {BOT_VERSION} – Too early for IEX PM experiment: {now_et.strftime('%H:%M:%S')} ET")
        return []

    # Hard Stop 2: Market Open (>= 09:30 ET)
    if now_et.time() >= time(9, 30):
        print(f"[Premarket] {BOT_VERSION} – Market already open: {now_et.strftime('%H:%M:%S')} ET")
        return []

    print(f"\n[Premarket] {BOT_VERSION} ({EXPERIMENT_MODE}) – Executing 08:00–09:30 ET Discovery & Validation...")
    api = REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version="v2")
    universe = load_universe()

    stats = {
        "total": len(universe),
        "no_snapshot": 0,
        "no_trade": 0,
        "no_bar": 0,
        "price_pass": 0,
        "price_fail": 0,
        "gap_pass": 0,
        "gap_fail": 0,
        "spread_pass": 0,
        "spread_fail": 0,
        "discovery_pass": 0,
    }

    discovery_candidates = []
    batch_size = 100

    for i in range(0, len(universe), batch_size):
        batch = universe[i:i + batch_size]
        try:
            snapshots = api.get_snapshots(batch)
        except Exception as e:
            print(f"[Premarket] Error fetching snapshots batch {i}: {e}")
            continue

        for ticker in batch:
            snap = snapshots.get(ticker)
            if not snap:
                stats["no_snapshot"] += 1
                continue

            trade = snap.latest_trade
            prev_bar = snap.prev_daily_bar

            if not trade or not trade.price:
                stats["no_trade"] += 1
                continue
            if not prev_bar or not prev_bar.close:
                stats["no_bar"] += 1
                continue

            price = float(trade.price)
            prev_close = float(prev_bar.close)
            gap_pct = ((price - prev_close) / prev_close) * 100.0

            bid = float(snap.latest_quote.bid_price) if snap.latest_quote and snap.latest_quote.bid_price else 0.0
            ask = float(snap.latest_quote.ask_price) if snap.latest_quote and snap.latest_quote.ask_price else 0.0
            spread_pct = ((ask - bid) / price) * 100.0 if price > 0 and ask > bid else 0.0

            if price < DISCOVERY_MIN_PRICE or price > DISCOVERY_MAX_PRICE:
                stats["price_fail"] += 1
                continue
            stats["price_pass"] += 1

            if gap_pct < DISCOVERY_MIN_GAP or gap_pct > DISCOVERY_MAX_GAP:
                stats["gap_fail"] += 1
                continue
            stats["gap_pass"] += 1

            if spread_pct > VALIDATION_MAX_SPREAD:
                stats["spread_fail"] += 1
                continue
            stats["spread_pass"] += 1

            stats["discovery_pass"] += 1
            discovery_candidates.append({
                "ticker": ticker,
                "price": price,
                "prev_close": prev_close,
                "gap_pct": gap_pct,
                "spread_pct": spread_pct,
            })

    print("\n" + "=" * 60)
    print(f"📊 DISCOVERY NEAR-MISS REPORT ({BOT_VERSION})")
    print("=" * 60)
    print(f"Universe: {stats['total']:,}")
    print(f"Price pass: {stats['price_pass']:,} | Price fail: {stats['price_fail']:,}")
    print(f"Gap pass: {stats['gap_pass']:,} | Gap fail: {stats['gap_fail']:,}")
    print(f"Spread pass: {stats['spread_pass']:,} | Spread fail: {stats['spread_fail']:,}")
    print(f"Discovery pass: {stats['discovery_pass']:,}")
    print("=" * 60)

    validated_candidates = []

    for candidate in discovery_candidates:
        ticker = candidate["ticker"]
        price = candidate["price"]

        pm_data = fetch_pm_data(ticker, current_price=price)
        pm_volume = pm_data.get("pm_volume", 0)
        pm_bars_count = pm_data.get("pm_bars_count", 0)

        # Soft Data Quality Tagging (Does NOT drop candidate)
        pm_data_quality = (
            "GOOD_DATA"
            if (pm_volume >= VALIDATION_MIN_PM_VOLUME_ABS and pm_bars_count >= VALIDATION_MIN_PM_BARS)
            else "LOW_DATA"
        )

        catalyst_res = get_catalyst_from_finnhub(ticker, FINNHUB_API_KEY)

        candidate.update({
            "pm_volume": pm_volume,
            "pm_bars": pm_bars_count,
            "pm_vwap": pm_data.get("pm_vwap"),
            "pm_high": pm_data.get("pm_high"),
            "pm_dist_signed": pm_data.get("pm_dist_signed"),
            "pm_high_dist": pm_data.get("pm_high_dist"),
            "pm_data_quality": pm_data_quality,
            "rvol": None,
            "rvol_status": "UNAVAILABLE",
            "catalyst_score": catalyst_res.get("score"),
            "catalyst_status": catalyst_res.get("status", "UNAVAILABLE"),
            "strategy_version": STRATEGY_VERSION,
            "data_version": DATA_VERSION,
            "mode": EXPERIMENT_MODE,
            "event_score": 75,
        })

        validated_candidates.append(candidate)

    return validated_candidates
