"""
DAYS-BOT V5.0 – Dynamic Scoring Engine

Early State | Accumulation | Pressure | Breakout/Momentum
Factor       | Acc (%) | Pressure (%) | Breakout+ (%)
Early Move   | 15      | 30           | 35
Catalyst     | 20      | 20           | 15
Float        | 20      | 15           | 10
Short        | 15      | 10           | 10
Volume       | 10      | 15           | 20
PMH/VWAP     | 10      | 10           | 10
Structure    | 10      | 10           | 0–5

Weights are research parameters (editable in config).
All scores are 0-100.
"""
from utils.config import LEARNING_MODE


# ============================================================
# WEIGHT CONFIGURATION (Research Parameters)
# ============================================================

WEIGHTS = {
    "ACCUMULATION": {
        "early_move": 0.15,
        "catalyst": 0.20,
        "float": 0.20,
        "short": 0.15,
        "volume": 0.10,
        "pm_vwap": 0.10,
        "structure": 0.10,
    },
    "PRESSURE": {
        "early_move": 0.30,
        "catalyst": 0.20,
        "float": 0.15,
        "short": 0.10,
        "volume": 0.15,
        "pm_vwap": 0.10,
        "structure": 0.10,
    },
    "BREAKOUT": {
        "early_move": 0.35,
        "catalyst": 0.15,
        "float": 0.10,
        "short": 0.10,
        "volume": 0.20,
        "pm_vwap": 0.10,
        "structure": 0.05,
    },
    "MOMENTUM": {
        "early_move": 0.35,
        "catalyst": 0.15,
        "float": 0.10,
        "short": 0.10,
        "volume": 0.20,
        "pm_vwap": 0.10,
        "structure": 0.05,
    },
    "UNKNOWN": {
        "early_move": 0.20,
        "catalyst": 0.20,
        "float": 0.20,
        "short": 0.15,
        "volume": 0.15,
        "pm_vwap": 0.10,
        "structure": 0.10,
    }
}

# Defaults when sub-scores are missing
DEFAULT_COMPONENTS = {
    "early_move": 0,
    "catalyst_score": 0,
    "float_score": 0,
    "short_score": 0,
    "volume_score": 0,
    "pm_vwap_score": 0,
    "structure_score": 0,
}


def _safe_score(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_score(score: float) -> float:
    """Ensure score is between 0 and 100"""
    return round(max(0, min(100, score)), 1)


def calculate_day_trade_score(
    early_score: float,
    early_components: dict,
    catalyst_score: float,
    float_val: float,
    short_val: float,
    volume: float,
    pm_vwap: float,
    structure_score: float,
    early_state: str,
) -> float:
    """
    Day Trade Score – weighted by Early State.
    """
    state = early_state if early_state in WEIGHTS else "UNKNOWN"
    weights = WEIGHTS.get(state, WEIGHTS["UNKNOWN"])

    # Get component scores (0-100)
    # Early components:
    # - pullback_buying, pmh_pressure, breakout_attempts,
    # - volume_acceleration, price_acceleration, vwap_control
    pullback = _safe_score(early_components.get("pullback_buying", 0))
    pmh_pressure = _safe_score(early_components.get("pmh_pressure", 0))
    volume_accel = _safe_score(early_components.get("volume_acceleration", 0))
    price_accel = _safe_score(early_components.get("price_acceleration", 0))
    vwap_control = _safe_score(early_components.get("vwap_control", 0))
    breakout_attempts = _safe_score(early_components.get("breakout_attempts", 0))

    # Composite early_move score for day trading (weighted)
    early_move_composite = (
        pullback * 0.20 +
        pmh_pressure * 0.20 +
        volume_accel * 0.20 +
        price_accel * 0.15 +
        vwap_control * 0.15 +
        breakout_attempts * 0.10
    )
    early_move_score = _normalize_score(early_move_composite)

    # Component scores:
    # catalyst_score (0-10 mapped to 0-100)
    catalyst_norm = _normalize_score(catalyst_score * 10)

    # float_score: lower is better
    if float_val > 0:
        if float_val < 5_000_000:
            float_score = 100
        elif float_val < 10_000_000:
            float_score = 85
        elif float_val < 20_000_000:
            float_score = 70
        elif float_val < 50_000_000:
            float_score = 50
        else:
            float_score = 30
    else:
        float_score = 50  # neutral

    # short_score: higher is better
    if short_val > 0:
        if short_val >= 0.25:
            short_score = 100
        elif short_val >= 0.15:
            short_score = 80
        elif short_val >= 0.10:
            short_score = 60
        else:
            short_score = 30
    else:
        short_score = 40

    # volume_score: high volume = better
    if volume > 0:
        if volume >= 1_000_000:
            volume_score = 100
        elif volume >= 500_000:
            volume_score = 80
        elif volume >= 100_000:
            volume_score = 60
        else:
            volume_score = 30
    else:
        volume_score = 30

    # pm_vwap_score: price above VWAP is better
    if pm_vwap > 0:
        # pm_vwap is a price level, not a score – we need a proxy
        # We'll use price/vwap ratio, but we don't have price here
        # So we rely on vwap_control from early_components
        pm_vwap_score = _safe_score(early_components.get("vwap_control", 50))
    else:
        pm_vwap_score = 30

    # structure_score (higher lows, etc.) – use early_components as proxy
    structure_score = _safe_score(early_components.get("pullback_buying", 40))

    # Weighted sum
    total = (
        early_move_score * weights.get("early_move", 0.20) +
        catalyst_norm * weights.get("catalyst", 0.20) +
        float_score * weights.get("float", 0.15) +
        short_score * weights.get("short", 0.10) +
        volume_score * weights.get("volume", 0.15) +
        pm_vwap_score * weights.get("pm_vwap", 0.10) +
        structure_score * weights.get("structure", 0.10)
    )

    # Penalty for missing critical data (soft)
    if early_score == 0:
        total *= 0.8

    return _normalize_score(total)


def calculate_swing_score_dynamic(
    catalyst_score: float,
    catalyst_type: str,
    float_val: float,
    short_val: float,
    volume: float,
    early_state: str,
    early_score: float,
) -> float:
    """
    Swing Score (1-3 days) – focus on Catalyst, Float, Structure.
    Less dependent on early moves (but still uses state).
    """
    # Catalyst Quality (0-10 mapped to 0-100)
    catalyst_norm = _normalize_score(catalyst_score * 10)

    # Bonus for specific catalyst types
    catalyst_bonus = 0
    if catalyst_type in ["FDA_APPROVAL", "M&A"]:
        catalyst_bonus = 15
    elif catalyst_type in ["CONTRACT", "PARTNERSHIP"]:
        catalyst_bonus = 10
    elif catalyst_type in ["EARNINGS", "STRONG"]:
        catalyst_bonus = 5
    elif catalyst_type in ["WEAK", "GENERAL"]:
        catalyst_bonus = -5
    catalyst_norm = _normalize_score(catalyst_norm + catalyst_bonus)

    # Float: lower = better for swing
    if float_val > 0:
        if float_val < 5_000_000:
            float_score = 100
        elif float_val < 10_000_000:
            float_score = 85
        elif float_val < 20_000_000:
            float_score = 70
        elif float_val < 50_000_000:
            float_score = 50
        else:
            float_score = 30
    else:
        float_score = 50

    # Short: higher = better for swing (potential squeeze)
    if short_val > 0:
        if short_val >= 0.25:
            short_score = 100
        elif short_val >= 0.15:
            short_score = 80
        elif short_val >= 0.10:
            short_score = 60
        else:
            short_score = 30
    else:
        short_score = 40

    # Volume: moderate-high for swing
    if volume > 0:
        if volume >= 1_000_000:
            volume_score = 90
        elif volume >= 500_000:
            volume_score = 75
        elif volume >= 100_000:
            volume_score = 55
        else:
            volume_score = 30
    else:
        volume_score = 30

    # Early state impacts swing (PRESSURE/BREAKOUT are good)
    state_bonus = {
        "ACCUMULATION": 5,
        "PRESSURE": 10,
        "BREAKOUT": 15,
        "MOMENTUM": 20,
        "UNKNOWN": 0,
    }.get(early_state, 0)

    # Swing weights (more catalyst + structure focused)
    total = (
        catalyst_norm * 0.30 +
        float_score * 0.25 +
        short_score * 0.15 +
        volume_score * 0.15 +
        state_bonus * 0.15
    )

    # If no catalyst, penalize heavily
    if catalyst_score <= 3:
        total *= 0.7

    # If Float is very low AND short is high, bonus
    if float_val and float_val < 10_000_000 and short_val and short_val > 0.15:
        total += 10

    return _normalize_score(total)


def calculate_dynamic_scores(
    candidate: dict,
    analysis: dict,
    early_data: dict,
) -> dict:
    """
    Main entry point for dynamic scoring.

    Returns:
        {
            "day_trade_score": float,
            "swing_score": float,
            "early_score": float,
            "early_state": str,
            "early_components": dict,
        }
    """
    # Extract data
    early_score = early_data.get("early_score", 0)
    early_state = early_data.get("state", "UNKNOWN")
    early_components = early_data.get("components", {})

    catalyst = analysis.get("catalyst", {})
    catalyst_score = catalyst.get("score", 0)
    catalyst_type = catalyst.get("type", "GENERAL")

    float_val = analysis.get("float", 0)
    short_val = analysis.get("short_interest", 0)
    volume = candidate.get("pm_volume", 0)
    pm_vwap = candidate.get("pm_vwap", 0)
    structure_score = early_components.get("pullback_buying", 40)

    # Day Trade Score
    day_trade = calculate_day_trade_score(
        early_score=early_score,
        early_components=early_components,
        catalyst_score=catalyst_score,
        float_val=float_val,
        short_val=short_val,
        volume=volume,
        pm_vwap=pm_vwap,
        structure_score=structure_score,
        early_state=early_state,
    )

    # Swing Score
    swing = calculate_swing_score_dynamic(
        catalyst_score=catalyst_score,
        catalyst_type=catalyst_type,
        float_val=float_val,
        short_val=short_val,
        volume=volume,
        early_state=early_state,
        early_score=early_score,
    )

    return {
        "early_score": round(early_score, 1),
        "early_state": early_state,
        "early_components": early_components,
        "day_trade_score": day_trade,
        "swing_score": swing,
  }
