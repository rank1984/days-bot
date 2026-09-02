"""
DAYS-BOT V4.1 – Premarket Discovery

Primary market-data source:
Alpaca Market Data / IEX.

No yfinance.
"""

from datetime import datetime, time
from typing import Dict, List

import pytz
import requests

from scanner.universe import load_universe
from scanner.discovery_fast import fast_discovery
from utils.config import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_DATA_URL,
    DISCOVERY_MIN_GAP,
    MAX_DISCOVERY_CANDIDATES,
)


ET = pytz.timezone("America/New_York")
UTC = pytz.utc

PM_START = time(4, 0)
PM_END = time(9, 30)

BATCH_SIZE = 40


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


def _parse_bars(
    ticker: str,
    bars: list,
    prev_close: float,
    target_date: str,
    manual: bool,
) -> dict | None:

    if not bars:
        return None

    pm_bars = []

    for bar in bars:

        try:
            ts = pd_timestamp(bar.get("t"))

            ts_et = ts.astimezone(ET)

            if ts_et.date().isoformat() != target_date:
                continue

            if not (
                PM_START
                <= ts_et.time()
                < PM_END
            ):
                continue

            pm_bars.append(bar)

        except Exception:
            continue

    if not pm_bars:
        return None

    closes = [
        _safe_float(x.get("c"))
        for x in pm_bars
    ]

    highs = [
        _safe_float(x.get("h"))
        for x in pm_bars
    ]

    lows = [
        _safe_float(x.get("l"))
        for x in pm_bars
    ]

    volumes = [
        _safe_int(x.get("v"))
        for x in pm_bars
    ]

    closes = [x for x in closes if x > 0]
    highs = [x for x in highs if x > 0]
    lows = [x for x in lows if x > 0]

    if not closes or prev_close <= 0:
        return None

    price = closes[-1]
    pm_high = max(highs) if highs else price
    pm_low = min(lows) if lows else price
    pm_volume = sum(volumes)

    if pm_volume > 0:
        weighted = sum(
            float(bar.get("c", 0))
            * _safe_int(bar.get("v"))
            for bar in pm_bars
        )
        pm_vwap = weighted / pm_volume
    else:
        pm_vwap = price

    gap_pct = (
        (price - prev_close)
        / prev_close
        * 100.0
    )

    pm_dist_signed = (
        (price - pm_high)
        / pm_high
        * 100.0
        if pm_high > 0
        else 0.0
    )

    score = 0.0

    score += min(
        max(gap_pct, 0) * 2,
        30,
    )

    score += min(
        pm_volume / 100_000 * 15,
        30,
    )

    if pm_high > 0:
        if price >= pm_high * 0.995:
            score += 25
        elif price >= pm_high * 0.98:
            score += 18
        elif price >= pm_high * 0.95:
            score += 10

    if pm_volume >= 500_000:
        score += 10
    elif pm_volume >= 100_000:
        score += 5

    return {
        "ticker": ticker,
        "price": price,
        "prev_close": prev_close,
        "gap_pct": round(gap_pct, 2),
        "pm_volume": pm_volume,
        "pm_bars": len(pm_bars),
        "pm_high": pm_high,
        "pm_low": pm_low,
        "pm_vwap": pm_vwap,
        "pm_dist_signed": round(
            pm_dist_signed,
            3,
        ),
        "spread_pct": None,
        "event_score": round(
            min(100, max(0, score)),
            1,
        ),
        "pm_data_quality": (
            "GOOD_DATA"
            if len(pm_bars) >= 5
            else "LOW_DATA"
        ),
        "mode": (
            "MANUAL_REPLAY"
            if manual
            else "LIVE"
        ),
        "strategy_version": "V4.1",
        "data_version": "ALPACA_IEX_V41",
        "scan_date": target_date,
        "source": "ALPACA_PREMARKET",
    }


def pd_timestamp(value):
    """
    Convert Alpaca ISO timestamp to timezone-aware datetime.
    """

    if isinstance(value, datetime):
        ts = value
    else:
        raw = str(value)

        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"

        ts = datetime.fromisoformat(raw)

    if ts.tzinfo is None:
        ts = UTC.localize(ts)

    return ts


def _get_previous_close(
    session: requests.Session,
    ticker: str,
) -> float:

    url = (
        f"{ALPACA_DATA_URL}/v2/stocks/"
        f"{ticker}/bars"
    )

    try:
        response = session.get(
            url,
            params={
                "timeframe": "1Day",
                "limit": 5,
                "feed": "iex",
            },
            timeout=10,
        )

        if response.status_code != 200:
            return 0.0

        data = response.json()

        bars = data.get("bars", [])

        if len(bars) < 1:
            return 0.0

        # Last regular daily bar is normally previous close
        return _safe_float(
            bars[-1].get("c")
        )

    except Exception:
        return 0.0


def scan_premarket(
    target_date_str: str = None,
    manual: bool = False,
) -> List[dict]:

    now_et = datetime.now(ET)

    if not target_date_str:
        target_date_str = now_et.strftime(
            "%Y-%m-%d"
        )

    in_pm = (
        PM_START
        <= now_et.time()
        < PM_END
    )

    print(
        f"[Discovery] Premarket scan for "
        f"{target_date_str} | ET: "
        f"{now_et.strftime('%H:%M:%S')} | "
        f"PM window: {in_pm}"
    )

    # Outside PM -> use fast discovery.
    if not in_pm:
        print(
            "[Discovery] Outside PM window – "
            "using Alpaca fast discovery."
        )
        return fast_discovery()

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        print(
            "[Discovery] Missing Alpaca credentials."
        )
        return fast_discovery()

    universe = load_universe()

    if not universe:
        return fast_discovery()

    session = requests.Session()
    session.headers.update(_headers())

    candidates = []

    # --------------------------------------------------------
    # First obtain previous closes.
    # Limited number to avoid unnecessary API load.
    # --------------------------------------------------------

    discovery_base = universe[:300]

    prev_closes = {}

    for ticker in discovery_base:

        prev = _get_previous_close(
            session,
            ticker,
        )

        if prev > 0:
            prev_closes[ticker] = prev

    # --------------------------------------------------------
    # Get 1-minute bars.
    # --------------------------------------------------------

    bars_url = (
        f"{ALPACA_DATA_URL}/v2/stocks/bars"
    )

    for batch in _chunks(
        list(prev_closes.keys()),
        BATCH_SIZE,
    ):

        try:

            start_et = ET.localize(
                datetime.strptime(
                    f"{target_date_str} 04:00:00",
                    "%Y-%m-%d %H:%M:%S",
                )
            )

            end_et = ET.localize(
                datetime.strptime(
                    f"{target_date_str} 09:30:00",
                    "%Y-%m-%d %H:%M:%S",
                )
            )

            response = session.get(
                bars_url,
                params={
                    "symbols": ",".join(batch),
                    "timeframe": "1Min",
                    "start": start_et.astimezone(
                        UTC
                    ).isoformat(),
                    "end": end_et.astimezone(
                        UTC
                    ).isoformat(),
                    "limit": 10000,
                    "feed": "iex",
                    "adjustment": "raw",
                },
                timeout=30,
            )

            if response.status_code != 200:
                print(
                    "[Discovery] PM bars HTTP "
                    f"{response.status_code}"
                )
                continue

            payload = response.json()

            bars_by_symbol = payload.get(
                "bars",
                {},
            )

            for ticker in batch:

                try:
                    bars = bars_by_symbol.get(
                        ticker,
                        [],
                    )

                    candidate = _parse_bars(
                        ticker=ticker,
                        bars=bars,
                        prev_close=prev_closes.get(
                            ticker,
                            0.0,
                        ),
                        target_date=target_date_str,
                        manual=manual,
                    )

                    if not candidate:
                        continue

                    # Do not eliminate candidates only because
                    # PM volume is weak. Discovery is permissive.
                    if (
                        abs(candidate["gap_pct"])
                        < DISCOVERY_MIN_GAP
                    ):
                        continue

                    candidates.append(candidate)

                except Exception as e:
                    print(
                        f"[Discovery] {ticker} "
                        f"parse error: {e}"
                    )

        except Exception as e:
            print(
                f"[Discovery] PM request error: {e}"
            )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if not candidates:
        print(
            "[Discovery] No PM candidates – "
            "using Alpaca fast discovery fallback."
        )

        fallback = fast_discovery()

        # Mark source clearly.
        for candidate in fallback:
            candidate["source"] = (
                "ALPACA_FAST_FALLBACK"
            )
            candidate["pm_data_quality"] = (
                "UNKNOWN_PM_DATA"
            )

        return fallback

    candidates.sort(
        key=lambda x: (
            x.get("event_score", 0),
            x.get("gap_pct", 0),
            x.get("pm_volume", 0),
        ),
        reverse=True,
    )

    print(
        f"[Discovery] Candidates found: "
        f"{len(candidates)}"
    )

    return candidates[
        :MAX_DISCOVERY_CANDIDATES
    ]
