#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6.4 — Cost Analyzer

Reads outcomes and computes cost/tax decomposition.
Writes ONLY to the new *_pct and *_score columns.
NEVER touches net_r, net_r_status, or event_rank.

V5.0.6.4 — schema-aware:
  - position_size lives on snapshots, not outcomes -> JOIN.
  - All optional columns are probed defensively.
  - Never crashes on schema drift.

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


def _cols(cur, table):
    try:
        return {r[1] for r in cur.execute("PRAGMA table_info(" + table + ")")}
    except sqlite3.OperationalError:
        return set()


def _estimated_slippage_pct(spread_pct):
    """
    Slippage model:
      spread < 2%  -> 0.5%
      spread 2-5%  -> 1.0%
      spread > 5%  -> 2.0%
    """
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


def _compute_net_edge_score(gross_edge_0_100, net_after_tax_pct, gross_pct):
    """
    Composite score. If net <= 0, score is 0.
    Otherwise, scaled by the fraction of gross retained after costs.
    """
    if gross_edge_0_100 is None or gross_pct is None or gross_pct <= 0:
        return 0.0
    if net_after_tax_pct is None or net_after_tax_pct <= 0:
        return 0.0
    retention = net_after_tax_pct / gross_pct
    if retention > 1.0:
        retention = 1.0
    if retention < 0.0:
        retention = 0.0
    return round(gross_edge_0_100 * retention, 2)


def process_row(row, free_trades_remaining=BLINK_FREE_TRADES_PER_MONTH):
    """
    Compute cost columns for a single row.
    Returns dict of column updates. Never touches net_r/net_r_status.
    """
    updates = {}

    # --- Inputs ---
    raw_fill = _safe_float(row["raw_fill"])
    exit_price = _safe_float(row["exit_price"])
    position_size = int(row["position_size"]) if row["position_size"] else 0
    spread_trigger = _safe_float(row["spread_pct_used"])

    if raw_fill is None or raw_fill <= 0:
        return {}

    position_value = raw_fill * position_size if position_size > 0 else None

    # --- Spread decomposition ---
    # Conservative: assume exit spread == entry spread.
    spread_at_trigger = spread_trigger if spread_trigger is not None else None
    spread_at_exit = spread_trigger if spread_trigger is not None else None

    round_trip_spread = None
    if spread_at_trigger is not None and spread_at_exit is not None:
        # Full spread, not half. Round-trip = entry ask + exit bid
        round_trip_spread = spread_at_trigger + spread_at_exit

    # --- Slippage ---
    slip_pct = _estimated_slippage_pct(spread_at_trigger)

    # --- Blink fee ---
    fee_dollars, fee_pct = _blink_fee(
        raw_fill, position_size, position_value, free_trades_remaining
    )

    # --- Gross target % ---
    t1_used = _safe_float(row["t1_used"])
    gross_target_pct = None
    if t1_used is not None and raw_fill > 0:
        gross_target_pct = ((t1_used - raw_fill) / raw_fill) * 100.0

    # --- Net before tax % ---
    net_before_tax_pct = None
    realized_pct = None
    if exit_price is not None and exit_price > 0:
        realized_pct = ((exit_price - raw_fill) / raw_fill) * 100.0
        if round_trip_spread is not None:
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
    gross_r_val = _safe_float(row["gross_r"])
    gross_edge_0_100 = None
    if gross_r_val is not None:
        gross_edge_0_100 = max(0.0, min(100.0, gross_r_val * 50.0))

    net_edge_score = _compute_net_edge_score(
        gross_edge_0_100,
        net_after_tax_pct,
        realized_pct,
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

    # Schema probe
    outcomes_cols = _cols(cur, "outcomes")
    snapshots_cols = _cols(cur, "snapshots")

    # Required columns in outcomes
    required_outcomes = {"outcome_id", "raw_fill", "exit_price",
                         "spread_pct_used", "t1_used", "gross_r"}
    missing_outcomes = required_outcomes - outcomes_cols
    if missing_outcomes:
        print(f"  MISSING outcomes columns: {sorted(missing_outcomes)}")
        print("  Cannot compute costs. Exiting.")
        conn.close()
        return 0

    # position_size is on snapshots
    has_position_size = "position_size" in snapshots_cols
    if not has_position_size:
        print("  snapshots.position_size missing — will use NULL (fee=0)")
    print(f"  position_size on snapshots: {has_position_size}")

    # Query with JOIN
    # outcome -> snapshot_id is on outcomes
    # position_size is on snapshots
    query = """
        SELECT
            o.outcome_id,
            o.raw_fill,
            o.exit_price,
            o.spread_pct_used,
            o.t1_used,
            o.gross_r,
            s.position_size AS position_size
        FROM outcomes o
        LEFT JOIN snapshots s
            ON s.snapshot_id = o.snapshot_id
        WHERE o.raw_fill IS NOT NULL
          AND o.exit_price IS NOT NULL
    """

    try:
        rows = cur.execute(query).fetchall()
    except sqlite3.OperationalError as e:
        print(f"  Query failed: {e}")
        conn.close()
        return 0

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
        try:
            cur.execute(
                f"UPDATE outcomes SET {set_clause} WHERE outcome_id = ?",
                values,
            )
            updated += 1
        except sqlite3.OperationalError as e:
            print(f"  ! update failed for outcome_id={row['outcome_id']}: {e}")
            skipped += 1

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