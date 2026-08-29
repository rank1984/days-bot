"""
DAYS-BOT V3.0 – Premarket Scanner
==================================

Experiment rules:

1. Discovery is the hard candidate generator.
2. PM data comes from Alpaca IEX feed.
3. PM bars are QUALITY metadata, not a hard gate.
4. RVOL is informational only.
5. Catalyst is informational only.
6. PM volume threshold is informational only.
7. Signed PM distance is preserved.
8. Every candidate receives experiment metadata.
9. No live trading is executed here.
"""

from datetime import datetime, time
from typing import List
import pytz

from alpaca_trade_api.rest import REST

from scanner.universe import load_universe
from utils.config import (
    ALPACA_API_KEY,
    ALPACA_BASE_URL,
    ALPACA_SECRET_KEY,
    BOT_VERSION,
    DATA_VERSION,
    DISCOVERY_MAX_GAP,
    DISCOVERY_MAX_PRICE,
    DISCOVERY_MIN_GAP,
    DISCOVERY_MIN_PRICE,
    EXPERIMENT_MODE,
    STRATEGY_VERSION,
    VALIDATION_MAX_PM_DIST,
    VALIDATION_MAX_SPREAD,
    VALIDATION_MIN_PM_BARS,
    VALIDATION_MIN_PM_VOLUME_ABS,
    VALIDATION_MIN_VWAP_DIST,
)

ET = pytz.timezone("America/New_York")


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def scan_premarket(target_date_str: str = None) -> List[dict]:
    """
    Main V3.0 premarket scanner.

    Discovery:
        Price
        Gap
        Spread

    PM:
        IEX minute bars
        PM volume
        PM bars count
        PM high
        PM VWAP
        signed distance
        PM data quality

    RVOL/Catalyst:
        Informational only.
    """

    now_et = datetime.now(ET)

    if target_date_str is None:
        target_date_str = now_et.strftime("%Y-%m-%d")

    print()
    print("=" * 70)
    print(
        f"[Premarket] {BOT_VERSION} "
        f"| mode={EXPERIMENT_MODE} "
        f"| strategy={STRATEGY_VERSION} "
        f"| data={DATA_VERSION}"
    )
    print(
        f"[Premarket] Date={target_date_str} "
        f"| Now ET={now_et.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("=" * 70)

    # ------------------------------------------------------------
    # API
    # ------------------------------------------------------------

    api = REST(
        ALPACA_API_KEY,
        ALPACA_SECRET_KEY,
        ALPACA_BASE_URL,
        api_version="v2",
    )

    # ------------------------------------------------------------
    # UNIVERSE
    # ------------------------------------------------------------

    universe = load_universe()

    if not universe:
        print("[Premarket] ❌ Universe is empty.")
        return []

    print(f"[Premarket] Universe: {len(universe):,}")

    # ------------------------------------------------------------
    # DISCOVERY STATS
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # DISCOVERY
    # ------------------------------------------------------------

    batch_size = 100

    for i in range(0, len(universe), batch_size):
        batch = universe[i : i + batch_size]

        symbols = []
        for item in batch:
            if isinstance(item, dict):
                symbol = item.get("symbol")
            else:
                symbol = str(item)

            if symbol:
                symbols.append(symbol)

        if not symbols:
            continue

        try:
            snapshots = api.get_snapshots(symbols)
        except Exception as e:
            print(f"[Discovery] Batch error {i}-{i + len(symbols)}: {e}")
            continue

        for ticker in symbols:
            try:
                snap = snapshots.get(ticker)

                if not snap:
                    stats["no_snapshot"] += 1
                    continue

                latest_trade = getattr(snap, "latest_trade", None)
                prev_bar = getattr(snap, "prev_daily_bar", None)

                if not latest_trade:
                    stats["no_trade"] += 1
                    continue

                if not prev_bar:
                    stats["no_bar"] += 1
                    continue

                price = _safe_float(getattr(latest_trade, "price", None))
                prev_close = _safe_float(getattr(prev_bar, "close", None))

                if price <= 0 or prev_close <= 0:
                    stats["no_trade"] += 1
                    continue

                # PRICE
                if (
                    price < DISCOVERY_MIN_PRICE
                    or price > DISCOVERY_MAX_PRICE
                ):
                    stats["price_fail"] += 1
                    continue

                stats["price_pass"] += 1

                # GAP
                gap_pct = ((price - prev_close) / prev_close) * 100.0

                if (
                    gap_pct < DISCOVERY_MIN_GAP
                    or gap_pct > DISCOVERY_MAX_GAP
                ):
                    stats["gap_fail"] += 1
                    continue

                stats["gap_pass"] += 1

                # SPREAD
                latest_quote = getattr(snap, "latest_quote", None)
                bid = _safe_float(getattr(latest_quote, "bid_price", None))
                ask = _safe_float(getattr(latest_quote, "ask_price", None))

                if bid > 0 and ask > bid:
                    spread_pct = ((ask - bid) / price) * 100.0
                else:
                    spread_pct = 0.0

                if spread_pct > VALIDATION_MAX_SPREAD:
                    stats["spread_fail"] += 1
                    continue

                stats["spread_pass"] += 1

                # DISCOVERY PASS
                stats["discovery_pass"] += 1

                discovery_candidates.append(
                    {
                        "ticker": ticker,
                        "price": price,
                        "prev_close": prev_close,
                        "gap_pct": gap_pct,
                        "spread_pct": spread_pct,
                        "mode": EXPERIMENT_MODE,
                        "strategy_version": STRATEGY_VERSION,
                        "data_version": DATA_VERSION,
                    }
                )

            except Exception as e:
                print(f"[Discovery] {ticker} processing error: {e}")
                continue

        print(
            f"[Discovery] Processed "
            f"{min(i + batch_size, len(universe)):,}"
            f"/{len(universe):,}"
        )

    # ------------------------------------------------------------
    # DISCOVERY REPORT
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("📊 DISCOVERY NEAR-MISS REPORT")
    print("=" * 70)
    print(f"Universe:       {stats['total']:,}")
    print(f"No snapshot:    {stats['no_snapshot']:,}")
    print(f"No trade:       {stats['no_trade']:,}")
    print(f"No daily bar:   {stats['no_bar']:,}")
    print(
        f"Price pass:     {stats['price_pass']:,} "
        f"| fail: {stats['price_fail']:,}"
    )
    print(
        f"Gap pass:       {stats['gap_pass']:,} "
        f"| fail: {stats['gap_fail']:,}"
    )
    print(
        f"Spread pass:    {stats['spread_pass']:,} "
        f"| fail: {stats['spread_fail']:,}"
    )
    print(f"Discovery pass: {stats['discovery_pass']:,}")
    print("=" * 70)

    if not discovery_candidates:
        return []

    # ------------------------------------------------------------
    # PM VALIDATION
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("📌 PM DATA QUALITY – IEX")
    print("=" * 70)

    validated_candidates = []

    pm_start = ET.localize(
        datetime.combine(now_et.date(), time(4, 0))
    )

    pm_end = min(
        now_et,
        ET.localize(
            datetime.combine(now_et.date(), time(9, 30))
        ),
    )

    for candidate in discovery_candidates:
        ticker = candidate["ticker"]

        try:
            bar_set = api.get_bars(
                ticker,
                "1Min",
                start=pm_start.isoformat(),
                end=pm_end.isoformat(),
                adjustment="raw",
                feed="iex",
            )
            bars = getattr(bar_set, "df", None)

            if bars is None or bars.empty:
                candidate.update(
                    {
                        "pm_volume": 0,
                        "pm_bars": 0,
                        "pm_bars_count": 0,
                        "pm_high": None,
                        "pm_low": None,
                        "pm_vwap": None,
                        "pm_dist_signed": None,
                        "pm_high_dist": None,
                        "pm_data_quality": "NO_DATA",
                        "pm_data_error": "NO_PM_BARS",
                        "rvol": None,
                        "rvol_status": "UNAVAILABLE",
                    }
                )

                print(
                    f"[PM RESULT] {ticker}"
                    f" | Bars=0"
                    f" | Vol=0"
                    f" | quality=NO_DATA"
                )
                continue

            pm_bars_count = len(bars)
            pm_volume = int(bars["volume"].sum())
            pm_high = float(bars["high"].max())
            pm_low = float(bars["low"].min())
            total_volume = bars["volume"].sum()

            if total_volume > 0:
                pm_vwap = float(
                    (bars["close"] * bars["volume"]).sum() / total_volume
                )
            else:
                pm_vwap = float(bars["close"].mean())

            current_price = candidate["price"]

            if pm_high > 0:
                pm_dist_signed = (
                    (current_price - pm_high) / pm_high
                ) * 100.0
            else:
                pm_dist_signed = None

            pm_high_dist = (
                max(0.0, pm_dist_signed)
                if pm_dist_signed is not None
                else None
            )

            if (
                pm_bars_count >= VALIDATION_MIN_PM_BARS
                and pm_volume >= VALIDATION_MIN_PM_VOLUME_ABS
            ):
                pm_data_quality = "GOOD_DATA"
            elif pm_bars_count > 0:
                pm_data_quality = "LOW_DATA"
            else:
                pm_data_quality = "NO_DATA"

            rvol = None
            rvol_status = "UNAVAILABLE"

            candidate.update(
                {
                    "pm_volume": pm_volume,
                    "pm_bars": pm_bars_count,
                    "pm_bars_count": pm_bars_count,
                    "pm_high": pm_high,
                    "pm_low": pm_low,
                    "pm_vwap": pm_vwap,
                    "pm_dist_signed": pm_dist_signed,
                    "pm_high_dist": pm_high_dist,
                    "pm_data_quality": pm_data_quality,
                    "pm_data_error": None,
                    "rvol": rvol,
                    "rvol_status": rvol_status,
                    "mode": EXPERIMENT_MODE,
                    "strategy_version": STRATEGY_VERSION,
                    "data_version": DATA_VERSION,
                }
            )

            print(
                f"[PM RESULT] {ticker}"
                f" | Bars={pm_bars_count}"
                f" | Vol={pm_volume:,}"
                f" | High={pm_high:.2f}"
                f" | VWAP={pm_vwap:.2f}"
                f" | DistSigned={pm_dist_signed:.2f}%"
                f" | quality={pm_data_quality}"
            )

            if pm_dist_signed is None or pm_dist_signed < -VALIDATION_MAX_PM_DIST:
                continue

            if pm_vwap <= 0:
                continue

            vwap_required_price = pm_vwap * (
                1.0 + VALIDATION_MIN_VWAP_DIST
            )

            if current_price < vwap_required_price:
                continue

            event_score = 0.0

            event_score += min(
                max(candidate["gap_pct"], 0.0) * 2.0, 30.0
            )

            if pm_volume > 0:
                event_score += min(
                    (pm_volume / 100_000.0) * 20.0, 30.0
                )

            if pm_dist_signed >= 0:
                event_score += 25.0
            elif pm_dist_signed >= -2.0:
                event_score += 15.0
            elif pm_dist_signed >= -5.0:
                event_score += 5.0

            if candidate["spread_pct"] <= 1.0:
                event_score += 10.0

            event_score = round(
                min(100.0, max(0.0, event_score)), 1
            )

            candidate["event_score"] = event_score

            if event_score >= 70:
                grade = "A"
            elif event_score >= 55:
                grade = "B"
            elif event_score >= 40:
                grade = "C"
            else:
                grade = "WATCH"

            candidate["grade"] = grade
            candidate["state"] = "WATCH"

            validated_candidates.append(candidate)

        except Exception as e:
            print(f"[PM ERROR] {ticker}: {e}")
            continue

    print()
    print("=" * 70)
    print("📊 PREMARKET SCAN V3.0 – EXPERIMENT")
    print("=" * 70)
    print(f"Discovery candidates: {len(discovery_candidates):,}")
    print(f"PM validated:         {len(validated_candidates):,}")

    good_data = sum(
        1
        for c in validated_candidates
        if c.get("pm_data_quality") == "GOOD_DATA"
    )
    low_data = sum(
        1
        for c in validated_candidates
        if c.get("pm_data_quality") == "LOW_DATA"
    )

    print(f"GOOD_DATA: {good_data:,} | LOW_DATA: {low_data:,}")
    print("RVOL: INFORMATIONAL / UNAVAILABLE")
    print("Catalyst: INFORMATIONAL / NOT USED AS HARD GATE")
    print(f"FINAL: {len(validated_candidates):,}")
    print("=" * 70)

    validated_candidates.sort(
        key=lambda x: (
            x.get("event_score", 0.0),
            x.get("gap_pct", 0.0),
        ),
        reverse=True,
    )

    return validated_candidates[:20]
