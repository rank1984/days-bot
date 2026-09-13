"""
DAYS-BOT V5.0.5.2 – Deterministic Trade Plan

Python-only trade planning.
No LLM decisions.

Rules:
- Requires valid price + PM high + PM VWAP.
- Entry = PMH breakout.
- Stop is structure/volatility based.
- Minimum stop distance = 1.5%.
- Position sizing is recalculated AFTER stop rounding.
- No valid plan when required PM data is missing.
"""

from typing import Dict, Any
import math


MIN_STOP_PCT = 0.015
TICK_SIZE = 0.01


def _safe_float(value, default=None):
    try:
        if value is None:
            return default
        result = float(value)
        if not math.isfinite(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def _round_up_tick(price: float) -> float:
    """Round upward to the nearest $0.01."""
    return round(
        math.ceil((price / TICK_SIZE) - 1e-9) * TICK_SIZE,
        2
    )


def _round_down_tick(price: float) -> float:
    """Round downward to the nearest $0.01."""
    return round(
        math.floor((price / TICK_SIZE) + 1e-9) * TICK_SIZE,
        2
    )


def build_trade_plan(
    candidate: Dict[str, Any],
    account_size: float = 5000.0,
    max_risk_pct: float = 0.005,
    max_position_pct: float = 0.20,
) -> Dict[str, Any]:

    result = {
        "decision": "NO_TRADE",
        "entry": None,
        "stop": None,
        "target_1": None,
        "target_2": None,
        "position_size": 0,
        "max_loss": 0.0,
        "risk_per_share": None,
        "hold_type": "NONE",
        "plan_valid": False,
        "plan_error": None,
    }

    # 1. Validate basic inputs
    price = _safe_float(candidate.get("price"))
    pm_high = _safe_float(candidate.get("pm_high"))
    pm_vwap = _safe_float(candidate.get("pm_vwap"))

    if price is None or price <= 0:
        result["plan_error"] = "MISSING_PRICE"
        return result

    if pm_high is None or pm_high <= 0:
        result["plan_error"] = "MISSING_PM_HIGH"
        return result

    if pm_vwap is None or pm_vwap <= 0:
        result["plan_error"] = "MISSING_PM_VWAP"
        return result

    # 2. Entry – PMH breakout
    raw_entry = pm_high * 1.005
    entry = _round_up_tick(raw_entry)

    if entry <= pm_high:
        entry = round(pm_high + TICK_SIZE, 2)

    # 3. Structural / volatility stop
    structural_stop = pm_vwap * 0.995

    range_proxy = abs(pm_high - pm_vwap)
    if range_proxy <= 0:
        range_proxy = entry * 0.01

    volatility_distance = max(range_proxy, entry * MIN_STOP_PCT)
    volatility_stop = entry - volatility_distance

    proposed_stop = max(structural_stop, volatility_stop)

    # 4. Enforce minimum stop distance
    minimum_stop_price = entry * (1.0 - MIN_STOP_PCT)

    if proposed_stop > minimum_stop_price:
        proposed_stop = minimum_stop_price

    stop = _round_down_tick(proposed_stop)

    # 5. Validate stop
    if stop <= 0:
        result["plan_error"] = "INVALID_STOP"
        return result

    if stop >= entry:
        result["plan_error"] = "ENTRY_NOT_ABOVE_STOP"
        return result

    risk_per_share = round(entry - stop, 2)

    if risk_per_share <= 0:
        result["plan_error"] = "NON_POSITIVE_RISK"
        return result

    stop_distance_pct = (entry - stop) / entry

    if stop_distance_pct < MIN_STOP_PCT:
        result["plan_error"] = "STOP_DISTANCE_BELOW_MINIMUM"
        return result

    # 6. Position sizing
    max_risk_dollars = account_size * max_risk_pct
    max_position_value = account_size * max_position_pct

    shares_by_risk = math.floor(max_risk_dollars / risk_per_share)
    shares_by_position = math.floor(max_position_value / entry)

    shares = min(shares_by_risk, shares_by_position)

    if shares <= 0:
        result["plan_error"] = "POSITION_SIZE_ZERO"
        return result

    # 7. Targets
    target_1 = round(entry + (2.0 * risk_per_share), 2)
    target_2 = round(entry + (4.0 * risk_per_share), 2)
    max_loss = round(shares * risk_per_share, 2)

    # 8. Final validation
    if not (
        entry > stop
        and target_1 > entry
        and target_2 > target_1
        and risk_per_share > 0
        and shares > 0
        and stop_distance_pct >= MIN_STOP_PCT
    ):
        result["plan_error"] = "VALIDATION_FAILED"
        return result

    # 9. Valid plan
    result.update({
        "decision": "WAIT_BREAKOUT",
        "entry": entry,
        "stop": stop,
        "target_1": target_1,
        "target_2": target_2,
        "position_size": shares,
        "max_loss": max_loss,
        "risk_per_share": risk_per_share,
        "hold_type": "MOMENTUM_15_90M",
        "plan_valid": True,
        "plan_error": None,
    })

    return result
