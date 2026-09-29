#!/usr/bin/env python3
"""
tests/test_outcome_engine.py

Standalone test runner — no pytest required.
Run:  python3 tests/test_outcome_engine.py

Exit code 0 = all tests pass
Exit code 1 = at least one test failed
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
    SLIPPAGE_PCT,
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
    expected_exit = 0.95 * (1 - SLIPPAGE_PCT / 100)
    assert abs(result["exit_fill"] - expected_exit) < 0.001, (
        f"exit_fill={result['exit_fill']} expected={expected_exit}"
    )


# =====================================================================
# TEST 2 — Gap-down: fill at open, not at stop  (F2)
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

    expected_exit = 0.85 * (1 - SLIPPAGE_PCT / 100)
    assert abs(result["exit_fill"] - expected_exit) < 0.001, (
        f"Gap-down fill must be at open ({expected_exit:.4f}), "
        f"got {result['exit_fill']:.4f} — F2 not applied"
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
# TEST 4 — T1 and T2 same bar: conservative behavior
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
# TEST 5 — Normal stop hit
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
    expected_exit = 0.95 * (1 - SLIPPAGE_PCT / 100)
    assert abs(result["exit_fill"] - expected_exit) < 0.001, (
        f"exit_fill={result['exit_fill']} expected={expected_exit}"
    )


# =====================================================================
# TEST 6 — Normal T2 hit
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
    t1_fill = 1.10 * (1 - SLIPPAGE_PCT / 100)
    t2_fill = 1.20 * (1 - SLIPPAGE_PCT / 100)
    expected_exit = 0.5 * t1_fill + 0.5 * t2_fill
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
# TEST 8 — compute_costs accepts spread_pct parameter  (F7)
# =====================================================================

@test("test_compute_costs_accepts_spread_pct")
def test_compute_costs_accepts_spread_pct():
    try:
        compute_costs(
            entry_fill=1.00,
            exit_fill=1.00,
            position_size=100,
            spread_pct=1.5,
        )
    except TypeError as e:
        raise TestFailure(
            f"compute_costs does not accept spread_pct: {e} — F7 not applied"
        )


# =====================================================================
# TEST 9 — R denominator contract (documents F1)
# =====================================================================

@test("test_r_denominator_contract")
def test_r_denominator_contract():
    gap_up_entry = 1.50
    stop_used = 1.00
    correct_risk = gap_up_entry - stop_used

    correct_r = compute_gross_net(
        entry_fill=gap_up_entry,
        exit_fill=stop_used,
        risk_per_share=correct_risk,
        position_size=100,
    )["gross_r"]

    buggy_r = compute_gross_net(
        entry_fill=gap_up_entry,
        exit_fill=stop_used,
        risk_per_share=0.02,
        position_size=100,
    )["gross_r"]

    assert -1.5 < correct_r < -0.5, f"correct_r={correct_r}"
    assert buggy_r < -10, f"buggy_r={buggy_r}"


# =====================================================================
# RUNNER
# =====================================================================

def main():
    print("=" * 74)
    print("DAYS-BOT — OUTCOME ENGINE TESTS")
    print("=" * 74)
    print(f"SLIPPAGE_PCT = {SLIPPAGE_PCT}")
    print()

    passed = 0
    failed = 0

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
    print("=" * 74)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 74)

    if failed > 0:
        print()
        print("EXPECTED FAILURES BEFORE F1-F12:")
        print("  test_gap_down_below_stop          (F2)")
        print("  test_detect_pmh_breakout_uses_close (F5)")
        print("  test_compute_costs_accepts_spread_pct (F7)")
        print()
        print("If you see DIFFERENT failures — report them.")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())