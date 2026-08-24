"""
Calculations – Entry, Stop, TP, Net Profit (FIXED)
"""
from typing import Dict, Any

# ── BROKER FEES (BLINK) ──────────────────────────────────
# נניח עמלה per-side (קנייה + מכירה)
def calculate_fee(trade_value: float, fee_pct: float = 0.018, fee_min: float = 1.50) -> float:
    """מחשב עמלה לעסקה בודדת (buy OR sell)"""
    if trade_value <= 0:
        return 0.0
    fee = max(fee_min, trade_value * fee_pct)
    return min(fee, trade_value * 0.018)  # capped at 1.8%


def calculate_entry_stop_tp(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates entry, stop, tp1, tp2 based on PM High and current price.
    Entry = max(trigger_price, current_price) – same as watchlist_manager.
    """
    price = candidate.get('price', 0)
    pm_high = candidate.get('pm_high', price * 1.02)
    trigger_price = round(pm_high * 1.005, 2)

    # ====== FIX: Same logic as watchlist_manager ======
    entry = trigger_price if trigger_price > price else price
    entry = round(entry, 2)

    # Stop = 5% below entry
    stop = round(entry * 0.95, 2)

    # TP1 = entry + 6%
    tp1 = round(entry * 1.06, 2)

    # TP2 = entry + 12%
    tp2 = round(entry * 1.12, 2)

    risk_share = entry - stop
    rr1 = round((tp1 - entry) / risk_share, 2) if risk_share > 0 else 0
    rr2 = round((tp2 - entry) / risk_share, 2) if risk_share > 0 else 0

    return {
        'entry': entry,
        'stop': stop,
        'tp1': tp1,
        'tp2': tp2,
        'risk_share': risk_share,
        'rr1': rr1,
        'rr2': rr2,
    }


def calculate_net_profit(
    entry: float,
    target: float,
    shares: int,
    tax_rate: float = 0.25,
    fee_pct: float = 0.018,
    fee_min: float = 1.50
) -> Dict[str, Any]:
    """
    Calculates gross profit, fees (entry + exit), tax on net profit, and net profit.
    """
    entry_value = entry * shares
    exit_value = target * shares
    gross_profit = exit_value - entry_value
    gross_pct = ((target - entry) / entry) * 100 if entry > 0 else 0

    # ====== FIX: Entry fee + Exit fee ======
    entry_fee = calculate_fee(entry_value, fee_pct, fee_min)
    exit_fee = calculate_fee(exit_value, fee_pct, fee_min)
    total_fee = entry_fee + exit_fee

    # ====== FIX: Tax on net profit (profit - fees) ======
    net_profit_before_tax = gross_profit - total_fee
    tax = net_profit_before_tax * tax_rate if net_profit_before_tax > 0 else 0
    net_profit = net_profit_before_tax - tax
    net_pct = (net_profit / entry_value) * 100 if entry_value > 0 else 0

    return {
        'gross_profit': round(gross_profit, 2),
        'gross_pct': round(gross_pct, 2),
        'entry_fee': round(entry_fee, 2),
        'exit_fee': round(exit_fee, 2),
        'total_fee': round(total_fee, 2),
        'tax': round(tax, 2),
        'net_profit': round(net_profit, 2),
        'net_pct': round(net_pct, 2),
    }
