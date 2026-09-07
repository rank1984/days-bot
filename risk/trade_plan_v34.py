"""
DAYS-BOT V4.3 – Trade Plan
Deterministic Python-only trade planning.

CRITICAL: Handles pm_high / pm_vwap = None properly.
No TypeError on None.
"""
from typing import Dict, Any
import math


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_trade_plan(
    candidate: Dict[str, Any],
    account_size: float = 5000.0,
    max_risk_pct: float = 0.005,
    max_position_pct: float = 0.20,
) -> Dict[str, Any]:
    """
    Build a trade plan based on PM data.
    Returns a full plan with entry/stop/targets, or NO_TRADE if invalid.
    """
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

    # ------------------------------------------------------------
    # 1. Extract and validate inputs
    # ------------------------------------------------------------
    price = _safe_float(candidate.get("price", 0))
    pm_high = _safe_float(candidate.get("pm_high", 0))
    pm_vwap = _safe_float(candidate.get("pm_vwap", 0))
    pm_low = _safe_float(candidate.get("pm_low", 0))

    # If pm_high is None or 0, we cannot build a valid entry
    if pm_high <= 0:
        result["plan_error"] = "MISSING_PM_HIGH"
        return result

    if pm_vwap <= 0:
        # If no VWAP, use pm_high * 0.98 as a fallback
        pm_vwap = pm_high * 0.98

    if price <= 0:
        result["plan_error"] = "MISSING_PRICE"
        return result

    # ------------------------------------------------------------
    # 2. Entry – breakout above PMH
    # ------------------------------------------------------------
    entry = round(pm_high * 1.005, 2)

    # ------------------------------------------------------------
    # 3. Stop – VWAP-based structural stop
    # ------------------------------------------------------------
    structural_stop = pm_vwap * 0.995

    # Volatility proxy: distance between PMH and VWAP
    range_proxy = abs(pm_high - pm_vwap)
    if range_proxy <= 0:
        range_proxy = entry * 0.01  # fallback 1%

    volatility_stop = entry - max(range_proxy, entry * 0.01)
    stop = max(structural_stop, volatility_stop)
    stop = round(stop, 2)

    # ------------------------------------------------------------
    # 4. Basic validation
    # ------------------------------------------------------------
    if entry <= stop:
        result["plan_error"] = "ENTRY_NOT_ABOVE_STOP"
        return result

    risk_per_share = entry - stop
    if risk_per_share <= 0:
        result["plan_error"] = "NON_POSITIVE_RISK"
        return result

    # ------------------------------------------------------------
    # 5. Account risk & Position sizing
    # ------------------------------------------------------------
    max_risk_dollars = account_size * max_risk_pct
    max_position_value = account_size * max_position_pct

    shares_by_risk = math.floor(max_risk_dollars / risk_per_share)
    shares_by_position = math.floor(max_position_value / entry)
    shares = min(shares_by_risk, shares_by_position)

    if shares <= 0:
        result["plan_error"] = "POSITION_SIZE_ZERO"
        return result

    # ------------------------------------------------------------
    # 6. Targets
    # ------------------------------------------------------------
    target_1 = round(entry + (2.0 * risk_per_share), 2)
    target_2 = round(entry + (4.0 * risk_per_share), 2)
    max_loss = round(shares * risk_per_share, 2)

    # ------------------------------------------------------------
    # 7. Final validation
    # ------------------------------------------------------------
    if not (entry > stop and target_1 > entry and target_2 > target_1 and risk_per_share > 0 and shares > 0):
        result["plan_error"] = "VALIDATION_FAILED"
        return result

    # ------------------------------------------------------------
    # 8. Valid plan
    # ------------------------------------------------------------
    result.update({
        "decision": "WAIT_BREAKOUT",
        "entry": entry,
        "stop": stop,
        "target_1": target_1,
        "target_2": target_2,
        "position_size": shares,
        "max_loss": max_loss,
        "risk_per_share": round(risk_per_share, 2),
        "hold_type": "MOMENTUM_15_90M",
        "plan_valid": True,
        "plan_error": None,
    })

    return result