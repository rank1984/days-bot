#!/usr/bin/env python3
"""
tests/test_outcome_engine.py

Unit tests for DAYS-BOT V5.0.6.1 Outcome Engine.

Written BEFORE the F1-F12 fixes. Running against the current (pre-fix)
code is expected to show 4 failures, one per fix.

Expected on current code:
    test_stop_first_same_bar               PASS
    test_gap_down_below_stop               FAIL   (F2)
    test_no_next_bar_non_executable        PASS
    test_t1_and_t2_same_bar_conservative   PASS
    test_normal_stop_hit                   PASS
    test_normal_t2_hit                     PASS
    test_detect_pmh_breakout_uses_close    FAIL   (F5)
    test_compute_costs_accepts_spread_pct  FAIL   (F7)
    test_r_denominator_contract            PASS (documents F1)

Run:
    pytest tests/test_outcome_engine.py -v
"""
import sys
from pathlib import Path

import pandas as pd
import pytest
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


# =====================================================================
# HELPERS
# =====================================================================

def make_df(rows, start_time="2026-09-28 09:30:00"):
    """
    Build a 1-minute OHLCV DataFrame from a list of tuples.
    rows: list of (open, high, low, close, volume)
    """
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


# =====================================================================
# TEST 1 — Stop wins when both stop and T1 touched on same bar
# =====================================================================

def test_stop_first_same_bar():
    """
    Conservative rule: if a single bar touches both stop and T1,
    STOP wins.
    """
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),   # bar 0: trigger
        (1.01, 1.03, 0.98, 1.00, 10000),   # bar 1: entry at open = 1.01
        (1.00, 1.15, 0.93, 1.10, 10000),   # bar 2: low 0.93 < stop 0.95
                                            #        high 1.15 > T1 1.10
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

    assert result["status"] == NET_R_STATUS_VALID
    assert result["exit_reason"] == "STOP_HIT"
    expected_exit = 0.95 * (1 - SLIPPAGE_PCT / 100)
    assert abs(result["exit_fill"] - expected_exit) < 0.001


# =====================================================================
# TEST 2 — Gap-down: fill at open, not at stop  (F2)
# =====================================================================

def test_gap_down_below_stop():
    """
    Bar 2 opens BELOW the stop (gap-down).
    Correct fill: at the OPEN, not at the stop.
    Current code fills at the stop — this test FAILS until F2 applied.
    """
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (0.85, 0.90, 0.80, 0.87, 10000),   # opens far below stop 0.95
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

    assert result["status"] == NET_R_STATUS_VALID
    assert result["exit_reason"] == "STOP_HIT"

    expected_exit = 0.85 * (1 - SLIPPAGE_PCT / 100)
    assert abs(result["exit_fill"] - expected_exit) < 0.001, (
        "Gap-down fill must be at open (" + str(round(expected_exit, 4)) +
        "), got " + str(round(result["exit_fill"], 4)) + " — F2 not applied"
    )


# =====================================================================
# TEST 3 — No next bar: NON_EXECUTABLE
# =====================================================================

def test_no_next_bar_non_executable():
    """
    Trigger fires on the last bar of the session.
    No bar N+1 -> entry impossible.
    """
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

    assert result["status"] == NET_R_STATUS_NON_EXECUTABLE
    assert result["exit_reason"] == "NOT_EXECUTABLE"


# =====================================================================
# TEST 4 — T1 and T2 same bar: conservative behavior
# =====================================================================

def test_t1_and_t2_same_bar_conservative():
    """
    Bar 2 touches both T1 and T2.
    Conservative: T1 this bar; T2 requires the NEXT bar to also touch.
    """
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.25, 0.99, 1.22, 10000),   # T1 (1.10) and T2 (1.20)
        (1.22, 1.23, 1.10, 1.15, 10000),   # T2 touched here too
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

    assert result["status"] == NET_R_STATUS_VALID
    assert result["exit_reason"] == "T2_HIT"


# =====================================================================
# TEST 5 — Normal stop hit
# =====================================================================

def test_normal_stop_hit():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.02, 0.94, 0.96, 10000),   # low 0.94 < stop 0.95, no gap
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

    assert result["exit_reason"] == "STOP_HIT"
    expected_exit = 0.95 * (1 - SLIPPAGE_PCT / 100)
    assert abs(result["exit_fill"] - expected_exit) < 0.001


# =====================================================================
# TEST 6 — Normal T2 hit
# =====================================================================

def test_normal_t2_hit():
    df = make_df([
        (1.00, 1.02, 0.99, 1.01, 10000),
        (1.01, 1.03, 0.98, 1.00, 10000),
        (1.00, 1.12, 0.99, 1.11, 10000),   # T1 1.10
        (1.11, 1.22, 1.10, 1.21, 10000),   # T2 1.20
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

    assert result["exit_reason"] == "T2_HIT"
    t1_fill = 1.10 * (1 - SLIPPAGE_PCT / 100)
    t2_fill = 1.20 * (1 - SLIPPAGE_PCT / 100)
    expected_exit = 0.5 * t1_fill + 0.5 * t2_fill
    assert abs(result["exit_fill"] - expected_exit) < 0.001


# =====================================================================
# TEST 7 — detect_pmh_breakout uses CLOSE (not High)  (F5)
# =====================================================================

def test_detect_pmh_breakout_uses_close():
    """
    Spec: Trigger = Close > PMH + buffer.
    Current code uses High >= level.
    Single bar where High crosses but Close does not.
    Current code fires (BUG); after F5, returns None.
    """
    df = make_df([
        (1.00, 1.02, 0.98, 0.99, 10000),   # High 1.02, Close 0.99
    ])

    result = detect_pmh_breakout(df, pm_high=1.00, buffer=0.01)

    assert result is None, (
        "detect_pmh_breakout fired on High-touch — spec requires Close. "
        "F5 not applied."
    )


# =====================================================================
# TEST 8 — compute_costs accepts spread_pct parameter  (F7)
# =====================================================================

def test_compute_costs_accepts_spread_pct():
    """
    After F7, compute_costs must accept a spread_pct parameter.
    Current signature: compute_costs(entry_fill, exit_fill, position_size).
    This test fails with TypeError until F7 is applied.
    """
    try:
        compute_costs(
            entry_fill=1.00,
            exit_fill=1.00,
            position_size=100,
            spread_pct=1.5,
        )
    except TypeError as e:
        pytest.fail(
            "compute_costs does not accept spread_pct: " + str(e) +
            " — F7 not applied"
        )


# =====================================================================
# TEST 9 — R denominator contract (documents F1)
# =====================================================================

def test_r_denominator_contract():
    """
    Documents the F1 contract for the caller of compute_gross_net.

    After F1:
        R = (exit - entry) / (entry_fill - initial_stop)
    Pre-F1 caller passed the PLAN risk, producing huge R values.

    This test PASSES on current code (compute_gross_net is agnostic);
    it documents the contract so callers can be updated in F1.
    """
    gap_up_entry = 1.50
    stop_used = 1.00
    correct_risk = gap_up_entry - stop_used  # 0.50

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

    assert -1.5 < correct_r < -0.5, "Correct R (fill - stop) near -1R"
    assert buggy_r < -10, "Plan risk produces exploded R (this is F1)"