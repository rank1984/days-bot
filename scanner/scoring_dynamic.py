"""
DAYS-BOT V4.4 – Dynamic Scoring Engine

Dynamic weights based on Early State:
- ACCUMULATION: Float/Short/Catalyst get higher weight
- PRESSURE: Early Move/PMH Pressure/Volume Acceleration get higher weight
- BREAKOUT+: PMH Break/Volume Acceleration/VWAP get higher weight

All scores are deterministic and independent of market conditions.
"""
from typing import Dict, Any


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_score(score: float, max_score: float) -> float:
    """Normalize score to 0-1 range."""
    if max_score <= 0:
        return 0.0
    return min(1.0, max(0.0, score / max_score))


def calculate_dynamic_scores(early_state: str, components: Dict[str, float], candidate: Dict) -> Dict[str, Any]:
    """
    Calculate Day Trade Score and Swing Score based on Early State.

    Returns:
        {
            "day_trade_score": float (0-100),
            "swing_score": float (0-100),
            "weight_mapping": dict
        }
    """

    # Extract components with safe defaults
    early_score = _safe_float(components.get('early_score', 0))
    pullback_buying = _safe_float(components.get('pullback_buying', 0))
    pmh_pressure = _safe_float(components.get('pmh_pressure', 0))
    breakout_attempts = _safe_float(components.get('breakout_attempts', 0))
    volume_acceleration = _safe_float(components.get('volume_acceleration', 0))
    price_acceleration = _safe_float(components.get('price_acceleration', 0))
    vwap_control = _safe_float(components.get('vwap_control', 0))

    # Candidate factors
    gap = _safe_float(candidate.get('gap_pct', 0))
    pm_volume = _safe_float(candidate.get('pm_volume', 0))
    float_val = _safe_float(candidate.get('float', 0))
    short_interest = _safe_float(candidate.get('short_interest', 0))
    catalyst_score = _safe_float(candidate.get('catalyst_score', 0))

    # Normalize factors to 0-1
    gap_norm = _normalize_score(gap, 20)  # max 20% gap
    pm_volume_norm = _normalize_score(pm_volume, 1_000_000)  # max 1M volume
    float_norm = 1.0 - _normalize_score(float_val, 50_000_000)  # lower float = higher score
    short_norm = _normalize_score(short_interest, 0.30)  # max 30% short interest
    catalyst_norm = _normalize_score(catalyst_score, 10)  # max score 10

    # -----------------------------------------------------------------
    # 1. Day Trade Score (faster, more aggressive)
    # -----------------------------------------------------------------
    # Weights based on Early State (for Day Trade)
    if early_state in ["ACCUMULATION", "PRESSURE"]:
        weights = {
            "pullback_buying": 0.20,
            "pmh_pressure": 0.20,
            "breakout_attempts": 0.10,
            "volume_acceleration": 0.15,
            "price_acceleration": 0.10,
            "vwap_control": 0.05,
            "gap": 0.10,
            "pm_volume": 0.10,
        }
    else:  # BREAKOUT, MOMENTUM, EXHAUSTION
        weights = {
            "pullback_buying": 0.10,
            "pmh_pressure": 0.10,
            "breakout_attempts": 0.10,
            "volume_acceleration": 0.20,
            "price_acceleration": 0.15,
            "vwap_control": 0.10,
            "gap": 0.10,
            "pm_volume": 0.15,
        }

    day_trade_raw = (
        weights.get("pullback_buying", 0) * _normalize_score(pullback_buying, 100) +
        weights.get("pmh_pressure", 0) * _normalize_score(pmh_pressure, 100) +
        weights.get("breakout_attempts", 0) * _normalize_score(breakout_attempts, 100) +
        weights.get("volume_acceleration", 0) * _normalize_score(volume_acceleration, 100) +
        weights.get("price_acceleration", 0) * _normalize_score(price_acceleration, 100) +
        weights.get("vwap_control", 0) * _normalize_score(vwap_control, 100) +
        weights.get("gap", 0) * gap_norm +
        weights.get("pm_volume", 0) * pm_volume_norm
    )

    day_trade_score = round(day_trade_raw * 100, 1)

    # -----------------------------------------------------------------
    # 2. Swing Score (slower, more patient)
    # -----------------------------------------------------------------
    swing_weights = {
        "catalyst": 0.25,
        "float": 0.20,
        "short_interest": 0.15,
        "early_score": 0.15,
        "pullback_buying": 0.05,
        "pmh_pressure": 0.05,
        "volume_acceleration": 0.05,
        "vwap_control": 0.05,
        "gap": 0.05,
    }

    swing_raw = (
        swing_weights.get("catalyst", 0) * catalyst_norm +
        swing_weights.get("float", 0) * float_norm +
        swing_weights.get("short_interest", 0) * short_norm +
        swing_weights.get("early_score", 0) * _normalize_score(early_score, 100) +
        swing_weights.get("pullback_buying", 0) * _normalize_score(pullback_buying, 100) +
        swing_weights.get("pmh_pressure", 0) * _normalize_score(pmh_pressure, 100) +
        swing_weights.get("volume_acceleration", 0) * _normalize_score(volume_acceleration, 100) +
        swing_weights.get("vwap_control", 0) * _normalize_score(vwap_control, 100) +
        swing_weights.get("gap", 0) * gap_norm
    )

    swing_score = round(swing_raw * 100, 1)

    # -----------------------------------------------------------------
    # 3. Determine Trade Type
    # -----------------------------------------------------------------
    if day_trade_score >= 70 and swing_score >= 70:
        trade_type = "BOTH"
    elif day_trade_score >= 70:
        trade_type = "INTRADAY"
    elif swing_score >= 70:
        trade_type = "SWING_1_3D"
    elif day_trade_score >= 55 or swing_score >= 55:
        trade_type = "WATCH"
    else:
        trade_type = "NO_TRADE"

    return {
        "day_trade_score": day_trade_score,
        "swing_score": swing_score,
        "trade_type": trade_type,
        "weight_mapping": weights,
        }
