"""
DAYS-BOT V3.4 – Deterministic Trade Plan (No AI intervention)
"""
from typing import Dict, Any
import math

def build_trade_plan(candidate: Dict[str, Any],
                     account_size: float = 5000.0,
                     max_risk_pct: float = 0.005,
                     max_position_pct: float = 0.20) -> Dict[str, Any]:
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

    try:
        price = float(candidate.get('price', 0))
        pm_high = float(candidate.get('pm_high', 0))
        pm_vwap = float(candidate.get('pm_vwap', 0))
    except:
        result["plan_error"] = "INVALID_PRICE_DATA"
        return result

    if price <= 0 or pm_high <= 0 or pm_vwap <= 0:
        result["plan_error"] = "MISSING_LEVELS"
        return result

    entry = round(pm_high * 1.005, 2)
    structural_stop = pm_vwap * 0.995
    range_proxy = abs(pm_high - pm_vwap)
    volatility_stop = entry - max(range_proxy, entry * 0.01)
    stop = round(max(structural_stop, volatility_stop), 2)

    if entry <= stop:
        result["plan_error"] = "ENTRY_NOT_ABOVE_STOP"
        return result

    risk_per_share = entry - stop
    if risk_per_share <= 0:
        result["plan_error"] = "NON_POSITIVE_RISK"
        return result

    max_risk_dollars = account_size * max_risk_pct
    max_position_value = account_size * max_position_pct

    shares_by_risk = math.floor(max_risk_dollars / risk_per_share)
    shares_by_position = math.floor(max_position_value / entry)
    shares = min(shares_by_risk, shares_by_position)

    if shares <= 0:
        result["plan_error"] = "POSITION_SIZE_ZERO"
        return result

    target_1 = round(entry + (2.0 * risk_per_share), 2)
    target_2 = round(entry + (4.0 * risk_per_share), 2)
    max_loss = round(shares * risk_per_share, 2)

    if not (entry > stop and target_1 > entry and target_2 > target_1 and max_loss <= max_risk_dollars + 0.01):
        result["plan_error"] = "VALIDATION_FAILED"
        return result

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