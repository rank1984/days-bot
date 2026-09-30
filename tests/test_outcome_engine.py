#!/usr/bin/env python3
"""
tests/test_outcome_engine.py

Standalone test runner — no pytest required.
Run:  python3 tests/test_outcome_engine.py

Exit code 0 = all tests pass
Exit code 1 = at least one test failed

V5.0.6.3 — updated for:
  - PR-FIX-1: stop uses PM VWAP (no SLIPPAGE_PCT constant)
  - PR-FIX-2/3: weighted partial exits (50/50)
  - PR-FIX-5: spread fallback removed
  - Cost model F7: raw fills only, costs computed separately
"""
import sys
import traceback
from pathlib import Path

import pandas as pd
import pytz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from evaluate_snapshots import (
    evaluate_horizon,
    detect_pmh_breakout,
    compute_costs,
    compute_gross_net,
    NET_R_STATUS_VALID,
    NET_R_STATUS_NON_EXECUTABLE,
    TICK_SIZE,
)

ET = pytz.timezone("America/New_York")


# ---------------------------------------------------------------------
# Test runner harness
# ---------------------------------------------------------------------

class TestFailure(Exception):
    pass


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
    df.index.name = "timestamp"
    return df


TESTS = []


def test(name):
    def deco(fn):
        TESTS.append((name, fn))
        return fn
    return deco


# =====================================================================
# TEST 1 — Stop wins when both stop and T1 touched on same bar
#
# Raw fills only (F7). Exit is at stop (0.95), no embedded slippage.
# =====================================================================

@test("test_stop_first_same_bar")
def test_stop_first_same_bar():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.15, 0.93, 1.10, 10000),
    ])

    result = evaluate_horizon(
        df,
        trigger_idx=0,
        entry_fill=1.01,
        stop=0.95,
        t1=1.10,
        t2=1.20,
        end_idx=len(df) - 1,
    )

    assert result["status"] == NET_R_STATUS_VALID, result["status"]
    assert result["exit_reason"] == "STOP_HIT", result["exit_reason"]
    # Raw fill at stop (F7: no embedded slippage)
    assert abs(result["exit_fill"] - 0.95) < 0.001, (
        f"exit_fill={result['exit_fill']} expected=0.95"
    )


# =====================================================================
# TEST 2 — Gap-down: fill at open, not at stop  (F2)
#
# Bar 2 opens at 0.85, below stop 0.95 -> exit_fill = 0.85 (raw open).
# =====================================================================

@test("test_gap_down_below_stop")
def test_gap_down_below_stop():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (0.85, 0.90, 0.80, 0.87, 10000),
    ])

    result = evaluate_horizon(
        df,
        trigger_idx=0,
        entry_fill=1.01,
        stop=0.95,
        t1=1.10,
        t2=1.20,
        end_idx=len(df) - 1,
    )

    assert result["status"] == NET_R_STATUS_VALID, result["status"]
    assert result["exit_reason"] == "STOP_HIT", result["exit_reason"]
    # Gap-down: raw open (0.85), not stop (0.95)
    assert abs(result["exit_fill"] - 0.85) < 0.001, (
        f"Gap-down fill must be at open (0.85), got {result['exit_fill']} — F2 not applied"
    )


# =====================================================================
# TEST 3 — No next bar: NON_EXECUTABLE
# =====================================================================

@test("test_no_next_bar_non_executable")
def test_no_next_bar_non_executable():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
    ])

    result = evaluate_horizon(
        df,
        trigger_idx=0,
        entry_fill=1.01,
        stop=0.95,
        t1=1.10,
        t2=1.20,
        end_idx=len(df) - 1,
    )

    assert result["status"] == NET_R_STATUS_NON_EXECUTABLE, result["status"]
    assert result["exit_reason"] == "NOT_EXECUTABLE", result["exit_reason"]


# =====================================================================
# TEST 4 — T1 and T2 same bar: T2 waits for next bar
#
# T1 hit on bar 2 (high 1.25). T2 requires half_exited; T2 first fires
# on bar 3 when high >= 1.20.
# =====================================================================

@test("test_t1_and_t2_same_bar_conservative")
def test_t1_and_t2_same_bar_conservative():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.25, 0.99, 1.22, 10000),
        (1.22, 1.23, 1.10, 1.15, 10000),
    ])

    result = evaluate_horizon(
        df,
        trigger_idx=0,
        entry_fill=1.01,
        stop=0.95,
        t1=1.10,
        t2=1.20,
        end_idx=len(df) - 1,
    )

    assert result["status"] == NET_R_STATUS_VALID, result["status"]
    assert result["exit_reason"] == "T2_HIT", result["exit_reason"]


# =====================================================================
# TEST 5 — Normal stop hit (raw fill)
# =====================================================================

@test("test_normal_stop_hit")
def test_normal_stop_hit():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.02, 0.94, 0.96, 10000),
    ])

    result = evaluate_horizon(
        df,
        trigger_idx=0,
        entry_fill=1.01,
        stop=0.95,
        t1=1.10,
        t2=1.20,
        end_idx=len(df) - 1,
    )

    assert result["exit_reason"] == "STOP_HIT", result["exit_reason"]
    # Bar open = 1.00 > stop 0.95 -> fill at stop (raw 0.95)
    assert abs(result["exit_fill"] - 0.95) < 0.001, (
        f"exit_fill={result['exit_fill']} expected=0.95"
    )


# =====================================================================
# TEST 6 — Normal T2 hit: weighted 50/50 raw
# =====================================================================

@test("test_normal_t2_hit")
def test_normal_t2_hit():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.12, 0.99, 1.11, 10000),
        (1.11, 1.22, 1.10, 1.21, 10000),
    ])

    result = evaluate_horizon(
        df,
        trigger_idx=0,
        entry_fill=1.01,
        stop=0.95,
        t1=1.10,
        t2=1.20,
        end_idx=len(df) - 1,
    )

    assert result["exit_reason"] == "T2_HIT", result["exit_reason"]
    expected_exit = 0.5 * 1.10 + 0.5 * 1.20  # = 1.15
    assert abs(result["exit_fill"] - expected_exit) < 0.001, (
        f"exit_fill={result['exit_fill']} expected={expected_exit}"
    )


# =====================================================================
# TEST 7 — detect_pmh_breakout uses CLOSE (not High)  (F5)
# =====================================================================

@test("test_detect_pmh_breakout_uses_close")
def test_detect_pmh_breakout_uses_close():
    df = make_df([
        (1.00, 1.02, 0.98, 0.99, 10000),
    ])

    result = detect_pmh_breakout(df, pm_high=1.00, buffer=0.01)

    assert result is None, (
        "detect_pmh_breakout fired on High-touch — spec requires Close. "
        "F5 not applied."
    )


# =====================================================================
# TEST 8 — compute_costs accepts spread_pct  (F7)
# =====================================================================

@test("test_compute_costs_accepts_spread_pct")
def test_compute_costs_accepts_spread_pct():
    try:
        costs = compute_costs(
            entry_fill=1.00,
            exit_fill=1.00,
            spread_pct=1.5,
            position_size=100,
        )
    except TypeError as e:
        raise TestFailure(
            f"compute_costs does not accept spread_pct: {e} — F7 not applied"
        )

    # Sanity: total cost > 0 and matches formula
    # spread_half = 0.0075; entry_cost = 1.00*0.0075 + 0.01 = 0.0175
    # exit_cost = 0.0175; total = 0.035
    assert abs(costs["total_per_share"] - 0.035) < 0.0001, costs


# =====================================================================
# TEST 9 — R denominator uses risk_actual (F1)
#
# compute_gross_net now expects `risk_actual`, not `risk_per_share`.
# =====================================================================

@test("test_r_denominator_contract")
def test_r_denominator_contract():
    gap_up_entry = 1.50
    stop_used = 1.00
    correct_risk = gap_up_entry - stop_used  # 0.50

    correct = compute_gross_net(
        entry_fill=gap_up_entry,
        exit_fill=stop_used,
        risk_actual=correct_risk,
        spread_pct=1.5,
    )
    correct_r = correct["gross_r"]

    buggy = compute_gross_net(
        entry_fill=gap_up_entry,
        exit_fill=stop_used,
        risk_actual=0.02,  # tiny risk -> huge negative R
        spread_pct=1.5,
    )
    buggy_r = buggy["gross_r"]

    assert -1.5 < correct_r < -0.5, f"correct_r={correct_r}"
    assert buggy_r < -10, f"buggy_r={buggy_r}"


# =====================================================================
# TEST 10 — PR-FIX-2: T1 hit then BE stop -> weighted 50/50
#
# New behavior (V5.0.6.3): half exits at T1, remaining half exits at BE.
# exit_fill = 0.5*T1 + 0.5*BE, exit_reason = "STOP_BE_AFTER_T1"
# =====================================================================

@test("test_partial_exit_be_after_t1")
def test_partial_exit_be_after_t1():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),  # trigger bar
        (1.01, 1.03, 0.98, 1.00, 10000),  # entry bar (open=1.01)
        (1.00, 1.12, 0.99, 1.11, 10000),  # T1 hits (high=1.12)
        (1.11, 1.12, 1.00, 1.05, 10000),  # low=1.00 <= BE=1.01 -> stop
    ])

    result = evaluate_horizon(
        df,
        trigger_idx=0,
        entry_fill=1.01,
        stop=0.95,
        t1=1.10,
        t2=1.20,
        end_idx=len(df) - 1,
    )

    assert result["status"] == NET_R_STATUS_VALID, result["status"]
    assert result["exit_reason"] == "STOP_BE_AFTER_T1", result["exit_reason"]
    # Weighted: 0.5 * 1.10 + 0.5 * 1.01 = 1.055
    expected = 0.5 * 1.10 + 0.5 * 1.01
    assert abs(result["exit_fill"] - expected) < 0.001, (
        f"exit_fill={result['exit_fill']} expected={expected} — PR-FIX-2 not applied"
    )


# =====================================================================
# TEST 11 — PR-FIX-3: T1 hit then horizon end -> weighted 50/50
#
# New behavior (V5.0.6.3): exit_reason = "HORIZON_END_AFTER_T1"
# exit_fill = 0.5*T1 + 0.5*close
# =====================================================================

@test("test_partial_exit_horizon_after_t1")
def test_partial_exit_horizon_after_t1():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),  # trigger bar
        (1.01, 1.03, 0.98, 1.00, 10000),  # entry bar
        (1.00, 1.12, 0.99, 1.11, 10000),  # T1 hits (high=1.12)
        (1.11, 1.15, 1.10, 1.14, 10000),  # horizon close=1.14, no T2
    ])

    result = evaluate_horizon(
        df,
        trigger_idx=0,
        entry_fill=1.01,
        stop=0.95,
        t1=1.10,
        t2=1.20,
        end_idx=len(df) - 1,
    )

    assert result["status"] == NET_R_STATUS_VALID, result["status"]
    assert result["exit_reason"] == "HORIZON_END_AFTER_T1", result["exit_reason"]
    # Weighted: 0.5 * 1.10 + 0.5 * 1.14 = 1.12
    expected = 0.5 * 1.10 + 0.5 * 1.14
    assert abs(result["exit_fill"] - expected) < 0.001, (
        f"exit_fill={result['exit_fill']} expected={expected} — PR-FIX-3 not applied"
    )


# =====================================================================
# TEST 12 — PR-FIX-2: exit_reason distinguishes BE after T1
#
# This is the diagnostic invariant: the exit_reason field must
# record that a partial exit occurred before the stop.
# =====================================================================

@test("test_exit_reason_field_after_partial")
def test_exit_reason_field_after_partial():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.12, 0.99, 1.11, 10000),  # T1
        (1.11, 1.12, 1.00, 1.05, 10000),  # BE stop
    ])

    result = evaluate_horizon(
        df,
        trigger_idx=0,
        entry_fill=1.01,
        stop=0.95,
        t1=1.10,
        t2=1.20,
        end_idx=len(df) - 1,
    )

    # The old code emitted "STOP_HIT" here, hiding the partial exit.
    assert result["exit_reason"] != "STOP_HIT", (
        "exit_reason=STOP_HIT after partial exit — PR-FIX-2 not applied"
    )
    assert result["exit_reason"] == "STOP_BE_AFTER_T1", result["exit_reason"]


# =====================================================================
# TEST 13 — Cost model sanity: spread + tick only
# =====================================================================

@test("test_cost_model_spread_plus_tick")
def test_cost_model_spread_plus_tick():
    costs = compute_costs(
        entry_fill=10.00,
        exit_fill=10.00,
        spread_pct=0.5,  # 0.25% per side
    )
    # entry_cost = 10.00 * 0.0025 + 0.01 = 0.035
    # exit_cost  = 10.00 * 0.0025 + 0.01 = 0.035
    # total      = 0.070
    assert abs(costs["total_per_share"] - 0.070) < 0.0001, costs
    assert abs(costs["tick_cost_ps"] - 2 * TICK_SIZE) < 1e-9, costs


# =====================================================================
# RUNNER
# =====================================================================

def main():
    print("=" * 74)
    print("DAYS-BOT — OUTCOME ENGINE TESTS (V5.0.6.3)")
    print("=" * 74)
    print(f"TICK_SIZE = {TICK_SIZE}")
    print()

    passed = 0
    failed = 0
    failures = []

    for name, fn in TESTS:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}")
            print(f"        {type(e).__name__}: {e}")
            failures.append((name, e))
            failed += 1

    print()
    print("=" * 74)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 74)

    if failed > 0:
        print()
        print("FAILED TESTS:")
        for name, e in failures:
            print(f"  - {name}: {e}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
