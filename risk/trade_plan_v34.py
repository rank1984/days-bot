"""
DAYS-BOT V3.4 Trade Plan

Deterministic Python-only trade planning.

Gemini must never calculate or modify:
- Entry
- Stop
- Targets
- Shares
- Risk
"""

from typing import Dict, Any
import math


def _round_price(price: float) -> float:
    return round(float(price), 2)


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
        "risk_pct": max_risk_pct,
        "hold_type": "NO_TRADE",
        "plan_valid": False,
        "plan_error": None,
    }

    try:
        price = float(candidate.get("price", 0))
        pm_high = float(candidate.get("pm_high", 0))
        pm_vwap = float(candidate.get("pm_vwap", 0))

    except (TypeError, ValueError):
        result["plan_error"] = "INVALID_PRICE_DATA"
        return result

    if price <= 0 or pm_high <= 0 or pm_vwap <= 0:
        result["plan_error"] = "MISSING_MARKET_LEVELS"
        return result

    # ---------------------------------------------------------
    # Entry
    # ---------------------------------------------------------
    #
    # We require a breakout above PMH.
    #
    entry = _round_price(pm_high * 1.005)

    # ---------------------------------------------------------
    # Stop
    # ---------------------------------------------------------
    #
    # VWAP-based structural stop.
    #
    structural_stop = pm_vwap * 0.995

    # Conservative volatility proxy:
    # use distance between PMH and VWAP.
    range_proxy = abs(pm_high - pm_vwap)

    volatility_stop = entry - max(
        range_proxy,
        entry * 0.01,
    )

    # Use the tighter valid stop below entry.
    stop = max(
        structural_stop,
        volatility_stop,
    )

    stop = _round_price(stop)

    # ---------------------------------------------------------
    # Basic validation
    # ---------------------------------------------------------

    if entry <= stop:
        result["plan_error"] = "ENTRY_NOT_ABOVE_STOP"
        return result

    risk_per_share = entry - stop

    if risk_per_share <= 0:
        result["plan_error"] = "NON_POSITIVE_RISK"
        return result

    # ---------------------------------------------------------
    # Account risk
    # ---------------------------------------------------------

    max_risk_dollars = (
        account_size
        * max_risk_pct
    )

    # ---------------------------------------------------------
    # Position value cap
    # ---------------------------------------------------------

    max_position_value = (
        account_size
        * max_position_pct
    )

    shares_by_risk = math.floor(
        max_risk_dollars
        / risk_per_share
    )

    shares_by_position = math.floor(
        max_position_value
        / entry
    )

    shares = min(
        shares_by_risk,
        shares_by_position,
    )

    if shares <= 0:
        result["plan_error"] = "POSITION_SIZE_ZERO"
        return result

    # ---------------------------------------------------------
    # Targets
    # ---------------------------------------------------------

    target_1 = _round_price(
        entry + (2.0 * risk_per_share)
    )

    target_2 = _round_price(
        entry + (4.0 * risk_per_share)
    )

    max_loss = _round_price(
        shares * risk_per_share
    )

    # ---------------------------------------------------------
    # Final validation
    # ---------------------------------------------------------

    if not (
        entry > stop
        and target_1 > entry
        and target_2 > target_1
        and risk_per_share > 0
        and shares > 0
        and max_loss <= max_risk_dollars + 0.01
    ):
        result["plan_error"] = "TRADE_PLAN_VALIDATION_FAILED"
        return result

    # ---------------------------------------------------------
    # Valid plan
    # ---------------------------------------------------------

    result.update({
        "decision": "WAIT_BREAKOUT",
        "entry": entry,
        "stop": stop,
        "target_1": target_1,
        "target_2": target_2,
        "position_size": shares,
        "max_loss": max_loss,
        "risk_per_share": _round_price(risk_per_share),
        "hold_type": "MOMENTUM_15_90M",
        "plan_valid": True,
        "plan_error": None,
    })

    return result
