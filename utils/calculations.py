import math
import utils.config as cfg

# Safe getter helper to guarantee no ImportError ever stops execution
def _get_cfg(attr_name, default_val):
    return getattr(cfg, attr_name, default_val)


def calculate_entry_stop_tp(candidate: dict) -> dict:
    price = candidate.get('price', 0.0)
    pm_high = candidate.get('pm_high', price)
    
    entry = max(price, pm_high) if pm_high else price
    stop = entry * 0.96  # 4% stop loss default
    
    risk = entry - stop
    tp1 = entry + (risk * 1.5)  # 1:1.5 RR
    tp2 = entry + (risk * 2.5)  # 1:2.5 RR
    
    rr1 = (tp1 - entry) / risk if risk > 0 else 0
    rr2 = (tp2 - entry) / risk if risk > 0 else 0
    
    return {
        'entry': round(entry, 2),
        'stop': round(stop, 2),
        'tp1': round(tp1, 2),
        'tp2': round(tp2, 2),
        'rr1': round(rr1, 2),
        'rr2': round(rr2, 2)
    }


def calculate_position_size(entry: float, stop: float, equity: float, max_risk_pct: float) -> int:
    if entry <= 0 or stop >= entry or equity <= 0:
        return 0
    
    risk_per_share = entry - stop
    max_risk_amount = equity * max_risk_pct
    shares = math.floor(max_risk_amount / risk_per_share)
    
    return max(shares, 0)


def calculate_net_profit(
    entry: float,
    exit_price: float,
    shares: int,
    monthly_ops_used: int = 0,
    monthly_shares_used: int = 0
) -> dict:
    if shares <= 0 or entry <= 0:
        return {'gross_pnl': 0.0, 'net_pnl': 0.0, 'net_pct': 0.0, 'fees': 0.0}

    fee_per_share = _get_cfg('FEE_PER_SHARE', 0.005)
    fee_min = _get_cfg('FEE_MIN', 1.0)
    fee_max_pct = _get_cfg('FEE_MAX_PCT', 0.01)
    slippage_pct = _get_cfg('SLIPPAGE_PCT', 0.001)

    position_value = entry * shares
    gross_pnl = (exit_price - entry) * shares

    # Calculate Fees for both Entry and Exit
    raw_fee = max(shares * fee_per_share, fee_min)
    capped_fee = min(raw_fee, position_value * fee_max_pct)
    total_fees = capped_fee * 2  # Entry + Exit

    # Slippage
    total_slippage = position_value * slippage_pct * 2

    net_pnl = gross_pnl - total_fees - total_slippage
    net_pct = (net_pnl / position_value) * 100.0 if position_value > 0 else 0.0

    return {
        'gross_pnl': round(gross_pnl, 2),
        'net_pnl': round(net_pnl, 2),
        'net_pct': round(net_pct, 2),
        'fees': round(total_fees + total_slippage, 2)
    }
