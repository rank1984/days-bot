#!/usr/bin/env python3
"""
tests/test_cost_model.py — F7 pre-fix baseline.

Run BEFORE applying the F7 code change:
    python3 tests/test_cost_model.py
Expected: FAIL (compute_costs does not accept spread_pct)

After F7: PASS
"""
import sys
from pathlib import Path

import pandas as pd
import pytz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from evaluate_snapshots import (
    compute_costs,
    compute_gross_net,
    evaluate_horizon,
)

ET = pytz.timezone("America/New_York")

TESTS = []


def test(name):
    def deco(fn):
        TESTS.append((name, fn))
        return fn
    return deco


def make_df(rows, start_time="2026-09-28 09:30:00"):
    times = pd.date_range(
        start=pd.Timestamp(start_time, tz=ET),
        periods=len(rows),
        freq="1min",
    )
    df = pd.DataFrame(
        rows,
        columns=["Open", "High", "Low", "Close", "Volume"],
        index=times,
    )
    return df


@test("test_compute_costs_accepts_spread_pct")
def test_compute_costs_accepts_spread_pct():
    """F7: spread_pct is a required explicit parameter."""
    try:
        compute_costs(
            entry_fill=1.00,
            exit_fill=1.00,
            spread_pct=1.5,
            position_size=100,
        )
    except TypeError as e:
        raise AssertionError(
            f"compute_costs does not accept spread_pct: {e}"
        )


@test("test_cost_per_share_formula")
def test_cost_per_share_formula():
    """cost per share = spread_half*price + TICK_SIZE, per side."""
    result = compute_costs(
        entry_fill=1.00,
        exit_fill=1.00,
        spread_pct=1.5,
        position_size=100,
    )
    expected_entry = 1.00 * (1.5 / 2 / 100) + 0.01  # 0.0175
    expected_exit = expected_entry
    expected_total = expected_entry + expected_exit  # 0.035
    assert abs(result["entry_cost_ps"] - expected_entry) < 1e-9
    assert abs(result["exit_cost_ps"] - expected_exit) < 1e-9
    assert abs(result["total_per_share"] - expected_total) < 1e-9


@test("test_net_r_x2_computed")
def test_net_r_x2_computed():
    """net_r_x2 = gross_r - 2*cost_r."""
    result = compute_gross_net(
        entry_fill=1.00,
        exit_fill=1.10,
        risk_actual=0.10,
        spread_pct=1.5,
        position_size=100,
    )
    assert result["gross_r"] is not None
    assert abs(result["gross_r"] - 1.0) < 1e-9
    assert result["cost_r"] is not None
    assert result["net_r_x2"] is not None
    assert abs(result["net_r_x2"] - (result["gross_r"] - 2 * result["cost_r"])) < 1e-9


@test("test_no_embedded_slippage_in_exit")
def test_no_embedded_slippage_in_exit():
    """After F7, evaluate_horizon returns RAW fills — no slippage embedded."""
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.02, 0.94, 0.96, 10000),
    ])
    result = evaluate_horizon(
        df, trigger_idx=0, entry_fill=1.01, stop=0.95,
        t1=1.10, t2=1.20, end_idx=len(df) - 1,
    )
    assert abs(result["exit_fill"] - 0.95) < 1e-9, (
        f"exit_fill should be RAW 0.95, got {result['exit_fill']}"
    )


@test("test_no_embedded_slippage_t2")
def test_no_embedded_slippage_t2():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.12, 0.99, 1.11, 10000),
        (1.11, 1.22, 1.10, 1.21, 10000),
    ])
    result = evaluate_horizon(
        df, trigger_idx=0, entry_fill=1.01, stop=0.95,
        t1=1.10, t2=1.20, end_idx=len(df) - 1,
    )
    expected = 0.5 * 1.10 + 0.5 * 1.20  # 1.15, no slippage
    assert abs(result["exit_fill"] - expected) < 1e-9


def main():
    print("=" * 74)
    print("F7 — COST MODEL TESTS")
    print("=" * 74)
    passed = failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}")
            print(f"        {type(e).__name__}: {e}")
            failed += 1
    print()
    print(f"RESULTS: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())