"""
DAYS-BOT V4.1 – Swing Engine

1–3 trading day swing analysis.

Uses Alpaca daily bars instead of yfinance.
Failures are local: one bad ticker must not kill the scan.
"""

from datetime import datetime, timedelta
from typing import Dict, List

import requests
import pytz

from utils.config import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_DATA_URL,
)


ET = pytz.timezone("America/New_York")

BARS_URL = (
    f"{ALPACA_DATA_URL}/v2/stocks/bars"
)


def _headers():
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _get_daily_bars(
    session,
    ticker: str,
    limit: int = 80,
) -> List[dict]:

    now = datetime.now(ET)

    start = now - timedelta(
        days=120
    )

    try:
        response = session.get(
            BARS_URL,
            params={
                "symbols": ticker,
                "timeframe": "1Day",
                "start": start.astimezone(
                    pytz.UTC
                ).isoformat(),
                "end": now.astimezone(
                    pytz.UTC
                ).isoformat(),
                "limit": limit,
                "feed": "iex",
                "adjustment": "raw",
            },
            timeout=15,
        )

        if response.status_code != 200:
            return []

        payload = response.json()

        bars = payload.get(
            "bars",
            {},
        )

        return bars.get(
            ticker,
            []
        )

    except Exception:
        return []


def _ema(values, span):
    if not values:
        return 0.0

    alpha = 2.0 / (
        span + 1.0
    )

    ema = values[0]

    for value in values[1:]:
        ema = (
            alpha * value
            + (1 - alpha) * ema
        )

    return ema


def calculate_swing_score(
    candidate: dict,
) -> dict:

    ticker = candidate.get(
        "ticker"
    )

    price = _safe_float(
        candidate.get("price")
    )

    if not ticker or price <= 0:
        return {
            "swing_score": 0,
            "swing_type": "INVALID_DATA",
        }

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return {
            "swing_score": 0,
            "swing_type": "NO_ALPACA_CREDENTIALS",
        }

    session = requests.Session()
    session.headers.update(
        _headers()
    )

    bars = _get_daily_bars(
        session,
        ticker,
    )

    if len(bars) < 20:
        return {
            "swing_score": 0,
            "swing_type": "INSUFFICIENT_DATA",
            "bars": len(bars),
        }

    closes = [
        _safe_float(b.get("c"))
        for b in bars
    ]

    volumes = [
        _safe_float(b.get("v"))
        for b in bars
    ]

    highs = [
        _safe_float(b.get("h"))
        for b in bars
    ]

    lows = [
        _safe_float(b.get("l"))
        for b in bars
    ]

    closes = [
        x for x in closes if x > 0
    ]

    volumes = [
        x for x in volumes if x >= 0
    ]

    highs = [
        x for x in highs if x > 0
    ]

    lows = [
        x for x in lows if x > 0
    ]

    if len(closes) < 20:
        return {
            "swing_score": 0,
            "swing_type": "INSUFFICIENT_CLOSES",
        }

    # --------------------------------------------------------
    # Trend
    # --------------------------------------------------------

    ema20 = _ema(
        closes,
        20,
    )

    ema50 = _ema(
        closes,
        50,
    )

    above_20 = price > ema20
    above_50 = price > ema50
    ema_cross = ema20 > ema50

    ema20_prev = _ema(
        closes[:-10],
        20,
    ) if len(closes) > 30 else ema20

    ema_slope = (
        (ema20 / ema20_prev - 1)
        * 100
        if ema20_prev > 0
        else 0
    )

    pct_from_ema20 = (
        (price - ema20)
        / ema20
        * 100
        if ema20 > 0
        else 0
    )

    trend_score = 0

    if above_20:
        trend_score += 8

    if above_50:
        trend_score += 8

    if ema_cross:
        trend_score += 8

    if ema_slope > 0.5:
        trend_score += 8
    elif ema_slope > 0:
        trend_score += 4

    if -5 <= pct_from_ema20 <= 5:
        trend_score += 8

    trend_score = min(
        trend_score,
        40,
    )

    # --------------------------------------------------------
    # Relative strength vs SPY
    # --------------------------------------------------------

    spy_bars = _get_daily_bars(
        session,
        "SPY",
    )

    rs = 0.0

    if len(spy_bars) >= 20:

        spy_closes = [
            _safe_float(b.get("c"))
            for b in spy_bars
        ]

        if len(spy_closes) >= 20:

            stock_ret = (
                closes[-1]
                / closes[-20]
                - 1
            ) * 100

            spy_ret = (
                spy_closes[-1]
                / spy_closes[-20]
                - 1
            ) * 100

            rs = stock_ret - spy_ret

    if rs > 5:
        rs_score = 25
    elif rs > 2:
        rs_score = 20
    elif rs > 0:
        rs_score = 15
    elif rs > -5:
        rs_score = 5
    else:
        rs_score = 0

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    if len(volumes) >= 20:

        avg20 = sum(
            volumes[-20:]
        ) / 20.0

        avg5 = sum(
            volumes[-5:]
        ) / 5.0

        rvol = (
            avg5 / avg20
            if avg20 > 0
            else 1.0
        )

    else:
        rvol = 1.0

    if rvol >= 2:
        volume_score = 20
    elif rvol >= 1.5:
        volume_score = 15
    elif rvol >= 1:
        volume_score = 10
    else:
        volume_score = 5

    # --------------------------------------------------------
    # Structure
    # --------------------------------------------------------

    recent_high = (
        max(closes[-10:])
    )

    recent_low = (
        min(closes[-10:])
    )

    if price >= recent_high * 0.995:
        structure = "BREAKOUT"
        structure_score = 20

    elif price >= recent_high * 0.95:
        structure = "CONSOLIDATION"
        structure_score = 12

    elif price > recent_low:
        structure = "PULLBACK"
        structure_score = 8

    else:
        structure = "WEAK"
        structure_score = 3

    # --------------------------------------------------------
    # Catalyst
    # --------------------------------------------------------

    catalyst_value = _safe_float(
        candidate.get(
            "catalyst_quality",
            0,
        )
    )

    # Also support nested analysis.
    if catalyst_value == 0:
        analysis = candidate.get(
            "analysis",
            {}
        )

        catalyst = analysis.get(
            "catalyst",
            {}
        )

        if isinstance(catalyst, dict):
            catalyst_value = _safe_float(
                catalyst.get(
                    "score",
                    0,
                )
            )

    if catalyst_value >= 8:
        catalyst_score = 15
    elif catalyst_value >= 5:
        catalyst_score = 10
    elif catalyst_value > 0:
        catalyst_score = 5
    else:
        catalyst_score = 0

    # --------------------------------------------------------
    # Risk
    # --------------------------------------------------------

    risk_penalty = 0

    analysis = candidate.get(
        "analysis",
        {}
    )

    sec_risk = analysis.get(
        "sec_risk",
        {}
    )

    if isinstance(sec_risk, dict):
        if sec_risk.get(
            "has_offering"
        ):
            risk_level = str(
                sec_risk.get(
                    "risk_level",
                    "LOW",
                )
            ).upper()

            if risk_level == "HIGH":
                risk_penalty -= 30
            elif risk_level == "MEDIUM":
                risk_penalty -= 15
            else:
                risk_penalty -= 7

    float_val = _safe_float(
        analysis.get("float")
    )

    if float_val > 100_000_000:
        risk_penalty -= 10
    elif float_val > 50_000_000:
        risk_penalty -= 5

    total_score = (
        trend_score
        + rs_score
        + volume_score
        + structure_score
        + catalyst_score
        + risk_penalty
    )

    total_score = max(
        0,
        min(100, total_score),
    )

    return {
        "swing_score": round(
            total_score,
            1,
        ),
        "trend_score": trend_score,
        "rs_score": rs_score,
        "volume_score": volume_score,
        "structure_score": structure_score,
        "catalyst_score": catalyst_score,
        "risk_penalty": risk_penalty,
        "above_20": above_20,
        "above_50": above_50,
        "ema_cross": ema_cross,
        "ema_slope": round(
            ema_slope,
            2,
        ),
        "pct_from_ema20": round(
            pct_from_ema20,
            2,
        ),
        "rs_vs_spy": round(
            rs,
            2,
        ),
        "rvol": round(
            rvol,
            2,
        ),
        "structure": structure,
        "price": price,
        "ema20": round(
            ema20,
            2,
        ),
        "ema50": round(
            ema50,
            2,
        ),
        "data_source": "ALPACA_IEX",
    }
