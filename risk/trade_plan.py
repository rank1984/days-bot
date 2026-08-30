"""
risk/trade_plan.py – V3.1 Trade Plan Engine
============================================

Calculates:
- Entry (pm_high * 1.005)
- Stop (based on VWAP and PM range)
- Targets (2R and 4R)
- Position size (risk % of account)
- Hold time classification
- Decision (BUY / WAIT / NO TRADE)
"""

from typing import Dict, Any

# Default config values – will be overridden by main config later
ACCOUNT_SIZE = 5000.0
MAX_RISK_PER_TRADE = 0.005      # 0.5%
MAX_POSITION_VALUE_PCT = 0.20   # 20%


def build_trade_plan(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts a candidate dict from scanner and returns enriched trade plan.
    """
    ticker = candidate.get("ticker", "UNKNOWN")
    price = candidate.get("price", 0.0)
    pm_high = candidate.get("pm_high", 0.0)
    pm_vwap = candidate.get("pm_vwap", 0.0)
    pm_low = candidate.get("pm_low", 0.0)
    pm_volume = candidate.get("pm_volume", 0)
    score = candidate.get("opportunity_score", 0.0)
    grade = candidate.get("grade", "WATCH")

    # --- Basic validation ---
    if pm_high <= 0 or price <= 0 or pm_vwap <= 0:
        return _no_trade(candidate, reason="Missing PM data")

    pm_range = pm_high - pm_low
    if pm_range <= 0:
        pm_range = pm_high * 0.02  # fallback 2% range

    # --- Entry: 0.5% above PM High ---
    entry = pm_high * 1.005
    if entry <= price:
        # If already above entry, we might still wait for a pullback,
        # but we keep the entry level as trigger.
        pass

    # --- Stop: based on VWAP and range ---
    stop_candidate_1 = pm_vwap * 0.995
    stop_candidate_2 = entry - pm_range
    stop = max(stop_candidate_1, stop_candidate_2)
    # Ensure stop is below entry
    if stop >= entry:
        stop = entry - pm_range
    if stop >= entry:
        stop = entry * 0.98  # hard fallback 2% stop

    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return _no_trade(candidate, reason="Invalid stop")

    # --- Targets ---
    target_1 = entry + 2 * risk_per_share   # 2R
    target_2 = entry + 4 * risk_per_share   # 4R

    # --- Position Size ---
    risk_dollars = ACCOUNT_SIZE * MAX_RISK_PER_TRADE
    shares_by_risk = int(risk_dollars / risk_per_share)
    if shares_by_risk < 1:
        shares_by_risk = 0

    max_position_value = ACCOUNT_SIZE * MAX_POSITION_VALUE_PCT
    shares_by_value = int(max_position_value / entry)
    shares = min(shares_by_risk, shares_by_value)
    if shares < 0:
        shares = 0

    # --- Decision ---
    # BUY only if price is near entry and volume is decent.
    # For now, we use a simple rule: if price >= entry * 0.99 and volume > 100k -> BUY SETUP
    # But we'll output WAIT as default and let the user decide.
    if score >= 70 and pm_volume > 100000 and price >= entry * 0.99:
        decision = "BUY"
        decision_detail = "BUY SETUP – WAIT FOR TRIGGER"
    elif score >= 55:
        decision = "WAIT"
        decision_detail = "WAIT – Monitor for breakout"
    else:
        decision = "NO TRADE"
        decision_detail = "Score too low"

    # --- Hold Time ---
    if score >= 80 and candidate.get("pm_dist_signed", -100) >= 0:
        hold_type = "MOMENTUM"
        hold_min = 15
        hold_max = 90
    elif score >= 65:
        hold_type = "INTRADAY"
        hold_min = 30
        hold_max = 240
    else:
        hold_type = "WATCH"
        hold_min = 0
        hold_max = 0

    # --- Risk model ---
    risk_model = "PM_RANGE"  # we are not using ATR yet

    # --- Invalidation conditions (human-readable) ---
    invalidation = [
        "Breakout fails (price falls back below PM High)",
        "Price loses VWAP",
        "Stop is hit",
        "Volume collapses (below 50% of PM average)",
        "Trading halt",
        "Spread becomes abnormal (>2%)"
    ]

    # --- Build result ---
    result = {
        "ticker": ticker,
        "price": price,
        "entry": round(entry, 4),
        "stop": round(stop, 4),
        "target_1": round(target_1, 4),
        "target_2": round(target_2, 4),
        "risk_per_share": round(risk_per_share, 4),
        "position_shares": shares,
        "risk_dollars": round(risk_dollars, 2),
        "max_loss_dollars": round(shares * risk_per_share, 2),
        "max_position_value": round(shares * entry, 2),
        "risk_reward_1": round(target_1 / entry, 2),
        "risk_reward_2": round(target_2 / entry, 2),
        "hold_type": hold_type,
        "hold_min": hold_min,
        "hold_max": hold_max,
        "hold_overnight": False,
        "decision": decision,
        "decision_detail": decision_detail,
        "risk_model": risk_model,
        "invalidation_conditions": invalidation,
        "opportunity_score": score,
        "grade": grade,
        "pm_volume": pm_volume,
        "pm_high": pm_high,
        "pm_vwap": pm_vwap,
        "pm_range": round(pm_range, 4),
    }

    return result


def _no_trade(candidate: Dict[str, Any], reason: str) -> Dict[str, Any]:
    result = {
        "ticker": candidate.get("ticker", "UNKNOWN"),
        "decision": "NO TRADE",
        "decision_detail": reason,
        "entry": None,
        "stop": None,
        "target_1": None,
        "target_2": None,
        "risk_per_share": None,
        "position_shares": 0,
        "hold_type": "NONE",
        "hold_min": 0,
        "hold_max": 0,
        "hold_overnight": False,
        "risk_model": None,
        "invalidation_conditions": [],
        "opportunity_score": candidate.get("opportunity_score", 0),
    }
    return result
