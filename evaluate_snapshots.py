
#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6.1 – Snapshot Evaluator

FIXES (V5.0.6.1):
- write_trigger() now writes trigger_data_mode + returns trigger_result_id
- write_outcome() now writes trigger_result_id (fixes TRIGGERED_NO_OUTCOME)
- evaluate_snapshot() computes trigger_data_mode once (PM_AWARE / RTH_ONLY)
- All 4 write_outcome calls pass trigger_result_id

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

ET = pytz.timezone("America/New_York")
UTC = pytz.UTC

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "alerts.db"


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

ISRAEL_TAX_RATE = 0.25

RTH_START = "09:30"
RTH_END = "15:59"

MOMENTUM_WINDOW_MIN = 90


# =====================================================================
# STATUS CONSTANTS
# =====================================================================

NET_R_STATUS_VALID = "VALID"
NET_R_STATUS_NON_EXECUTABLE = "NON_EXECUTABLE"
NET_R_STATUS_INVALID = "INVALID"
NET_R_STATUS_INCOMPLETE = "INCOMPLETE"


# =====================================================================
# HELPERS
# =====================================================================

def _safe_float(value, default=None):
    try:
        if value is None:
            return default
        value = float(value)
        if not math.isfinite(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=None):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _utc_string(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = ET.localize(value)
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _et_string(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = ET.localize(value)
    return value.astimezone(ET).strftime("%Y-%m-%d %H:%M:%S")


def _json(value):
    try:
        return json.dumps(value, default=str)
    except Exception:
        return None


# =====================================================================
# DATABASE MIGRATION
# =====================================================================

def ensure_schema():
    from database.snapshot_schema import init_snapshot_schema
    init_snapshot_schema()


# =====================================================================
# MARKET DATA
# =====================================================================

def fetch_rth_bars(ticker, scan_date):
    try:
        start = datetime.strptime(scan_date, "%Y-%m-%d")
        end = start + timedelta(days=1)

        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1m",
            prepost=False,
            progress=False,
            auto_adjust=False,
            threads=False,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(ET)

        df = df.between_time(RTH_START, RTH_END)
        return df

    except Exception as exc:
        print(f"[evaluate] {ticker} fetch error: {type(exc).__name__}: {exc}")
        return pd.DataFrame()


# =====================================================================
# PM BAR RESTORATION
# =====================================================================

def load_pm_bars(snapshot):
    raw = snapshot["pm_bars_json"]
    if not raw:
        return pd.DataFrame()

    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return pd.DataFrame()

        rows = []
        for item in data:
            if isinstance(item, dict):
                rows.append(item)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        rename = {
            "timestamp": "timestamp",
            "time": "timestamp",
            "datetime": "timestamp",
            "Date": "timestamp",
        }
        for old, new in rename.items():
            if old in df.columns and new not in df.columns:
                df = df.rename(columns={old: new})

        if "timestamp" not in df.columns:
            return pd.DataFrame()

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])

        if df.empty:
            return pd.DataFrame()

        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(ET)
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert(ET)

        df = df.set_index("timestamp")

        mapping = {}
        for col in df.columns:
            lower = str(col).lower()
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

        df = df.rename(columns=mapping)
        return df.sort_index()

    except Exception as exc:
        print(f"[PM] restore error: {type(exc).__name__}: {exc}")
        return pd.DataFrame()


# =====================================================================
# TRIGGER HELPERS
# =====================================================================

def _valid_ohlcv(df):
    required = {"Open", "High", "Low", "Close"}
    return not df.empty and required.issubset(set(df.columns))


def _median_previous_volume(df, idx):
    if "Volume" not in df.columns:
        return None

    start = max(0, idx - 5)
    values = []

    for j in range(start, idx):
        v = _safe_float(df.iloc[j]["Volume"])
        if v is not None and v > 0:
            values.append(v)

    if len(values) < 3:
        return None

    return float(pd.Series(values).median())


def _entry_fill_from_next_bar(df, trigger_idx):
    next_idx = trigger_idx + 1
    if next_idx >= len(df):
        return None

    open_price = _safe_float(df.iloc[next_idx]["Open"])
    if open_price is None or open_price <= 0:
        return None

    return open_price * (1 + SLIPPAGE_PCT / 100.0)


# =====================================================================
# TRIGGER A — PMH BREAKOUT
# =====================================================================

def detect_pmh_breakout(df, pm_high, buffer):
    if pm_high is None or pm_high <= 0 or not _valid_ohlcv(df):
        return None

    level = pm_high + buffer

    for idx in range(len(df)):
        high = _safe_float(df.iloc[idx]["High"])
        if high is not None and high >= level:
            return {
                "method": "PMH_BREAKOUT_V1",
                "idx": idx,
                "time": df.index[idx],
                "trigger_price": high,
                "level": level,
            }

    return None


# =====================================================================
# TRIGGER B — BREAKOUT + VOLUME
# =====================================================================

def detect_volume_breakout(df, pm_high, buffer):
    if pm_high is None or pm_high <= 0 or not _valid_ohlcv(df):
        return None

    level = pm_high + buffer

    for idx in range(len(df)):
        close = _safe_float(df.iloc[idx]["Close"])
        volume = _safe_float(df.iloc[idx].get("Volume"))

        if close is None or volume is None or volume <= 0:
            continue

        median_volume = _median_previous_volume(df, idx)
        if median_volume is None:
            continue

        if close >= level and volume >= (1.2 * median_volume):
            return {
                "method": "BREAKOUT_VOLUME_V1",
                "idx": idx,
                "time": df.index[idx],
                "trigger_price": close,
                "level": level,
                "volume": volume,
                "median_volume": median_volume,
            }

    return None


# =====================================================================
# TRIGGER C — VWAP RECLAIM
# =====================================================================

def detect_vwap_reclaim(df, pm_vwap):
    if pm_vwap is None or pm_vwap <= 0 or not _valid_ohlcv(df):
        return None

    for idx in range(1, len(df)):
        previous_close = _safe_float(df.iloc[idx - 1]["Close"])
        current_close = _safe_float(df.iloc[idx]["Close"])

        if previous_close is None or current_close is None:
            continue

        if previous_close < pm_vwap and current_close >= pm_vwap:
            return {
                "method": "VWAP_RECLAIM_V1",
                "idx": idx,
                "time": df.index[idx],
                "trigger_price": current_close,
                "level": pm_vwap,
            }

    return None


# =====================================================================
# TRIGGER D — PULLBACK / RETEST
# =====================================================================

def detect_pullback_retest(df, pm_high, buffer, timeout_minutes=60):
    if pm_high is None or pm_high <= 0 or not _valid_ohlcv(df):
        return None

    level = pm_high + buffer

    breakout_idx = None
    for idx in range(len(df)):
        high = _safe_float(df.iloc[idx]["High"])
        if high is not None and high >= level:
            breakout_idx = idx
            break

    if breakout_idx is None:
        return None

    breakout_time = df.index[breakout_idx]

    pullback_idx = None
    for idx in range(breakout_idx + 1, len(df)):
        elapsed = (df.index[idx] - breakout_time).total_seconds() / 60
        if elapsed > timeout_minutes:
            break

        low = _safe_float(df.iloc[idx]["Low"])
        if low is not None and low <= level:
            pullback_idx = idx
            break

    if pullback_idx is None:
        return None

    for idx in range(pullback_idx + 1, len(df)):
        elapsed = (df.index[idx] - breakout_time).total_seconds() / 60
        if elapsed > timeout_minutes:
            break

        close = _safe_float(df.iloc[idx]["Close"])
        if close is not None and close >= level:
            return {
                "method": "PULLBACK_RETEST_V1",
                "idx": idx,
                "time": df.index[idx],
                "trigger_price": close,
                "level": level,
                "breakout_idx": breakout_idx,
                "pullback_idx": pullback_idx,
            }

    return None


# =====================================================================
# COST MODEL
# =====================================================================

def compute_costs(entry_fill, exit_fill, position_size):
    entry_fill = _safe_float(entry_fill)
    exit_fill = _safe_float(exit_fill)
    position_size = _safe_int(position_size)

    if (
        entry_fill is None
        or exit_fill is None
        or position_size is None
        or position_size <= 0
    ):
        return {
            "gross_pnl": None,
            "commission": 0.0,
            "tax": 0.0,
            "total": 0.0,
        }

    entry_value = entry_fill * position_size
    exit_value = exit_fill * position_size
    gross_pnl = exit_value - entry_value

    def blink_fee(value):
        per_share = position_size * BLINK_FEE_PER_SHARE
        max_fee = abs(value) * BLINK_MAX_FEE_PCT
        return max(BLINK_MIN_FEE, min(per_share, max_fee))

    commission = blink_fee(entry_value) + blink_fee(exit_value)
    tax = max(0.0, gross_pnl) * ISRAEL_TAX_RATE

    return {
        "gross_pnl": gross_pnl,
        "commission": commission,
        "tax": tax,
        "total": commission + tax,
    }


# =====================================================================
# OUTCOME ENGINE
# =====================================================================

def evaluate_horizon(df, trigger_idx, entry_fill, stop, t1, t2, end_idx=None):
    if end_idx is None:
        end_idx = len(df) - 1

    end_idx = min(end_idx, len(df) - 1)
    entry_idx = trigger_idx + 1

    if entry_idx >= len(df):
        return {
            "status": NET_R_STATUS_NON_EXECUTABLE,
            "entry_fill": None,
            "exit_fill": None,
            "exit_reason": "NOT_EXECUTABLE",
            "exit_idx": None,
        }

    entry_time = df.index[entry_idx]
    current_stop = stop
    half_exited = False
    exit_reason = "HORIZON_END"
    exit_idx = end_idx
    exit_fill = _safe_float(df.iloc[end_idx]["Close"])

    if exit_fill is None or entry_fill is None:
        return {
            "status": NET_R_STATUS_INCOMPLETE,
            "entry_fill": entry_fill,
            "exit_fill": None,
            "exit_reason": "INCOMPLETE_DATA",
            "exit_idx": None,
        }

    mfe = entry_fill
    mae = entry_fill
    mfe_idx = entry_idx
    mae_idx = entry_idx

    for idx in range(entry_idx, end_idx + 1):
        row = df.iloc[idx]
        high = _safe_float(row["High"])
        low = _safe_float(row["Low"])

        if high is None or low is None:
            continue

        if high > mfe:
            mfe = high
            mfe_idx = idx

        if low < mae:
            mae = low
            mae_idx = idx

        # STOP FIRST
        if low <= current_stop:
            exit_reason = "STOP_HIT"
            exit_idx = idx
            exit_price = current_stop * (1 - SLIPPAGE_PCT / 100.0)
            exit_fill = exit_price
            break

        # T1
        if not half_exited and high >= t1:
            half_exited = True
            current_stop = entry_fill
            continue

        # T2
        if half_exited and high >= t2:
            exit_reason = "T2_HIT"
            exit_idx = idx
            t1_fill = t1 * (1 - SLIPPAGE_PCT / 100.0)
            t2_fill = t2 * (1 - SLIPPAGE_PCT / 100.0)
            exit_fill = 0.5 * t1_fill + 0.5 * t2_fill
            break
    else:
        exit_idx = end_idx
        close = _safe_float(df.iloc[end_idx]["Close"])
        if close is None:
            return {
                "status": NET_R_STATUS_INCOMPLETE,
                "entry_fill": entry_fill,
                "exit_fill": None,
                "exit_reason": "INCOMPLETE_DATA",
                "exit_idx": end_idx,
            }
        exit_fill = close * (1 - SLIPPAGE_PCT / 100.0)
        exit_reason = "HORIZON_END"

    hold_minutes = int((df.index[exit_idx] - entry_time).total_seconds() / 60)
    time_to_mfe = int((df.index[mfe_idx] - entry_time).total_seconds())
    time_to_mae = int((df.index[mae_idx] - entry_time).total_seconds())

    mfe_pct = (mfe - entry_fill) / entry_fill * 100
    mae_pct = (mae - entry_fill) / entry_fill * 100
    gross_pct = (exit_fill - entry_fill) / entry_fill * 100

    return {
        "status": NET_R_STATUS_VALID,
        "entry_fill": entry_fill,
        "exit_fill": exit_fill,
        "exit_reason": exit_reason,
        "exit_idx": exit_idx,
        "exit_time": df.index[exit_idx],
        "mfe": mfe,
        "mae": mae,
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "time_to_mfe_sec": time_to_mfe,
        "time_to_mae_sec": time_to_mae,
        "hold_minutes": hold_minutes,
        "gross_pct": gross_pct,
    }


# =====================================================================
# NET / GROSS
# =====================================================================

def compute_gross_net(entry_fill, exit_fill, risk_per_share, position_size):
    entry_fill = _safe_float(entry_fill)
    exit_fill = _safe_float(exit_fill)
    risk_per_share = _safe_float(risk_per_share)
    position_size = _safe_int(position_size)

    if (
        entry_fill is None
        or exit_fill is None
        or risk_per_share is None
        or risk_per_share <= 0
        or position_size is None
        or position_size <= 0
    ):
        return {
            "gross_r": None,
            "gross_pct": None,
            "net_r": None,
            "net_pct": None,
            "costs": {
                "gross_pnl": None,
                "commission": 0.0,
                "tax": 0.0,
                "total": 0.0,
            },
            "outcome": "NON_EXECUTABLE",
            "net_r_status": NET_R_STATUS_NON_EXECUTABLE,
        }

    gross_per_share = exit_fill - entry_fill
    gross_r = gross_per_share / risk_per_share
    gross_pct = gross_per_share / entry_fill * 100

    costs = compute_costs(entry_fill, exit_fill, position_size)

    net_pnl = costs["gross_pnl"] - costs["total"]
    net_per_share = net_pnl / position_size
    net_r = net_per_share / risk_per_share
    net_pct = net_pnl / (entry_fill * position_size) * 100

    if net_r > 0.05:
        label = "WIN"
    elif net_r < -0.05:
        label = "LOSS"
    else:
        label = "BREAKEVEN"

    return {
        "gross_r": gross_r,
        "gross_pct": gross_pct,
        "net_r": net_r,
        "net_pct": net_pct,
        "costs": costs,
        "outcome": label,
        "net_r_status": NET_R_STATUS_VALID,
    }


# =====================================================================
# DB WRITE — TRIGGER  (V5.0.6.1)
# =====================================================================

def write_trigger(
    cur,
    snapshot_id,
    method,
    hit,
    trig_time,
    trig_price,
    elapsed_sec,
    window,
    trigger_data_mode,
    extra=None,
):
    cur.execute(
        """
        INSERT OR REPLACE INTO trigger_results
        (
            snapshot_id,
            trigger_method,
            trigger_version,
            hit,
            trigger_time_utc,
            trigger_time_et,
            trigger_price,
            elapsed_sec_from_t0,
            window,
            trigger_data_mode,
            metadata_json
        )
        VALUES (
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?
        )
        """,
        (
            snapshot_id,
            method,
            TRIGGER_VERSION,
            1 if hit else 0,
            _utc_string(trig_time),
            _et_string(trig_time),
            trig_price,
            elapsed_sec,
            window,
            trigger_data_mode,
            _json(extra),
        ),
    )

    # Fetch the actual trigger_result_id (INSERT OR REPLACE may have
    # deleted and re-created the row, so lastrowid is not reliable).
    row = cur.execute(
        """
        SELECT trigger_result_id
        FROM trigger_results
        WHERE snapshot_id = ?
          AND trigger_method = ?
          AND trigger_version = ?
        """,
        (snapshot_id, method, TRIGGER_VERSION),
    ).fetchone()

    if row is None:
        return None

    try:
        return row["trigger_result_id"]
    except (TypeError, IndexError):
        return row[0]


# =====================================================================
# DB WRITE — OUTCOME  (V5.0.6.1)
# =====================================================================

def write_outcome(
    cur,
    snapshot,
    trigger,
    trigger_result_id,
    horizon,
    outcome_data,
):
    snapshot_id = snapshot["snapshot_id"]

    entry_fill = outcome_data.get("entry_fill")
    exit_fill = outcome_data.get("exit_fill")

    risk_per_share = _safe_float(snapshot["risk_per_share"])
    position_size = _safe_int(snapshot["position_size"])

    result = compute_gross_net(
        entry_fill,
        exit_fill,
        risk_per_share,
        position_size,
    )

    t0_price = _safe_float(snapshot["price"])
    trigger_price = _safe_float(trigger.get("trigger_price"))

    absolute_move = None
    relative_move = None

    if t0_price is not None and t0_price > 0 and trigger_price is not None:
        absolute_move = (trigger_price - t0_price) / t0_price * 100

    planned_entry = _safe_float(snapshot["entry"])

    if (
        planned_entry is not None
        and planned_entry > 0
        and trigger_price is not None
    ):
        relative_move = (
            (trigger_price - planned_entry) / planned_entry * 100
        )

    entry_efficiency = None
    if (
        planned_entry is not None
        and planned_entry > 0
        and entry_fill is not None
    ):
        entry_efficiency = (
            (entry_fill - planned_entry) / planned_entry * 100
        )

    costs = result["costs"]

    exit_time_value = outcome_data.get("exit_time")
    exit_time_utc = _utc_string(exit_time_value) if exit_time_value else None

    cur.execute(
        """
        INSERT OR REPLACE INTO outcomes
        (
            snapshot_id,
            trigger_result_id,
            trigger_method,
            trigger_version,
            outcome_horizon,

            t0_price,

            mfe,
            mae,
            mfe_pct,
            mae_pct,

            time_to_mfe_sec,
            time_to_mae_sec,

            absolute_move_before_trigger_pct,
            relative_move_before_trigger_pct,

            entry_slippage_pct,
            entry_efficiency,

            exit_reason,
            exit_price,
            exit_time_utc,
            hold_minutes,

            gross_r,
            gross_pct,

            cost_spread,
            cost_slippage,
            cost_commission,
            cost_tax,
            cost_total,

            net_r,
            net_pct,
            outcome,
            net_r_status,

            exit_rules_version,
            cost_model_version
        )
        VALUES (
            ?, ?, ?, ?, ?,

            ?,

            ?, ?, ?, ?,

            ?, ?,

            ?, ?,

            ?, ?,

            ?, ?, ?, ?,

            ?, ?,

            ?, ?, ?, ?, ?,

            ?, ?, ?, ?,

            ?, ?
        )
        """,
        (
            snapshot_id,
            trigger_result_id,
            trigger["method"],
            TRIGGER_VERSION,
            horizon,

            t0_price,

            outcome_data.get("mfe"),
            outcome_data.get("mae"),
            outcome_data.get("mfe_pct"),
            outcome_data.get("mae_pct"),

            outcome_data.get("time_to_mfe_sec"),
            outcome_data.get("time_to_mae_sec"),

            absolute_move,
            relative_move,

            SLIPPAGE_PCT,
            entry_efficiency,

            outcome_data.get("exit_reason"),
            exit_fill,
            exit_time_utc,
            outcome_data.get("hold_minutes"),

            result["gross_r"],
            result["gross_pct"],

            0.0,
            0.0,
            costs["commission"],
            costs["tax"],
            costs["total"],

            result["net_r"],
            result["net_pct"],
            result["outcome"],
            result["net_r_status"],

            EXIT_RULES_VERSION,
            COST_MODEL_VERSION,
        ),
    )

    return result


# =====================================================================
# HORIZON HELPERS
# =====================================================================

def _index_at_or_before(df, target_time):
    indices = df.index <= target_time
    positions = indices.nonzero()[0] if hasattr(indices, "nonzero") else []
    if len(positions) == 0:
        return None
    return int(positions[-1])


def evaluate_momentum(df, trigger, snapshot):
    trigger_idx = trigger["idx"]
    trigger_time = df.index[trigger_idx]
    end_time = trigger_time + timedelta(minutes=MOMENTUM_WINDOW_MIN)

    mask = df.index <= end_time
    positions = mask.nonzero()[0]

    if len(positions) == 0:
        return None

    horizon_idx = int(positions[-1])

    entry_fill = _entry_fill_from_next_bar(df, trigger_idx)

    return evaluate_horizon(
        df,
        trigger_idx,
        entry_fill,
        _safe_float(snapshot["stop"]),
        _safe_float(snapshot["target_1"]),
        _safe_float(snapshot["target_2"]),
        horizon_idx,
    )


def evaluate_intraday(df, trigger, snapshot):
    trigger_idx = trigger["idx"]
    entry_fill = _entry_fill_from_next_bar(df, trigger_idx)

    return evaluate_horizon(
        df,
        trigger_idx,
        entry_fill,
        _safe_float(snapshot["stop"]),
        _safe_float(snapshot["target_1"]),
        _safe_float(snapshot["target_2"]),
        len(df) - 1,
    )


def fetch_daily_bars(ticker, scan_date):
    try:
        start = datetime.strptime(scan_date, "%Y-%m-%d")
        end = start + timedelta(days=7)

        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df

    except Exception as exc:
        print(f"[swing] {ticker} daily error: {type(exc).__name__}: {exc}")
        return pd.DataFrame()


def evaluate_swing(ticker, scan_date, trigger, snapshot):
    daily = fetch_daily_bars(ticker, scan_date)

    if daily.empty:
        return {
            "status": NET_R_STATUS_INCOMPLETE,
            "entry_fill": None,
            "exit_fill": None,
            "exit_reason": "INCOMPLETE_DATA",
        }

    trigger_time = trigger["time"]
    trigger_date = trigger_time.date()

    future = daily[daily.index.date >= trigger_date].head(4)

    if future.empty:
        return {
            "status": NET_R_STATUS_INCOMPLETE,
            "entry_fill": None,
            "exit_fill": None,
            "exit_reason": "HORIZON_END_NULL",
        }

    entry_fill = _safe_float(snapshot["entry"])

    if entry_fill is None or entry_fill <= 0:
        return {
            "status": NET_R_STATUS_NON_EXECUTABLE,
            "entry_fill": None,
            "exit_fill": None,
            "exit_reason": "NOT_EXECUTABLE",
        }

    stop = _safe_float(snapshot["stop"])
    risk = _safe_float(snapshot["risk_per_share"])

    if stop is None or risk is None or risk <= 0:
        return {
            "status": NET_R_STATUS_INVALID,
            "entry_fill": None,
            "exit_fill": None,
            "exit_reason": "INVALID_RISK",
        }

    t1 = _safe_float(snapshot["target_1"])
    t2 = _safe_float(snapshot["target_2"])

    mfe = entry_fill
    mae = entry_fill
    exit_price = None
    exit_reason = "HORIZON_END"
    half_exited = False

    for _, row in future.iterrows():
        high = _safe_float(row["High"])
        low = _safe_float(row["Low"])
        close = _safe_float(row["Close"])

        if high is None or low is None:
            continue

        mfe = max(mfe, high)
        mae = min(mae, low)

        current_stop = entry_fill if half_exited else stop

        if low <= current_stop:
            exit_price = current_stop * (1 - SLIPPAGE_PCT / 100)
            exit_reason = "STOP_HIT"
            break

        if not half_exited and high >= t1:
            half_exited = True

        if half_exited and high >= t2:
            t1_fill = t1 * (1 - SLIPPAGE_PCT / 100)
            t2_fill = t2 * (1 - SLIPPAGE_PCT / 100)
            exit_price = 0.5 * t1_fill + 0.5 * t2_fill
            exit_reason = "T2_HIT"
            break

    if exit_price is None:
        closes = future["Close"].dropna()
        if closes.empty:
            return {
                "status": NET_R_STATUS_INCOMPLETE,
                "entry_fill": None,
                "exit_fill": None,
                "exit_reason": "HORIZON_END_NULL",
            }
        close = float(closes.iloc[-1])
        exit_price = close * (1 - SLIPPAGE_PCT / 100)

    mfe_pct = (mfe - entry_fill) / entry_fill * 100
    mae_pct = (mae - entry_fill) / entry_fill * 100

    return {
        "status": NET_R_STATUS_VALID,
        "entry_fill": entry_fill,
        "exit_fill": exit_price,
        "exit_reason": exit_reason,
        "mfe": mfe,
        "mae": mae,
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "time_to_mfe_sec": None,
        "time_to_mae_sec": None,
        "hold_minutes": None,
    }


# =====================================================================
# SNAPSHOT EVALUATION
# =====================================================================

def evaluate_snapshot(cur, snapshot):
    snapshot_id = snapshot["snapshot_id"]
    ticker = snapshot["ticker"]
    scan_date = snapshot["scan_date"]

    entry = _safe_float(snapshot["entry"])
    stop = _safe_float(snapshot["stop"])
    t1 = _safe_float(snapshot["target_1"])
    t2 = _safe_float(snapshot["target_2"])

    # -------------------------------------------------------------
    # V5.0.6.1 — trigger_data_mode from pm_bars_json
    # -------------------------------------------------------------
    trigger_data_mode = "RTH_ONLY"
    try:
        raw_pm = snapshot["pm_bars_json"]
        if raw_pm:
            parsed = json.loads(raw_pm)
            if isinstance(parsed, list) and len(parsed) >= 5:
                trigger_data_mode = "PM_AWARE"
    except Exception:
        trigger_data_mode = "RTH_ONLY"

    # -------------------------------------------------------------
    # No valid plan
    # -------------------------------------------------------------
    if entry is None or stop is None or t1 is None or t2 is None:
        print(f"[evaluate] {ticker}: NO_TRADE / missing plan")

        write_trigger(
            cur,
            snapshot_id,
            "PMH_BREAKOUT_V1",
            False,
            None,
            None,
            None,
            "RTH",
            trigger_data_mode,
            {"reason": "NO_VALID_PLAN"},
        )
        return

    # -------------------------------------------------------------
    # RTH data
    # -------------------------------------------------------------
    df = fetch_rth_bars(ticker, scan_date)

    if df.empty:
        print(f"[evaluate] {ticker}: NO_RTH_DATA")

        for method in (
            "PMH_BREAKOUT_V1",
            "BREAKOUT_VOLUME_V1",
            "VWAP_RECLAIM_V1",
            "PULLBACK_RETEST_V1",
        ):
            write_trigger(
                cur,
                snapshot_id,
                method,
                False,
                None,
                None,
                None,
                "RTH",
                trigger_data_mode,
                {"reason": "NO_RTH_DATA"},
            )
        return

    # -------------------------------------------------------------
    # PM values
    # -------------------------------------------------------------
    pm_high = _safe_float(snapshot["pm_high"])
    pm_vwap = _safe_float(snapshot["pm_vwap"])

    atr = _safe_float(snapshot["atr"])
    if atr is not None and atr > 0:
        buffer = max(0.01, 0.05 * atr)
    else:
        buffer = max(0.01, entry * 0.005)

    # -------------------------------------------------------------
    # Four trigger methods
    # -------------------------------------------------------------
    triggers = []

    candidates = [
        detect_pmh_breakout(df, pm_high, buffer),
        detect_volume_breakout(df, pm_high, buffer),
        detect_vwap_reclaim(df, pm_vwap),
        detect_pullback_retest(df, pm_high, buffer),
    ]

    method_names = [
        "PMH_BREAKOUT_V1",
        "BREAKOUT_VOLUME_V1",
        "VWAP_RECLAIM_V1",
        "PULLBACK_RETEST_V1",
    ]

    # -------------------------------------------------------------
    # Write every trigger result.
    # -------------------------------------------------------------
    for method, trigger in zip(method_names, candidates):

        if trigger is None:
            write_trigger(
                cur,
                snapshot_id,
                method,
                False,
                None,
                None,
                None,
                "RTH",
                trigger_data_mode,
            )
            continue

        trigger["method"] = method
        trigger_time = trigger["time"]

        t0_time = pd.Timestamp(snapshot["snapshot_time_et"])
        if t0_time.tzinfo is None:
            t0_time = ET.localize(t0_time.to_pydatetime())
        else:
            t0_time = t0_time.tz_convert(ET)

        elapsed_sec = int((trigger_time - t0_time).total_seconds())

        trig_id = write_trigger(
            cur,
            snapshot_id,
            method,
            True,
            trigger_time,
            trigger["trigger_price"],
            elapsed_sec,
            "RTH",
            trigger_data_mode,
            trigger,
        )

        if trig_id is None:
            print(
                f"[evaluate] {ticker} {method}: "
                f"failed to obtain trigger_result_id"
            )
            continue

        trigger["trigger_result_id"] = trig_id
        triggers.append(trigger)

    # -------------------------------------------------------------
    # Evaluate outcomes for each trigger.
    # -------------------------------------------------------------
    for trigger in triggers:

        entry_fill = _entry_fill_from_next_bar(df, trigger["idx"])

        trig_rid = trigger["trigger_result_id"]

        if entry_fill is None:

            outcome_data = {
                "status": NET_R_STATUS_NON_EXECUTABLE,
                "entry_fill": None,
                "exit_fill": None,
                "exit_reason": "NOT_EXECUTABLE",
            }

            for horizon in ("MOMENTUM_90M", "INTRADAY_EOD"):
                write_outcome(
                    cur,
                    snapshot,
                    trigger,
                    trig_rid,
                    horizon,
                    outcome_data,
                )

            swing = {
                "status": NET_R_STATUS_NON_EXECUTABLE,
                "entry_fill": None,
                "exit_fill": None,
                "exit_reason": "NOT_EXECUTABLE",
            }
            write_outcome(
                cur,
                snapshot,
                trigger,
                trig_rid,
                "SWING_3D",
                swing,
            )
            continue

        # ---------------------------------------------------------
        # Momentum
        # ---------------------------------------------------------
        momentum = evaluate_momentum(df, trigger, snapshot)
        if momentum is not None:
            momentum["entry_fill"] = entry_fill
            write_outcome(
                cur,
                snapshot,
                trigger,
                trig_rid,
                "MOMENTUM_90M",
                momentum,
            )

        # ---------------------------------------------------------
        # Intraday
        # ---------------------------------------------------------
        intraday = evaluate_horizon(
            df,
            trigger["idx"],
            entry_fill,
            stop,
            t1,
            t2,
            len(df) - 1,
        )
        write_outcome(
            cur,
            snapshot,
            trigger,
            trig_rid,
            "INTRADAY_EOD",
            intraday,
        )

        # ---------------------------------------------------------
        # Swing
        # ---------------------------------------------------------
        swing = evaluate_swing(ticker, scan_date, trigger, snapshot)
        write_outcome(
            cur,
            snapshot,
            trigger,
            trig_rid,
            "SWING_3D",
            swing,
        )


# =====================================================================
# PERFORMANCE STATS
# =====================================================================

def update_stats(stats, result):
    status = result.get("net_r_status")
    net_r = result.get("net_r")

    if status == NET_R_STATUS_VALID and net_r is not None:
        net_r = float(net_r)
        stats["valid_net_r"] += 1
        stats["sum_net_r"] += net_r

        if net_r > 0.05:
            stats["wins"] += 1
        elif net_r < -0.05:
            stats["losses"] += 1
        else:
            stats["breakeven"] += 1
    else:
        stats["excluded_net_r"] += 1


def calculate_db_stats(cur, scan_date):
    rows = cur.execute(
        """
        SELECT
            outcome_horizon,
            net_r,
            net_r_status,
            outcome
        FROM outcomes o
        JOIN snapshots s
          ON s.snapshot_id = o.snapshot_id
        WHERE s.scan_date = ?
        """,
        (scan_date,),
    ).fetchall()

    stats = {
        "total_outcomes": len(rows),
        "valid_net_r": 0,
        "excluded_net_r": 0,
        "wins": 0,
        "losses": 0,
        "breakeven": 0,
        "sum_net_r": 0.0,
    }

    for row in rows:
        update_stats(stats, {
            "net_r": row["net_r"],
            "net_r_status": row["net_r_status"],
        })

    return stats


# =====================================================================
# MAIN
# =====================================================================

def evaluate_all(scan_date=None, force=False):
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}")
        return

    ensure_schema()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        if scan_date is None:
            row = cur.execute(
                "SELECT MAX(scan_date) FROM snapshots"
            ).fetchone()

            if not row or not row[0]:
                print("No snapshots.")
                return

            scan_date = row[0]

        print()
        print("=" * 80)
        print("DAYS-BOT V5.0.6.1 SNAPSHOT EVALUATOR")
        print(f"scan_date={scan_date}")
        print("=" * 80)

        if force:
            cur.execute(
                """
                DELETE FROM outcomes
                WHERE snapshot_id IN (
                    SELECT snapshot_id FROM snapshots WHERE scan_date = ?
                )
                """,
                (scan_date,),
            )
            cur.execute(
                """
                DELETE FROM trigger_results
                WHERE snapshot_id IN (
                    SELECT snapshot_id FROM snapshots WHERE scan_date = ?
                )
                """,
                (scan_date,),
            )
            conn.commit()

        snapshots = cur.execute(
            """
            SELECT * FROM snapshots
            WHERE scan_date = ?
            ORDER BY snapshot_id
            """,
            (scan_date,),
        ).fetchall()

        print(f"Snapshots: {len(snapshots)}")

        if not snapshots:
            return

        for snapshot in snapshots:
            try:
                evaluate_snapshot(cur, snapshot)
                conn.commit()
            except Exception as exc:
                print(
                    f"[evaluate] {snapshot['ticker']} ERROR: "
                    f"{type(exc).__name__}: {exc}"
                )
                conn.rollback()

        stats = calculate_db_stats(cur, scan_date)

        print()
        print("=" * 80)
        print(f"SUMMARY — {scan_date}")
        print("=" * 80)
        print(f"Total outcomes:     {stats['total_outcomes']}")
        print(f"Valid Net-R:        {stats['valid_net_r']}")
        print(f"Excluded Net-R:     {stats['excluded_net_r']}")

        if stats["valid_net_r"] > 0:
            avg_net = stats["sum_net_r"] / stats["valid_net_r"]
            win_rate = stats["wins"] / stats["valid_net_r"] * 100

            print(f"Avg Net R:          {avg_net:.3f}")
            print(f"Win Rate:           {win_rate:.1f}%")
            print(
                f"W / L / BE:         "
                f"{stats['wins']} / {stats['losses']} / {stats['breakeven']}"
            )
        else:
            print("Avg Net R:          N/A")
            print("Win Rate:           N/A")

        print("=" * 80)

    finally:
        conn.close()


# =====================================================================
# CLI
# =====================================================================

if __name__ == "__main__":
    parser = ArgumentParser(
        description="DAYS-BOT V5.0.6.1 Snapshot Evaluator"
    )
    parser.add_argument(
        "--scan-date",
        type=str,
        default=None,
        help="Scan date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete derived trigger/outcome rows and reevaluate.",
    )
    args = parser.parse_args()

    evaluate_all(scan_date=args.scan_date, force=args.force)
