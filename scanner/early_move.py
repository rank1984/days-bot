"""
DAYS-BOT V4.4 – Early Move Detection Engine

Identifies behavioral signatures before price moves:
- Pullback buying (dip buyers)
- PMH pressure (resistance tests)
- Volume acceleration
- Price acceleration
- Time above VWAP
- Breakout attempts

Returns:
    early_score (0-100)
    components (dict of sub-scores)
    state (str): ACCUMULATION, PRESSURE, BREAKOUT, MOMENTUM, EXHAUSTION, FADE
"""

import pytz
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

ET = pytz.timezone("America/New_York")


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_price_bars(ticker: str, lookback_minutes: int = 30) -> Optional[List[Dict[str, float]]]:
    """
    Fetch 1-minute OHLCV bars for the last N minutes.
    Uses Alpaca IEX feed.
    """
    import requests
    from utils.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_DATA_URL

    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None

    now_et = datetime.now(ET)
    start = now_et - timedelta(minutes=lookback_minutes + 5)

    try:
        response = requests.get(
            f"{ALPACA_DATA_URL.rstrip('/')}/v2/stocks/bars",
            headers={
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
                "Accept": "application/json",
            },
            params={
                "symbols": ticker,
                "timeframe": "1Min",
                "start": start.isoformat(),
                "end": now_et.isoformat(),
                "adjustment": "raw",
                "feed": "iex",
                "limit": 100,
            },
            timeout=10,
        )

        if response.status_code != 200:
            return None

        data = response.json()
        bars = data.get("bars", {}).get(ticker, [])

        if not bars:
            return None

        # Parse bars
        parsed = []
        for bar in bars:
            ts = datetime.fromisoformat(bar["t"].replace("Z", "+00:00")).astimezone(ET)
            parsed.append({
                "time": ts,
                "open": _safe_float(bar.get("o")),
                "high": _safe_float(bar.get("h")),
                "low": _safe_float(bar.get("l")),
                "close": _safe_float(bar.get("c")),
                "volume": _safe_int(bar.get("v")),
            })

        return parsed

    except Exception as e:
        print(f"[EarlyMove] Error fetching bars for {ticker}: {e}")
        return None


def _score_pullback_buying(bars: List[Dict]) -> float:
    """
    Measures how quickly dips are bought.
    - Lower dip depth = better
    - Faster recovery = better
    """
    if len(bars) < 10:
        return 0.0

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]

    # Find dips of > 0.5% from recent high
    dips = []
    for i in range(5, len(bars)):
        recent_high = max(highs[i-5:i])
        if recent_high > 0:
            dip_pct = (recent_high - closes[i]) / recent_high * 100
            if dip_pct > 0.5:
                dips.append(dip_pct)

    if not dips:
        return 0.0

    # Average dip depth
    avg_dip = sum(dips) / len(dips)

    # Recovery speed: how many bars to return to previous high
    recovery_times = []
    for i in range(5, len(bars)-5):
        if closes[i] < closes[i-1] * 0.995:  # dipped
            for j in range(i+1, min(i+10, len(bars))):
                if closes[j] >= closes[i-1]:
                    recovery_times.append(j - i)
                    break

    avg_recovery = sum(recovery_times) / len(recovery_times) if recovery_times else 10

    # Score: lower dip + faster recovery = higher score
    dip_score = max(0, min(100, 100 - avg_dip * 10))
    recovery_score = max(0, min(100, 100 - avg_recovery * 10))

    return round((dip_score * 0.6 + recovery_score * 0.4), 1)


def _score_pmh_pressure(bars: List[Dict], pm_high: float) -> float:
    """
    Measures pressure near PMH - repeated tests without breakdown.
    """
    if pm_high <= 0 or len(bars) < 10:
        return 0.0

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]

    # Count bars within 1% of PMH
    near_pmh = sum(1 for c in closes if abs(c - pm_high) / pm_high < 0.01)
    total_bars = len(closes)

    if total_bars == 0:
        return 0.0

    # Count breakout attempts (bars that touched PMH or higher)
    attempts = sum(1 for h in highs if h >= pm_high)

    # Ratio of time spent near PMH
    near_ratio = near_pmh / total_bars

    # Pressure score: more attempts + more time near PMH = higher pressure
    attempt_score = min(100, attempts * 15)
    near_score = min(100, near_ratio * 200)

    return round((attempt_score * 0.5 + near_score * 0.5), 1)


def _score_volume_acceleration(bars: List[Dict]) -> float:
    """
    Measures if volume is accelerating (increasing over time).
    """
    if len(bars) < 10:
        return 0.0

    volumes = [b["volume"] for b in bars]
    total = len(volumes)

    # Split into first half and second half
    half = total // 2
    first_half = volumes[:half]
    second_half = volumes[half:]

    if not first_half or not second_half:
        return 0.0

    avg_first = sum(first_half) / len(first_half) if first_half else 1
    avg_second = sum(second_half) / len(second_half) if second_half else 1

    if avg_first == 0:
        return 0.0

    acceleration = avg_second / avg_first

    # Score: >1 is acceleration, <1 is deceleration
    if acceleration >= 2.0:
        return 100.0
    elif acceleration >= 1.5:
        return 75.0
    elif acceleration >= 1.2:
        return 50.0
    elif acceleration >= 1.0:
        return 25.0
    else:
        return 0.0


def _score_price_acceleration(bars: List[Dict]) -> float:
    """
    Measures if price is accelerating upward.
    """
    if len(bars) < 10:
        return 0.0

    closes = [b["close"] for b in bars]
    total = len(closes)

    # Split into first half and second half
    half = total // 2
    first_half = closes[:half]
    second_half = closes[half:]

    if not first_half or not second_half:
        return 0.0

    first_start = first_half[0]
    first_end = first_half[-1]
    second_start = second_half[0]
    second_end = second_half[-1]

    if first_start == 0:
        return 0.0

    first_return = (first_end - first_start) / first_start * 100
    second_return = (second_end - second_start) / second_start * 100

    # Score: positive acceleration = higher score
    if second_return > first_return and second_return > 0:
        # Acceleration is positive
        accel_factor = second_return / max(0.1, first_return)
        score = min(100, accel_factor * 30)
        return round(score, 1)
    elif second_return > 0:
        # Positive but slowing
        return 40.0
    else:
        return 0.0


def _score_vwap_control(bars: List[Dict], vwap: float) -> float:
    """
    Measures percentage of time price is above VWAP.
    """
    if vwap <= 0 or len(bars) < 10:
        return 0.0

    closes = [b["close"] for b in bars]
    above_vwap = sum(1 for c in closes if c >= vwap)
    total = len(closes)

    if total == 0:
        return 0.0

    ratio = above_vwap / total

    # Score: higher ratio = stronger control
    return round(min(100, ratio * 150), 1)


def _score_breakout_attempts(bars: List[Dict], pm_high: float) -> float:
    """
    Measures how many times price tested PMH and pulled back.
    """
    if pm_high <= 0 or len(bars) < 5:
        return 0.0

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]

    # Count breakout attempts: highs above PMH but closes below
    attempts = 0
    for i in range(len(bars)):
        if highs[i] >= pm_high and closes[i] < pm_high * 1.01:
            attempts += 1

    # Score: more attempts = higher pressure (up to 5 attempts = 100)
    return round(min(100, attempts * 20), 1)


def _classify_state(early_score: float, components: Dict[str, float]) -> str:
    """
    Classify the current behavioral state.
    """
    if early_score < 30:
        return "ACCUMULATION"
    elif early_score < 50:
        return "PRESSURE"
    elif early_score < 70:
        return "BREAKOUT"
    elif early_score < 85:
        return "MOMENTUM"
    else:
        return "EXHAUSTION"


def calculate_early_move_score(
    ticker: str,
    pm_high: Optional[float] = None,
    vwap: Optional[float] = None,
    bars: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Calculate Early Move Score and behavioral state.

    Args:
        ticker: Stock ticker
        pm_high: Premarket high (if available)
        vwap: VWAP (if available)
        bars: 1-minute OHLCV bars (if None, fetched automatically)

    Returns:
        {
            "early_score": float (0-100),
            "components": dict,
            "state": str
        }
    """
    # Fetch bars if not provided
    if bars is None:
        bars = _get_price_bars(ticker, lookback_minutes=30)

    if not bars or len(bars) < 5:
        return {
            "early_score": 0,
            "state": "INSUFFICIENT_DATA",
            "components": {},
            "error": "Not enough bars"
        }

    # Calculate components
    components = {}

    # Pullback buying
    components["pullback_buying"] = _score_pullback_buying(bars)

    # PMH pressure (if pm_high available)
    if pm_high is not None and pm_high > 0:
        components["pmh_pressure"] = _score_pmh_pressure(bars, pm_high)
        components["breakout_attempts"] = _score_breakout_attempts(bars, pm_high)
    else:
        components["pmh_pressure"] = 0
        components["breakout_attempts"] = 0

    # Volume acceleration
    components["volume_acceleration"] = _score_volume_acceleration(bars)

    # Price acceleration
    components["price_acceleration"] = _score_price_acceleration(bars)

    # VWAP control (if vwap available)
    if vwap is not None and vwap > 0:
        components["vwap_control"] = _score_vwap_control(bars, vwap)
    else:
        components["vwap_control"] = 0

    # Weighted early score
    weights = {
        "pullback_buying": 0.25,
        "pmh_pressure": 0.20,
        "breakout_attempts": 0.15,
        "volume_acceleration": 0.15,
        "price_acceleration": 0.15,
        "vwap_control": 0.10,
    }

    # Calculate weighted score
    early_score = 0.0
    for key, weight in weights.items():
        early_score += components.get(key, 0) * weight

    early_score = round(early_score, 1)

    # State classification
    state = _classify_state(early_score, components)

    return {
        "early_score": early_score,
        "state": state,
        "components": components,
        "bars_count": len(bars),
    }
