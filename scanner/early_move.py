"""
DAYS-BOT V5.0.4 – Early Move Detection Engine
"""
import pytz
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

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


def _get_price_bars(ticker: str, lookback_minutes: int = 30) -> Optional[List[Dict[str, Any]]]:
    """Fetch 1-minute OHLCV bars using Alpaca IEX feed."""
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
    if len(bars) < 10:
        return 0.0

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]

    dips = []
    for i in range(5, len(bars)):
        recent_high = max(highs[i-5:i])
        if recent_high > 0:
            dip_pct = (recent_high - closes[i]) / recent_high * 100
            if dip_pct > 0.3:
                dips.append(dip_pct)

    if not dips:
        return 0.0

    avg_dip = sum(dips) / len(dips)

    recovery_times = []
    for i in range(5, len(bars)-5):
        if closes[i] < closes[i-1] * 0.995:
            for j in range(i+1, min(i+10, len(bars))):
                if closes[j] >= closes[i-1]:
                    recovery_times.append(j - i)
                    break

    avg_recovery = sum(recovery_times) / len(recovery_times) if recovery_times else 10

    dip_score = max(0, min(100, 100 - avg_dip * 10))
    recovery_score = max(0, min(100, 100 - avg_recovery * 10))

    return round((dip_score * 0.5 + recovery_score * 0.5), 1)


def _score_pmh_pressure(bars: List[Dict], pm_high: float) -> float:
    if pm_high <= 0 or len(bars) < 10:
        return 0.0

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    total = len(closes)

    if total == 0:
        return 0.0

    near_pmh = sum(1 for c in closes if abs(c - pm_high) / pm_high < 0.015)
    attempts = sum(1 for h in highs if h >= pm_high)

    near_ratio = near_pmh / total if total > 0 else 0
    attempt_score = min(100, attempts * 15)
    near_score = min(100, near_ratio * 150)

    return round((attempt_score * 0.5 + near_score * 0.5), 1)


def _score_volume_acceleration(bars: List[Dict]) -> float:
    if len(bars) < 10:
        return 0.0

    volumes = [b["volume"] for b in bars]
    total = len(volumes)
    half = total // 2

    if half < 3:
        return 0.0

    first_half = volumes[:half]
    second_half = volumes[half:]

    avg_first = sum(first_half) / len(first_half) if first_half else 1
    avg_second = sum(second_half) / len(second_half) if second_half else 1

    if avg_first == 0:
        return 0.0

    acceleration = avg_second / avg_first

    if acceleration >= 2.5:
        return 100.0
    elif acceleration >= 1.8:
        return 80.0
    elif acceleration >= 1.3:
        return 55.0
    elif acceleration >= 1.0:
        return 25.0
    return 0.0


def _score_price_acceleration(bars: List[Dict]) -> float:
    if len(bars) < 10:
        return 0.0

    closes = [b["close"] for b in bars]
    total = len(closes)
    half = total // 2

    if half < 3:
        return 0.0

    first_half = closes[:half]
    second_half = closes[half:]

    first_start = first_half[0]
    first_end = first_half[-1]
    second_start = second_half[0]
    second_end = second_half[-1]

    if first_start == 0 or second_start == 0:
        return 0.0

    first_return = (first_end - first_start) / first_start * 100
    second_return = (second_end - second_start) / second_start * 100

    if second_return > first_return and second_return > 0.5:
        accel_factor = second_return / max(0.1, first_return) if first_return > 0 else 2
        return round(min(100, accel_factor * 25), 1)
    elif second_return > 0:
        return 35.0
    return 0.0


def _score_vwap_control(bars: List[Dict], vwap: float) -> float:
    if vwap <= 0 or len(bars) < 10:
        return 0.0

    closes = [b["close"] for b in bars]
    above_vwap = sum(1 for c in closes if c >= vwap * 0.995)
    total = len(closes)

    if total == 0:
        return 0.0

    ratio = above_vwap / total
    return round(min(100, ratio * 120), 1)


def _classify_state(early_score: float, components: Dict[str, float]) -> str:
    """State = behavioral, not just score."""
    pmh = components.get('pmh_pressure', 0)
    vol = components.get('volume_acceleration', 0)
    pb = components.get('pullback_buying', 0)

    if early_score < 30:
        return "QUIET"
    elif early_score < 50:
        if pmh > 40 and vol > 30:
            return "PRESSURE"
        return "ACCUMULATION"
    elif early_score < 70:
        if pmh > 50 and vol > 40 and pb > 40:
            return "BREAKOUT_SETUP"
        elif pmh > 40:
            return "PRESSURE"
        return "BREAKOUT"
    elif early_score < 85:
        if vol > 60 and early_score > 75:
            return "MOMENTUM"
        return "EXTENSION"
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
    If data is insufficient, returns state='UNAVAILABLE'.
    """
    if bars is None:
        bars = _get_price_bars(ticker, lookback_minutes=30)

    if not bars or len(bars) < 5:
        return {
            "early_score": 0,
            "state": "UNAVAILABLE",
            "components": {},
            "data_quality": "UNKNOWN",
            "error": "Not enough bars"
        }

    components = {
        "pullback_buying": _score_pullback_buying(bars),
        "volume_acceleration": _score_volume_acceleration(bars),
        "price_acceleration": _score_price_acceleration(bars),
    }

    if pm_high is not None and pm_high > 0:
        components["pmh_pressure"] = _score_pmh_pressure(bars, pm_high)
    else:
        components["pmh_pressure"] = 0

    if vwap is not None and vwap > 0:
        components["vwap_control"] = _score_vwap_control(bars, vwap)
    else:
        components["vwap_control"] = 0

    # weighted score
    weights = {
        "pullback_buying": 0.25,
        "pmh_pressure": 0.20,
        "volume_acceleration": 0.20,
        "price_acceleration": 0.20,
        "vwap_control": 0.15,
    }

    early_score = 0.0
    for key, weight in weights.items():
        early_score += components.get(key, 0) * weight

    early_score = round(early_score, 1)
    state = _classify_state(early_score, components)

    data_quality = "GOOD" if len(bars) >= 15 else "PARTIAL"

    return {
        "early_score": early_score,
        "state": state,
        "components": components,
        "data_quality": data_quality,
        "bars_count": len(bars),
    }
