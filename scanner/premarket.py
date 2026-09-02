"""
DAYS-BOT V4.1 – Premarket Discovery

Uses Alpaca Market Data API instead of yfinance.

Flow:
    Universe
       ↓
    Alpaca snapshots
       ↓
    Fast candidates
       ↓
    Alpaca 1-minute bars
       ↓
    Premarket metrics
       ↓
    Top 40

Missing PM data does NOT destroy the entire scan.
"""

from datetime import datetime, timedelta, time
from typing import List, Dict

import requests
import pytz

from scanner.universe import load_universe
from scanner.discovery_fast import fast_discovery
from utils.config import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_DATA_URL,
)


ET = pytz.timezone("America/New_York")

PM_START = time(4, 0)
PM_END = time(9, 30)

BAR_BATCH_SIZE = 100

SESSION = requests.Session()

SESSION.headers.update({
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "User-Agent": "DAYS-BOT/4.1",
})


# ============================================================
# HELPERS
# ============================================================

def _chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


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


def _is_in_pm_window(now_et):
    return (
        PM_START <= now_et.time() < PM_END
    )


def _get_previous_trading_day(
    target_date_str: str
) -> str:

    target = datetime.strptime(
        target_date_str,
        "%Y-%m-%d"
    )

    # Enough for weekends.
    day = target - timedelta(days=1)

    while day.weekday() >= 5:
        day -= timedelta(days=1)

    return day.strftime("%Y-%m-%d")


# ============================================================
# ALPACA BARS
# ============================================================

def _get_bars(
    symbols: List[str],
    start_et: datetime,
    end_et: datetime,
) -> Dict[str, List[dict]]:

    if not symbols:
        return {}

    url = (
        f"{ALPACA_DATA_URL}"
        "/v2/stocks/bars"
    )

    # Alpaca accepts RFC3339 timestamps.
    start_utc = start_et.astimezone(
        pytz.UTC
    ).isoformat()

    end_utc = end_et.astimezone(
        pytz.UTC
    ).isoformat()

    params = {
        "symbols": ",".join(symbols),
        "timeframe": "1Min",
        "start": start_utc,
        "end": end_utc,
        "feed": "iex",
        "limit": 10000,
        "adjustment": "raw",
    }

    try:
        response = SESSION.get(
            url,
            params=params,
            timeout=20
        )

        if response.status_code != 200:
            print(
                "[Premarket] Alpaca bars HTTP "
                f"{response.status_code}: "
                f"{response.text[:200]}"
            )
            return {}

        data = response.json()

        return data.get("bars", {}) or {}

    except Exception as e:
        print(
            f"[Premarket] Bars error: {e}"
        )
        return {}


# ============================================================
# BUILD PM METRICS
# ============================================================

def _build_pm_candidate(
    base: dict,
    bars: List[dict]
) -> dict | None:

    if not bars:
        return None

    clean_bars = []

    for bar in bars:
        try:
            timestamp = bar.get("t")

            if not timestamp:
                continue

            dt = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )

            dt_et = dt.astimezone(ET)

            if not (
                PM_START
                <= dt_et.time()
                < PM_END
            ):
                continue

            close = _safe_float(bar.get("c"))

            high = _safe_float(bar.get("h"))
            low = _safe_float(bar.get("l"))

            volume = _safe_int(bar.get("v"))

            if close is None:
                continue

            clean_bars.append({
                "close": close,
                "high": high if high is not None else close,
                "low": low if low is not None else close,
                "volume": volume,
            })

        except Exception:
            continue

    if not clean_bars:
        return None

    price = clean_bars[-1]["close"]

    pm_volume = sum(
        x["volume"]
        for x in clean_bars
    )

    pm_high = max(
        x["high"]
        for x in clean_bars
    )

    pm_low = min(
        x["low"]
        for x in clean_bars
    )

    if pm_volume > 0:
        pm_vwap = (
            sum(
                x["close"] * x["volume"]
                for x in clean_bars
            )
            / pm_volume
        )
    else:
        pm_vwap = price

    prev_close = base.get(
        "prev_close"
    )

    if not prev_close or prev_close <= 0:
        return None

    gap_pct = (
        (price - prev_close)
        / prev_close
    ) * 100.0

    pm_dist_signed = (
        (price - pm_high)
        / pm_high
        * 100.0
        if pm_high > 0
        else 0.0
    )

    # --------------------------------------------------------
    # Better PM score
    # --------------------------------------------------------

    score = 0.0

    # Gap
    score += min(
        max(gap_pct, 0) * 2.0,
        30.0
    )

    # Volume
    score += min(
        pm_volume / 100_000.0 * 4.0,
        25.0
    )

    # Near PM high
    if pm_high > 0:
        distance = abs(
            (price - pm_high)
            / pm_high
            * 100.0
        )

        if distance <= 0.5:
            score += 25
        elif distance <= 1.0:
            score += 20
        elif distance <= 2.0:
            score += 15
        elif distance <= 5.0:
            score += 8

    # Price above PM VWAP
    if pm_vwap > 0:
        if price >= pm_vwap:
            score += 15
        elif price >= pm_vwap * 0.99:
            score += 7

    score = round(
        min(max(score, 0), 100),
        1
    )

    result = dict(base)

    result.update({
        "price": price,
        "prev_close": prev_close,
        "gap_pct": round(gap_pct, 2),

        "pm_volume": pm_volume,
        "pm_bars": len(clean_bars),

        "pm_high": pm_high,
        "pm_low": pm_low,
        "pm_vwap": pm_vwap,

        "pm_dist_signed": round(
            pm_dist_signed,
            3
        ),

        "event_score": score,

        "pm_data_quality": (
            "GOOD_DATA"
            if len(clean_bars) >= 5
            else "LOW_DATA"
        ),

        "market_data_source": "ALPACA_IEX",

        "strategy_version": "V4.1",
        "data_version": "ALPACA_IEX_PM_V41",

        "source": "PM",
    })

    return result


# ============================================================
# PREMARKET SCAN
# ============================================================

def scan_premarket(
    target_date_str: str = None,
    manual: bool = False
) -> List[dict]:

    now_et = datetime.now(ET)

    if not target_date_str:
        target_date_str = now_et.strftime(
            "%Y-%m-%d"
        )

    in_pm = _is_in_pm_window(now_et)

    print(
        f"[Discovery] Premarket scan "
        f"{target_date_str} | "
        f"ET: {now_et.strftime('%H:%M:%S')} | "
        f"PM window: {in_pm}"
    )

    # --------------------------------------------------------
    # Outside PM
    # --------------------------------------------------------

    if not in_pm:

        print(
            "[Discovery] Outside PM window "
            "– using Alpaca fast discovery."
        )

        candidates = fast_discovery()

        for c in candidates:
            c["mode"] = (
                "MANUAL_REPLAY"
                if manual
                else "LIVE"
            )

        return candidates

    # --------------------------------------------------------
    # Stage 1
    # --------------------------------------------------------

    universe = load_universe(
        max_symbols=300
    )

    if not universe:
        return []

    # Fast discovery gets the relevant 30.
    discovery_candidates = fast_discovery(
        universe
    )

    if not discovery_candidates:
        print(
            "[Discovery] No fast candidates."
        )
        return []

    # --------------------------------------------------------
    # Stage 2
    # --------------------------------------------------------

    # Don't hit PM bars for 300 symbols.
    # Only top 40.
    discovery_candidates = (
        discovery_candidates[:40]
    )

    start_et = datetime.strptime(
        target_date_str + " 04:00:00",
        "%Y-%m-%d %H:%M:%S"
    )

    end_et = datetime.strptime(
        target_date_str + " 09:30:00",
        "%Y-%m-%d %H:%M:%S"
    )

    start_et = ET.localize(start_et)
    end_et = ET.localize(end_et)

    symbols = [
        c["ticker"]
        for c in discovery_candidates
    ]

    bars_by_symbol = {}

    for batch in _chunked(
        symbols,
        BAR_BATCH_SIZE
    ):

        batch_bars = _get_bars(
            batch,
            start_et,
            end_et
        )

        bars_by_symbol.update(
            batch_bars
        )

    # --------------------------------------------------------
    # Build candidates
    # --------------------------------------------------------

    candidates = []

    for base in discovery_candidates:

        ticker = base["ticker"]

        bars = bars_by_symbol.get(
            ticker,
            []
        )

        candidate = _build_pm_candidate(
            base,
            bars
        )

        # IMPORTANT:
        # Missing PM data does NOT kill
        # the candidate.
        if candidate is None:

            candidate = dict(base)

            candidate.update({
                "pm_data_quality":
                    "UNKNOWN",

                "pm_bars": 0,

                "pm_high":
                    base.get("price"),

                "pm_low":
                    base.get("price"),

                "pm_vwap":
                    base.get("price"),

                "pm_dist_signed": 0.0,

                "source":
                    "PM_FALLBACK",

                "data_warning":
                    "Premarket bars unavailable",
            })

        candidate["mode"] = (
            "MANUAL_REPLAY"
            if manual
            else "LIVE"
        )

        candidates.append(candidate)

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x: (
            x.get("event_score", 0),
            x.get("gap_pct", 0),
            x.get("pm_volume", 0),
        ),
        reverse=True
    )

    print(
        f"[Discovery] Candidates found: "
        f"{len(candidates)}"
    )

    return candidates[:40]