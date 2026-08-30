"""
V3.2 Trade Plan – Entry, Stop, Targets, Position, Hold Time
"""
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT

def build_trade_plan(candidate, confirmed_price=None):
    price = candidate.get('price', 0)
    pm_high = candidate.get('pm_high', 0)
    pm_vwap = candidate.get('pm_vwap', 0)
    pm_low = candidate.get('pm_low', 0)
    pm_volume = candidate.get('pm_volume', 0)
    score = candidate.get('opportunity_score', 0)

    if not pm_high or not pm_vwap:
        return {"decision": "NO TRADE", "reason": "Missing PM data"}

    # Entry – 0.5% מעל PM High (או המחיר הנוכחי אם גבוה יותר)
    entry = max(pm_high * 1.005, price)  # אם כבר מעל, ניקח את המחיר הנוכחי

    # Stop – מבוסס על VWAP ו-range
    pm_range = pm_high - pm_low if pm_low else pm_high * 0.02
    stop_candidate1 = pm_vwap * 0.995
    stop_candidate2 = entry - pm_range
    stop = max(stop_candidate1, stop_candidate2)
    if stop >= entry:
        stop = entry - pm_range
    if stop >= entry:
        stop = entry * 0.98

    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return {"decision": "NO TRADE", "reason": "Invalid stop"}

    # Targets
    target_1 = entry + 2 * risk_per_share
    target_2 = entry + 4 * risk_per_share

    # Position Size
    risk_dollars = ACCOUNT_SIZE * MAX_RISK_PER_TRADE_V31
    shares_by_risk = int(risk_dollars / risk_per_share)
    if shares_by_risk < 1:
        shares_by_risk = 0
    max_position_value = ACCOUNT_SIZE * MAX_POSITION_VALUE_PCT
    shares_by_value = int(max_position_value / entry)
    shares = min(shares_by_risk, shares_by_value)
    if shares < 0:
        shares = 0

    # Decision
    if score >= 70 and pm_volume > 100000 and price >= entry * 0.99:
        decision = "BUY SETUP"
        decision_detail = "WAIT FOR BREAKOUT"
    elif score >= 55:
        decision = "WAIT"
        decision_detail = "Monitor for breakout"
    else:
        decision = "NO TRADE"
        decision_detail = "Score too low"

    # Hold Time
    if score >= 80 and candidate.get('pm_dist_signed', -100) >= 0:
        hold_type = "MOMENTUM"
        hold_min, hold_max = 15, 90
    elif score >= 65:
        hold_type = "INTRADAY"
        hold_min, hold_max = 30, 240
    else:
        hold_type = "WATCH"
        hold_min, hold_max = 0, 0

    return {
        "entry": round(entry, 4),
        "stop": round(stop, 4),
        "target_1": round(target_1, 4),
        "target_2": round(target_2, 4),
        "risk_per_share": round(risk_per_share, 4),
        "position_shares": shares,
        "risk_dollars": round(risk_dollars, 2),
        "risk_reward_1": round((target_1 - entry) / risk_per_share, 1),
        "risk_reward_2": round((target_2 - entry) / risk_per_share, 1),
        "hold_type": hold_type,
        "hold_min": hold_min,
        "hold_max": hold_max,
        "decision": decision,
        "decision_detail": decision_detail,
        "invalidation_conditions": [
            "Falls below VWAP",
            "Spread > 2%",
            "Trading halt",
            "Breakout fails"
        ]
    }
