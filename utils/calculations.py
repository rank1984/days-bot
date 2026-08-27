from typing import Dict, Any
from utils.config import (
    FEE_PER_SHARE,
    FEE_MIN,
    FEE_MAX_PCT,
    FREE_OPS_QUOTA,
    FREE_SHARES_QUOTA,
    FREE_OPS_BUFFER,
    FREE_SHARES_BUFFER,
    MANUAL_OPS_OFFSET,
    MANUAL_SHARES_OFFSET,
)

def calculate_fee(
    shares: int,
    price: float,
    monthly_ops_used: int = 0,
    monthly_shares_used: int = 0,
    fee_per_share: float = FEE_PER_SHARE,
    fee_min: float = FEE_MIN,
    max_pct_cap: float = FEE_MAX_PCT
) -> float:
    """
    Calculates exact BLINK broker execution fee with strict AND safety buffer checks.
    """
    if shares <= 0 or price <= 0:
        return 0.0

    effective_ops_used = monthly_ops_used + MANUAL_OPS_OFFSET
    effective_shares_used = monthly_shares_used + MANUAL_SHARES_OFFSET

    effective_ops_limit = FREE_OPS_QUOTA - FREE_OPS_BUFFER       # 8 ops
    effective_shares_limit = FREE_SHARES_QUOTA - FREE_SHARES_BUFFER # 800 shares

    is_ops_within_buffer = effective_ops_used < effective_ops_limit
    is_shares_within_buffer = (effective_shares_used + shares) <= effective_shares_limit

    # Strict AND logic against conservative buffers
    if is_ops_within_buffer and is_shares_within_buffer:
        return 0.0

    trade_value = shares * price
    raw_fee = shares * fee_per_share
    capped_fee = min(raw_fee, trade_value * max_pct_cap)

    return round(max(fee_min, capped_fee), 4)


def calculate_position_size(entry: float, stop: float, equity: float, max_risk_pct: float) -> int:
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0 or equity <= 0:
        return 0
    max_risk_amount = equity * max_risk_pct
    return int(max_risk_amount / risk_per_share)


def calculate_entry_stop_tp(candidate: Dict[str, Any]) -> Dict[str, Any]:
    price = candidate.get('price', 0.0)
    pm_low = candidate.get('pm_low', price * 0.95)

    entry = round(price, 2)
    stop = round(pm_low, 2) if pm_low < entry else round(entry * 0.95, 2)
    risk = entry - stop

    tp1 = round(entry + (risk * 1.5), 2)
    tp2 = round(entry + (risk * 3.0), 2)

    rr1 = round((tp1 - entry) / risk, 2) if risk > 0 else 0.0
    rr2 = round((tp2 - entry) / risk, 2) if risk > 0 else 0.0

    return {
        'entry': entry,
        'stop': stop,
        'tp1': tp1,
        'tp2': tp2,
        'rr1': rr1,
        'rr2': rr2,
    }


def calculate_net_profit(
    entry: float,
    exit_price: float,
    shares: int,
    monthly_ops_used: int = 0,
    monthly_shares_used: int = 0
) -> Dict[str, float]:
    if shares <= 0 or entry <= 0:
        return {'gross_profit': 0.0, 'fees': 0.0, 'net_profit': 0.0, 'net_pct': 0.0}

    buy_value = entry * shares
    sell_value = exit_price * shares
    gross_profit = sell_value - buy_value

    buy_fee = calculate_fee(shares, entry, monthly_ops_used, monthly_shares_used)
    
    updated_ops = monthly_ops_used + 1
    updated_shares = monthly_shares_used + shares
    sell_fee = calculate_fee(shares, exit_price, updated_ops, updated_shares)

    total_fees = buy_fee + sell_fee
    net_profit = gross_profit - total_fees
    net_pct = (net_profit / buy_value) * 100 if buy_value > 0 else 0.0

    return {
        'gross_profit': round(gross_profit, 2),
        'fees': round(total_fees, 2),
        'net_profit': round(net_profit, 2),
        'net_pct': round(net_pct, 2)
    }
