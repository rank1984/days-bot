"""
Calculations – Entry, Stop, TP, Net Profit, RR
"""
from typing import Dict, Any


def calculate_entry_stop_tp(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates entry, stop, tp1, tp2 based on PM High, VWAP, ATR (fallback).
    Returns dict with entry, stop, tp1, tp2, rr1, rr2, risk_share.
    """
    price = candidate.get('price', 0)
    pm_high = candidate.get('pm_high', price * 1.02)
    pm_vwap = candidate.get('pm_vwap', price)
    gap_pct = candidate.get('gap_pct', 0)

    # Entry = PM High + 0.5% buffer (breakout confirmation)
    entry = round(pm_high * 1.005, 2)

    # Stop = 5% below entry (conservative) – later replace with ATR-based
    stop = round(entry * 0.95, 2)

    # TP1 = Entry + 6%
    tp1 = round(entry * 1.06, 2)

    # TP2 = Entry + 12%
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


def calculate_net_profit(entry: float, target: float, shares: int, tax_rate: float = 0.25,
                         broker_fee_pct: float = 0.018, broker_fee_min: float = 1.50) -> Dict[str, Any]:
    """
    Calculates gross profit, fees, tax, net profit for a trade.
    """
    gross_profit = (target - entry) * shares
    gross_pct = ((target - entry) / entry) * 100 if entry > 0 else 0

    # Broker fee (max of min fee or percentage)
    trade_value = target * shares
    fee = max(broker_fee_min, trade_value * broker_fee_pct)

    tax = gross_profit * tax_rate if gross_profit > 0 else 0

    net_profit = gross_profit - fee - tax
    net_pct = (net_profit / (entry * shares)) * 100 if entry * shares > 0 else 0

    return {
        'gross_profit': round(gross_profit, 2),
        'gross_pct': round(gross_pct, 2),
        'fee': round(fee, 2),
        'tax': round(tax, 2),
        'net_profit': round(net_profit, 2),
        'net_pct': round(net_pct, 2),
    }
