#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6 – Snapshot Evaluator

Purpose
-------
Evaluate immutable T0 snapshots against post-T0 market data.

IMPORTANT
---------
This evaluator does NOT change strategy decisions.

It evaluates what the snapshot already contained.

Net-R statuses
--------------
VALID
    Executable trade with valid entry/risk/position.

NON_EXECUTABLE
    Trigger happened but the trade could not actually be executed.

INVALID
    Required trade/risk data is invalid.

INCOMPLETE
    Required market/outcome data is incomplete.

A real 0R executable trade remains:

    net_r = 0
    net_r_status = VALID
    outcome = BREAKEVEN

It must NOT be converted to NULL merely because Net R is zero.
"""

import json
import math
import sqlite3

from argparse import ArgumentParser
from datetime import datetime, timedelta

from pathlib import Path

import pandas as pd
import pytz
import yfinance as yf


# =====================================================================
# PATHS
# =====================================================================

ET = pytz.timezone(
    "America/New_York"
)

UTC = pytz.UTC

BASE_DIR = Path(
    __file__
).resolve().parent

DB_PATH = (
    BASE_DIR
    / "data"
    / "alerts.db"
)


# =====================================================================
# VERSIONED CONFIG
# =====================================================================

TRIGGER_VERSION = "V5.0.6-T1"
EXIT_RULES_VERSION = "V5.0.6-E1"
COST_MODEL_VERSION = "V5.0.6-C1"

SLIPPAGE_PCT = 0.15

BLINK_FEE_PER_SHARE = 0.01
BLINK_MIN_FEE = 1.50
BLINK_MAX_FEE_PCT = 0.018

# Keep tax nullable conceptually.
# Do not hard-code an Israeli tax liability into strategy evidence.
ISRAEL_TAX_RATE = 0.25

RTH_START = "09:30"
RTH_END = "15:59"

MOMENTUM_WINDOW_MIN = 90


# =====================================================================
# STATUS CONSTANTS
# =====================================================================

NET_R_STATUS_VALID = (
    "VALID"
)

NET_R_STATUS_NON_EXECUTABLE = (
    "NON_EXECUTABLE"
)

NET_R_STATUS_INVALID = (
    "INVALID"
)

NET_R_STATUS_INCOMPLETE = (
    "INCOMPLETE"
)


# =====================================================================
# HELPERS
# =====================================================================

def _safe_float(
    value,
    default=None,
):
    try:
        if value is None:
            return default

        value = float(value)

        if not math.isfinite(value):
            return default

        return value

    except (
        TypeError,
        ValueError,
    ):
        return default


def _safe_int(
    value,
    default=None,
):
    try:
        if value is None:
            return default

        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _utc_string(value):
    if value is None:
        return None

    if value.tzinfo is None:
        value = ET.localize(
            value
        )

    return value.astimezone(
        UTC
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _et_string(value):
    if value is None:
        return None

    if value.tzinfo is None:
        value = ET.localize(
            value
        )

    return value.astimezone(
        ET
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _json(value):
    try:
        return json.dumps(
            value,
            default=str,
        )
    except Exception:
        return None


# =====================================================================
# DATABASE MIGRATION
# =====================================================================

def ensure_schema():
    """
    Initialize schema and guarantee the new Net-R status column exists.
    """

    from database.snapshot_schema import (
        init_snapshot_schema
    )

    init_snapshot_schema()


# =====================================================================
# MARKET DATA
# =====================================================================

def fetch_rth_bars(
    ticker: str,
    scan_date: str,
) -> pd.DataFrame:
    """
    Fetch 1-minute RTH bars.

    Only RTH bars are returned.
    """

    try:

        start = datetime.strptime(
            scan_date,
            "%Y-%m-%d",
        )

        end = (
            start
            + timedelta(days=1)
        )

        df = yf.download(
            ticker,
            start=start.strftime(
                "%Y-%m-%d"
            ),
            end=end.strftime(
                "%Y-%m-%d"
            ),
            interval="1m",
            prepost=False,
            progress=False,
            auto_adjust=False,
            threads=False,
        )

        if (
            df is None
            or df.empty
        ):
            return pd.DataFrame()

        if isinstance(
            df.columns,
            pd.MultiIndex,
        ):
            df.columns = (
                df.columns
                .get_level_values(0)
            )

        df.index = pd.to_datetime(
            df.index
        )

        if df.index.tz is None:
            df.index = (
                df.index
                .tz_localize(
                    "UTC"
                )
            )

        df.index = (
            df.index
            .tz_convert(ET)
        )

        df = df.between_time(
            RTH_START,
            RTH_END,
        )

        return df

    except Exception as exc:

        print(
            f"[evaluate] "
            f"{ticker} fetch error: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return pd.DataFrame()


# =====================================================================
# PM BAR RESTORATION
# =====================================================================

def load_pm_bars(snapshot):
    """
    Restore immutable PM bars from snapshot.pm_bars_json.

    Returns DataFrame or empty DataFrame.
    """

    raw = snapshot["pm_bars_json"]

    if not raw:
        return pd.DataFrame()

    try:

        data = json.loads(
            raw
        )

        if not isinstance(
            data,
            list,
        ):
            return pd.DataFrame()

        rows = []

        for item in data:

            if not isinstance(
                item,
                dict,
            ):
                continue

            rows.append(item)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(
            rows
        )

        rename = {
            "timestamp": "timestamp",
            "time": "timestamp",
            "datetime": "timestamp",
            "Date": "timestamp",
        }

        for old, new in rename.items():
            if (
                old in df.columns
                and new not in df.columns
            ):
                df = df.rename(
                    columns={
                        old: new
                    }
                )

        if "timestamp" not in df.columns:
            return pd.DataFrame()

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        df = df.dropna(
            subset=[
                "timestamp"
            ]
        )

        if df.empty:
            return pd.DataFrame()

        if df["timestamp"].dt.tz is None:
            df["timestamp"] = (
                df["timestamp"]
                .dt.tz_localize(
                    ET
                )
            )
        else:
            df["timestamp"] = (
                df["timestamp"]
                .dt.tz_convert(
                    ET
                )
            )

        df = df.set_index(
            "timestamp"
        )

        # Normalize column names.
        mapping = {}

        for col in df.columns:

            lower = str(
                col
            ).lower()

            if lower == "open":
                mapping[col] = "Open"

            elif lower == "high":
                mapping[col] = "High"

            elif lower == "low":
                mapping[col] = "Low"

            elif lower == "close":
                mapping[col] = "Close"

            elif lower == "volume":
                mapping[col] = "Volume"

        df = df.rename(
            columns=mapping
        )

        return df.sort_index()

    except Exception as exc:

        print(
            f"[PM] restore error: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return pd.DataFrame()


# =====================================================================
# TRIGGER HELPERS
# =====================================================================

def _valid_ohlcv(df):
    required = {
        "Open",
        "High",
        "Low",
        "Close",
    }

    return (
        not df.empty
        and required.issubset(
            set(df.columns)
        )
    )


def _median_previous_volume(
    df,
    idx,
):
    """
    Median volume of previous five valid bars.

    If fewer than three valid previous bars exist,
    volume confirmation is unavailable.
    """

    if "Volume" not in df.columns:
        return None

    start = max(
        0,
        idx - 5,
    )

    values = []

    for j in range(
        start,
        idx,
    ):

        v = _safe_float(
            df.iloc[j][
                "Volume"
            ]
        )

        if (
            v is not None
            and v > 0
        ):
            values.append(v)

    if len(values) < 3:
        return None

    return float(
        pd.Series(values)
        .median()
    )


def _entry_fill_from_next_bar(
    df,
    trigger_idx,
):
    """
    Trigger occurs on bar N.

    Execution occurs on bar N+1 open
    plus fixed buy slippage.

    If N+1 does not exist:
        trigger hit
        NOT_EXECUTABLE
    """

    next_idx = (
        trigger_idx + 1
    )

    if next_idx >= len(df):
        return None

    open_price = _safe_float(
        df.iloc[next_idx][
            "Open"
        ]
    )

    if (
        open_price is None
        or open_price <= 0
    ):
        return None

    return (
        open_price
        * (
            1
            + SLIPPAGE_PCT
            / 100.0
        )
    )


# =====================================================================
# TRIGGER A — PMH BREAKOUT
# =====================================================================

def detect_pmh_breakout(
    df,
    pm_high,
    buffer,
):
    if (
        pm_high is None
        or pm_high <= 0
        or not _valid_ohlcv(df)
    ):
        return None

    level = (
        pm_high
        + buffer
    )

    for idx in range(
        len(df)
    ):

        high = _safe_float(
            df.iloc[idx]["High"]
        )

        if (
            high is not None
            and high >= level
        ):
            return {
                "method":
                    "PMH_BREAKOUT_V1",

                "idx":
                    idx,

                "time":
                    df.index[idx],

                "trigger_price":
                    high,

                "level":
                    level,
            }

    return None


# =====================================================================
# TRIGGER B — BREAKOUT + VOLUME
# =====================================================================

def detect_volume_breakout(
    df,
    pm_high,
    buffer,
):
    if (
        pm_high is None
        or pm_high <= 0
        or not _valid_ohlcv(df)
    ):
        return None

    level = (
        pm_high
        + buffer
    )

    for idx in range(
        len(df)
    ):

        close = _safe_float(
            df.iloc[idx]["Close"]
        )

        volume = _safe_float(
            df.iloc[idx].get(
                "Volume"
            )
        )

        if (
            close is None
            or volume is None
            or volume <= 0
        ):
            continue

        median_volume = (
            _median_previous_volume(
                df,
                idx,
            )
        )

        if median_volume is None:
            continue

        if (
            close >= level
            and volume
            >= (
                1.2
                * median_volume
            )
        ):
            return {
                "method":
                    "BREAKOUT_VOLUME_V1",

                "idx":
                    idx,

                "time":
                    df.index[idx],

                "trigger_price":
                    close,

                "level":
                    level,

                "volume":
                    volume,

                "median_volume":
                    median_volume,
            }

    return None


# =====================================================================
# TRIGGER C — VWAP RECLAIM
# =====================================================================

def detect_vwap_reclaim(
    df,
    pm_vwap,
):
    if (
        pm_vwap is None
        or pm_vwap <= 0
        or not _valid_ohlcv(df)
    ):
        return None

    for idx in range(
        1,
        len(df),
    ):

        previous_close = (
            _safe_float(
                df.iloc[
                    idx - 1
                ]["Close"]
            )
        )

        current_close = (
            _safe_float(
                df.iloc[idx][
                    "Close"
                ]
            )
        )

        if (
            previous_close is None
            or current_close is None
        ):
            continue

        if (
            previous_close
            < pm_vwap
            and current_close
            >= pm_vwap
        ):
            return {
                "method":
                    "VWAP_RECLAIM_V1",

                "idx":
                    idx,

                "time":
                    df.index[idx],

                "trigger_price":
                    current_close,

                "level":
                    pm_vwap,
            }

    return None


# =====================================================================
# TRIGGER D — PULLBACK / RETEST
# =====================================================================

def detect_pullback_retest(
    df,
    pm_high,
    buffer,
    timeout_minutes=60,
):
    if (
        pm_high is None
        or pm_high <= 0
        or not _valid_ohlcv(df)
    ):
        return None

    level = (
        pm_high
        + buffer
    )

    breakout_idx = None

    for idx in range(
        len(df)
    ):

        high = _safe_float(
            df.iloc[idx]["High"]
        )

        if (
            high is not None
            and high >= level
        ):
            breakout_idx = idx
            break

    if breakout_idx is None:
        return None

    breakout_time = (
        df.index[
            breakout_idx
        ]
    )

    # -------------------------------------------------------------
    # Separate bars required:
    # Breakout -> Pullback -> Reclaim
    # -------------------------------------------------------------

    pullback_idx = None

    for idx in range(
        breakout_idx + 1,
        len(df),
    ):

        elapsed = (
            df.index[idx]
            - breakout_time
        ).total_seconds() / 60

        if elapsed > timeout_minutes:
            break

        low = _safe_float(
            df.iloc[idx]["Low"]
        )

        if (
            low is not None
            and low <= level
        ):
            pullback_idx = idx
            break

    if pullback_idx is None:
        return None

    for idx in range(
        pullback_idx + 1,
        len(df),
    ):

        elapsed = (
            df.index[idx]
            - breakout_time
        ).total_seconds() / 60

        if elapsed > timeout_minutes:
            break

        close = _safe_float(
            df.iloc[idx]["Close"]
        )

        if (
            close is not None
            and close >= level
        ):
            return {
                "method":
                    "PULLBACK_RETEST_V1",

                "idx":
                    idx,

                "time":
                    df.index[idx],

                "trigger_price":
                    close,

                "level":
                    level,

                "breakout_idx":
                    breakout_idx,

                "pullback_idx":
                    pullback_idx,
            }

    return None


# =====================================================================
# COST MODEL
# =====================================================================

def compute_costs(
    entry_fill,
    exit_fill,
    position_size,
):
    """
    Fixed versioned commission model.

    Tax remains an optional model component.
    """

    entry_fill = _safe_float(
        entry_fill
    )

    exit_fill = _safe_float(
        exit_fill
    )

    position_size = _safe_int(
        position_size
    )

    if (
        entry_fill is None
        or exit_fill is None
        or position_size is None
        or position_size <= 0
    ):
        return {
            "gross_pnl":
                None,

            "commission":
                0.0,

            "tax":
                0.0,

            "total":
                0.0,
        }

    entry_value = (
        entry_fill
        * position_size
    )

    exit_value = (
        exit_fill
        * position_size
    )

    gross_pnl = (
        exit_value
        - entry_value
    )

    def blink_fee(value):
        per_share = (
            position_size
            * BLINK_FEE_PER_SHARE
        )

        max_fee = (
            abs(value)
            * BLINK_MAX_FEE_PCT
        )

        return max(
            BLINK_MIN_FEE,
            min(
                per_share,
                max_fee,
            ),
        )

    commission = (
        blink_fee(entry_value)
        + blink_fee(exit_value)
    )

    tax = (
        max(
            0.0,
            gross_pnl,
        )
        * ISRAEL_TAX_RATE
    )

    return {
        "gross_pnl":
            gross_pnl,

        "commission":
            commission,

        "tax":
            tax,

        "total":
            commission + tax,
    }


# =====================================================================
# OUTCOME ENGINE
# =====================================================================

def evaluate_horizon(
    df,
    trigger_idx,
    entry_fill,
    stop,
    t1,
    t2,
    end_idx=None,
):
    """
    V5.0.6 Exit Rules

    - Trigger on bar N.
    - Entry on N+1 open + slippage.
    - 50% at T1.
    - Stop moves to breakeven after T1.
    - Remaining 50% exits at T2.
    - Stop-first on same candle.
    """

    if end_idx is None:
        end_idx = len(df) - 1

    end_idx = min(
        end_idx,
        len(df) - 1,
    )

    entry_idx = (
        trigger_idx + 1
    )

    if entry_idx >= len(df):
        return {
            "status":
                NET_R_STATUS_NON_EXECUTABLE,

            "entry_fill":
                None,

            "exit_fill":
                None,

            "exit_reason":
                "NOT_EXECUTABLE",

            "exit_idx":
                None,
        }

    entry_time = (
        df.index[
            entry_idx
        ]
    )

    current_stop = stop

    half_exited = False

    exit_reason = (
        "HORIZON_END"
    )

    exit_idx = end_idx

    exit_fill = _safe_float(
        df.iloc[end_idx][
            "Close"
        ]
    )

    if (
        exit_fill is None
        or entry_fill is None
    ):
        return {
            "status":
                NET_R_STATUS_INCOMPLETE,

            "entry_fill":
                entry_fill,

            "exit_fill":
                None,

            "exit_reason":
                "INCOMPLETE_DATA",

            "exit_idx":
                None,
        }

    mfe = entry_fill
    mae = entry_f