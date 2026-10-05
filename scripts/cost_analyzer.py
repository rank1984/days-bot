#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6.4 — Cost Analyzer

Reads outcomes and computes cost/tax decomposition.
Writes ONLY to the new *_pct and *_score columns.
NEVER touches net_r, net_r_status, or event_rank.

Run: python3 scripts/cost_analyzer.py
"""
import os
import sys
import sqlite3
import math

DB_PATH = "data/alerts.db"

BLINK_COST_VERSION = "V6-COST-1"
BLINK_FREE_TRADES_PER_MONTH = 10
BLINK_FEE_PER_SHARE = 0.01
BLINK_MIN_FEE = 1.50
BLINK_MAX_FEE_PCT = 1.8

TAX_RATE = 0.25

# Slippage model:
#   spread < 2%  -> 0.5%
#   spread 2-5%  -> 1.0%
#   spread > 5%  -> 2.0%
def _estimated_slippage_pct(spread_pct):
    if spread_pct is None:
        return 0.5
    if spread_pct < 2.0:
        return 0.5
    if spread_pct < 5.0:
        return 1.0
    return 2.0


def _blink_fee(price, shares, position_value, free_trades_remaining):
    """
    Returns (fee_dollars, fee_pct).
    Blink model:
      - First 10 trades per month: $0
      - Otherwise: $0.01/share, min $1.50, max 1.8% of trade value
    """
    if position_value is None or position_value <= 0:
        return (0.0, 0.0)

    if free_trades_remaining > 0:
        return (0.0, 0.0)

    shares = int(shares or 0)
    if shares <= 0:
        return (0.0, 0.0)

    fee = shares * BLINK_FEE_PER_SHARE
    if fee < BLINK_MIN_FEE:
        fee = BLINK_MIN_FEE
    max_fee = position_value * (BLINK_MAX_FEE_PCT / 100.0)
    if fee > max_fee:
        fee = max_fee

    fee_pct = (fee / position_value) * 100.0
    return (round(fee, 4), round(fee_pct, 4))


def _safe_float(v, default=None):
    try:
        if v is None:
            return default
        x = float(v)
        if not math.isfinite(x):
            return default
        return x
    except (TypeError, ValueError):
        return default


def _compute_net_edge_score(gross_edge_0_100, net_after_tax_pct, gross_pct):
    """
    Composite score. If net is <= 0, score is 0.
    Otherwise, scaled by the fraction of gross retained after costs.
    """
    if gross_edge_0_100 is None or gross_pct is None or gross_pct <= 0:
        return 0.0
    if net_after_tax_pct is None or net_after_tax_pct <= 0:
        return 0.0
    retention = net_after_tax_pct / gross_pct
    if retention > 1.0:
        retention = 1.0
    return round(gross_edge_0_100 * retention, 2)


def process_row(row, free_trades_remaining=BLINK_FREE_TRADES_PER_MONTH):
    """
    Compute cost columns for a single outcome row.
    Returns dict of column updates. Never touches net_r/net_r_status.
    """
    updates = {}

    # --- Inputs ---
    raw_fill = _safe_float(row["raw_fill"])
    exit_price = _safe_float(row["exit_price"])
    position_size = int(row["position_size"]) if row["position_size"] else 0
    entry_price = _safe_float(row["raw_fill"])  # same as raw_fill
    spread_trigger = _safe_float(row["spread_pct_used"])

    if raw_fill is None or raw_fill <= 0:
        return {}

    position_value = raw_fill * position_size if position_size > 0 else None

    # --- Spread decomposition ---
    # Conservative: assume exit spread == entry spread (we don't have
    # historical exit quotes yet).
    spread_at_trigger = spread_trigger if spread_trigger is not None else None
    spread_at_exit = spread_trigger if spread_trigger is not None else None

    round_trip_spread = None
    if spread_at_trigger is not None and spread_at_exit is not None:
        round_trip_spread = spread_at_trigger + spread_at_exit

    # --- Slippage ---
    slip_pct = _estimated_slippage_pct(spread_at_trigger)

    # --- Blink fee ---
    fee_dollars, fee_pct = _blink_fee(
        raw_fill, position_size, position_value, free_trades_remaining
    )

    # --- Gross target % ---
    # Distance to T1 (2R) as % of entry.
    t1_used = _safe_float(row["t1_used"])
    gross_target_pct = None
    if t1_used is not None and raw_fill is not None and raw_fill > 0:
        gross_target_pct = ((t1_used - raw_fill) / raw_fill) * 100.0

    # --- Net before tax % ---
    # Realized exit vs entry, minus full round-trip costs
    net_before_tax_pct = None
    if exit_price is not None and round_trip_spread is not None:
        realized_pct = ((exit_price - raw_fill) / raw_fill) * 100.0
        total_cost_pct = round_trip_spread + slip_pct + (fee_pct or 0.0)
        net_before_tax_pct = realized_pct - total_cost_pct

    # --- Net after tax % ---
    net_after_tax_pct = None
    if net_before_tax_pct is not None:
        if net_before_tax_pct > 0:
            net_after_tax_pct = net_before_tax_pct * (1.0 - TAX_RATE)
        else:
            net_after_tax_pct = net_before_tax_pct  # loss not taxed

    # --- Net edge score ---
    # Input "gross_edge" = the gross_r in 0-100 scale
    gross_r_val = _safe_float(row["gross_r"])
    gross_edge_0_100 = None
    if gross_r_val is not None:
        # Map R to a 0-100 scale: 2R = 100, clamp at 0
        gross_edge_0_100 = max(0.0, min(100.0, gross_r_val * 50.0))

    net_edge_score = _compute_net_edge_score(
        gross_edge_0_100,
        net_after_tax_pct,
        ((exit_price - raw_fill) / raw_fill * 100.0) if (exit_price and raw_fill) else None,
    )

    # --- Assemble ---
    updates["spread_at_trigger_pct"] = spread_at_trigger
    updates["spread_at_exit_pct"] = spread_at_exit
    updates["round_trip_spread_pct"] = round_trip_spread
    updates["estimated_slippage_pct"] = slip_pct
    updates["position_value"] = round(position_value, 2) if position_value else None
    updates["blink_fee_dollars"] = fee_dollars
    updates["blink_fee_pct"] = fee_pct
    updates["gross_target_pct"] = round(gross_target_pct, 4) if gross_target_pct is not None else None
    updates["net_before_tax_pct"] = round(net_before_tax_pct, 4) if net_before_tax_pct is not None else None
    updates["net_after_tax_pct"] = round(net_after_tax_pct, 4) if net_after_tax_pct is not None else None
    updates["net_edge_score"] = net_edge_score
    updates["blink_cost_version"] = BLINK_COST_VERSION

    return updates


def main():
    if not os.path.exists(DB_PATH):
        print("DB not found at " + DB_PATH)
        return 0

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print()
    print("=" * 74)
    print("COST ANALYZER — " + BLINK_COST_VERSION)
    print("=" * 74)

    rows = cur.execute("""
        SELECT outcome_id, raw_fill, exit_price, position_size,
               spread_pct_used, t1_used, gross_r
        FROM outcomes
        WHERE raw_fill IS NOT NULL
          AND exit_price IS NOT NULL
    """).fetchall()

    print(f"  outcomes to process: {len(rows)}")
    updated = 0
    skipped = 0

    for row in rows:
        updates = process_row(row)
        if not updates:
            skipped += 1
            continue

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [row["outcome_id"]]
        cur.execute(
            f"UPDATE outcomes SET {set_clause} WHERE outcome_id = ?",
            values,
        )
        updated += 1

    conn.commit()
    conn.close()

    print(f"  updated:  {updated}")
    print(f"  skipped:  {skipped} (insufficient data)")
    print("=" * 74)
    print("COST ANALYZER COMPLETE")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())