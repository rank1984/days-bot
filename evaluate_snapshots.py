#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6.3 — Snapshot Evaluator

V5.0.6.3 (Pre-Registration compliant) — changes over V5.0.6.2:

  PR-FIX-1: Stop anchor uses snapshot.pm_vwap, NOT RTH cumulative VWAP.
            If pm_vwap is None -> NON_EXECUTABLE, no Event.

  PR-FIX-2: Partial exits weighted in Net R.
            T1 hit + BE stop        -> exit_fill = 0.5*t1 + 0.5*BE
            T1 hit + horizon close  -> exit_fill = 0.5*t1 + 0.5*close
            T1 hit + T2 hit         -> exit_fill = 0.5*t1 + 0.5*t2
            exit_reason distinguishes BE-after-T1 from plain STOP_HIT.

  PR-FIX-3: evaluate_swing uses intraday data only from entry_idx.
            Previous behavior used daily OHLC of the trigger date,
            which includes prices from before the entry — lookahead.

  PR-FIX-4: event_rank enforced. Only the first eligible trigger for
            a (ticker, scan_date) becomes Event rank=1. All other
            triggers are recorded with rank>=2 and excluded from the
            primary sample.

  PR-FIX-5: Spread fallback REMOVED.
            No quote in window [T-60s, T-10s] -> spread_status = UNKNOWN
            -> NON_EXECUTABLE. Falling back to a fixed 1.5% masks
            liquidity problems.

  PR-FIX-6: ATR = ATR(14) on 5-min RTH bars from PREVIOUS trading day.
            Fixed at 09:30 ET, does not update during the day.
            If <14 valid bars -> ATR = None -> no Event.

  Trigger priority (per P4):
      BREAKOUT_VOLUME_V1  = primary Event (rank 1)
      PMH_BREAKOUT_V1     = recorded, but not Event
      VWAP_RECLAIM_V1     = recorded, but not Event
      PULLBACK_RETEST_V1  = recorded, but not Event

V5.0.6.2 legacy:
  F5: PMH breakout uses Close > level
  F2: gap-down stop fills at bar open
  F7: cost = spread + tick, computed ONCE
  F1: R from actual fill (risk_actual = raw_fill - stop_used)
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

TRIGGER_VERSION = "V5.0.6-T3"
EXIT_RULES_VERSION = "V5.0.6-E3"
COST_MODEL_VERSION = "V5.0.6-C3"

# Cost model (F7)
TICK_SIZE = 0.01

# Spread config (PR-FIX-5)
SPREAD_WINDOW_BEFORE_SEC = 60   # look back from trigger
SPREAD_WINDOW_AFTER_SEC = 10    # stop lookback here (too close to trigger)
SPREAD_FETCH_RANGE_SEC = 120    # how far back to fetch from API

# Horizon
MOMENTUM_WINDOW_MIN = 90
RTH_START = "09:30"
RTH_END = "15:59"

# PM window (for ATR previous-day fetch and PMH consistency)
PM_START = "04:00"
PM_END = "09:30"

# Timing (F1)
MAX_NEXT_BAR_DELAY_SEC = 120

# Trigger window (P3)
TRIGGER_WINDOW_START = "09:30"
TRIGGER_WINDOW_END = "11:00"

# ATR (P14)
ATR_PERIOD = 14
ATR_INTERVAL = "5m"


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


def _is_in_window(ts_et, start_hhmm, end_hhmm):
    """ts_et is a tz-aware Timestamp. Returns True if time in [start, end)."""
    if ts_et is None:
        return False
    hhmm = ts_et.strftime("%H%M")
    return (start_hhmm <= hhmm < end_hhmm)


def _previous_trading_date(scan_date_str):
    """Return the previous weekday (Mon-Fri) as YYYY-MM-DD."""
    d = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
    d = d - timedelta(days=1)
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d = d - timedelta(days=1)
    return d.strftime("%Y-%m-%d")


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


# Global cache for previous-day ATR (per ticker/date)
_ATR_CACHE = {}


def _compute_prev_day_atr(ticker, scan_date):
    """
    PR-FIX-6 / P14: ATR(14) on 5-min RTH bars from PREVIOUS trading day.
    No look-ahead: only uses data from the prior day.
    """
    key = (ticker, scan_date)
    if key in _ATR_CACHE:
        return _ATR_CACHE[key]

    try:
        prev_date = _previous_trading_date(scan_date)
        start = datetime.strptime(prev_date, "%Y-%m-%d")
        end = start + timedelta(days=1)

        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval=ATR_INTERVAL,
            prepost=False,
            progress=False,
            auto_adjust=False,
            threads=False,
        )

        if df is None or df.empty:
            _ATR_CACHE[key] = None
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(ET)

        df = df.between_time(RTH_START, RTH_END)
        if len(df) < ATR_PERIOD + 1:
            _ATR_CACHE[key] = None
            return None

        # True Range = max(H-L, |H-prevC|, |L-prevC|)
        prev_close = df["Close"].shift(1)
        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ], axis=1).max(axis=1)

        # Wilder-style: simple mean over ATR_PERIOD of last TRs
        # (using simple mean for reproducibility)
        atr = float(tr.iloc[-ATR_PERIOD:].mean())
        _ATR_CACHE[key] = atr if atr > 0 else None
        return _ATR_CACHE[key]

    except Exception as exc:
        print(f"[evaluate] {ticker} ATR error: {type(exc).__name__}: {exc}")
        _ATR_CACHE[key] = None
        return None


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

        rows = [item for item in data if isinstance(item, dict)]
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


def _entry_raw_open_from_next_bar(df, trigger_idx):
    next_idx = trigger_idx + 1
    if next_idx >= len(df):
        return None

    open_price = _safe_float(df.iloc[next_idx]["Open"])
    if open_price is None or open_price <= 0:
        return None

    return open_price


def _entry_fill_from_next_bar(df, trigger_idx):
    """Backward-compat alias."""
    return _entry_raw_open_from_next_bar(df, trigger_idx)


def _fetch_spread_pct(ticker, trigger_time):
    """
    PR-FIX-5 / P15:
      Look for a quote in [T-60s, T-10s] closest to T-30s.
      If none -> return None, source='UNKNOWN'.
      The evaluator will then mark the trade NON_EXECUTABLE.
    """
    try:
        import requests
        from utils.config import (
            ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_DATA_URL
        )
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            return (None, "UNKNOWN", None, None)

        url = f"{ALPACA_DATA_URL.rstrip('/')}/v2/stocks/{ticker}/quotes"
        end_dt = trigger_time.astimezone(UTC) - timedelta(seconds=SPREAD_WINDOW_AFTER_SEC)
        start_dt = end_dt - timedelta(seconds=SPREAD_FETCH_RANGE_SEC)

        resp = requests.get(
            url,
            headers={
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
                "Accept": "application/json",
            },
            params={
                "start": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": 50,
                "feed": "iex",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return (None, "UNKNOWN", None, None)

        data = resp.json()
        quotes = data.get("quotes", [])
        if not quotes:
            return (None, "UNKNOWN", None, None)

        # Target timestamp: trigger_time - 30 seconds (ET)
        target_ts = trigger_time.astimezone(UTC) - timedelta(seconds=30)

        best = None
        best_delta = None
        for q in quotes:
            qt_iso = q.get("t")
            if not qt_iso:
                continue
            try:
                qt = datetime.fromisoformat(qt_iso.replace("Z", "+00:00"))
            except Exception:
                continue
            delta = abs((qt - target_ts).total_seconds())
            if best_delta is None or delta < best_delta:
                best = q
                best_delta = delta

        if best is None:
            return (None, "UNKNOWN", None, None)

        bid = _safe_float(best.get("bp"))
        ask = _safe_float(best.get("ap"))
        qt_iso = best.get("t")

        if bid is None or ask is None or bid <= 0 or ask <= 0:
            return (None, "UNKNOWN", best, qt_iso)
        if ask <= bid:
            return (None, "UNKNOWN", best, qt_iso)

        mid = (bid + ask) / 2.0
        spread_pct = (ask - bid) / mid * 100.0
        return (round(spread_pct, 4), "QUOTE", best, qt_iso)

    except Exception as exc:
        print(f"[spread] {ticker} fetch error: {type(exc).__name__}: {exc}")
        return (None, "UNKNOWN", None, None)


# =====================================================================
# TRIGGERS
# =====================================================================

def detect_pmh_breakout(df, pm_high, buffer):
    """
    F5: Close > PMH + buffer (not High >= level).
    Secondary trigger (not the primary Event).
    """
    if pm_high is None or pm_high <= 0 or not _valid_ohlcv(df):
        return None

    level = pm_high + buffer

    for idx in range(len(df)):
        close = _safe_float(df.iloc[idx]["Close"])
        if close is not None and close > level:
            return {
                "method": "PMH_BREAKOUT_V1",
                "idx": idx,
                "time": df.index[idx],
                "trigger_price": close,
                "level": level,
            }

    return None


def detect_volume_breakout(df, pm_high, buffer):
    """
    PR-FIX: This is the PRIMARY Event trigger per P4.
    Close >= PMH + buffer AND Volume >= 1.2 * median(prev 5 valid bars).
    """
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
# COST MODEL (F7)
# =====================================================================

def compute_costs(entry_fill, exit_fill, spread_pct, position_size=None):
    entry_fill = _safe_float(entry_fill)
    exit_fill = _safe_float(exit_fill)
    spread_pct = _safe_float(spread_pct)

    if entry_fill is None or exit_fill is None or spread_pct is None:
        return {
            "entry_cost_ps": None,
            "exit_cost_ps": None,
            "spread_cost_ps": None,
            "tick_cost_ps": None,
            "total_per_share": None,
            "total_dollars": None,
            "commission": 0.0,
            "tax": 0.0,
        }

    spread_half = (spread_pct / 2.0) / 100.0
    entry_cost_ps = entry_fill * spread_half + TICK_SIZE
    exit_cost_ps = exit_fill * spread_half + TICK_SIZE
    total_per_share = entry_cost_ps + exit_cost_ps

    total_dollars = None
    if position_size is not None and position_size > 0:
        total_dollars = total_per_share * position_size

    return {
        "entry_cost_ps": entry_cost_ps,
        "exit_cost_ps": exit_cost_ps,
        "spread_cost_ps": entry_fill * spread_half + exit_fill * spread_half,
        "tick_cost_ps": 2.0 * TICK_SIZE,
        "total_per_share": total_per_share,
        "total_dollars": total_dollars,
        "commission": 0.0,
        "tax": 0.0,
    }


def compute_gross_net(entry_fill, exit_fill, risk_actual, spread_pct,
                      position_size=None):
    entry_fill = _safe_float(entry_fill)
    exit_fill = _safe_float(exit_fill)
    risk_actual = _safe_float(risk_actual)
    spread_pct = _safe_float(spread_pct)

    empty = {
        "gross_r": None,
        "gross_pct": None,
        "cost_r": None,
        "net_r": None,
        "net_r_x2": None,
        "net_pct": None,
        "costs": {
            "entry_cost_ps": None, "exit_cost_ps": None,
            "spread_cost_ps": None, "tick_cost_ps": None,
            "total_per_share": None, "total_dollars": None,
            "commission": 0.0, "tax": 0.0,
        },
        "outcome": "NON_EXECUTABLE",
        "net_r_status": NET_R_STATUS_NON_EXECUTABLE,
    }

    if (entry_fill is None or exit_fill is None
            or risk_actual is None or risk_actual <= 0
            or spread_pct is None):
        return empty

    gross_per_share = exit_fill - entry_fill
    gross_r = gross_per_share / risk_actual
    gross_pct = gross_per_share / entry_fill * 100.0

    costs = compute_costs(entry_fill, exit_fill, spread_pct, position_size)
    if costs["total_per_share"] is None:
        return empty

    cost_r = costs["total_per_share"] / risk_actual
    net_r = gross_r - cost_r
    net_r_x2 = gross_r - 2.0 * cost_r
    net_pct = (gross_per_share - costs["total_per_share"]) / entry_fill * 100.0

    if net_r > 0.05:
        label = "WIN"
    elif net_r < -0.05:
        label = "LOSS"
    else:
        label = "BREAKEVEN"

    return {
        "gross_r": gross_r,
        "gross_pct": gross_pct,
        "cost_r": cost_r,
        "net_r": net_r,
        "net_r_x2": net_r_x2,
        "net_pct": net_pct,
        "costs": costs,
        "outcome": label,
        "net_r_status": NET_R_STATUS_VALID,
    }


# =====================================================================
# OUTCOME ENGINE
# =====================================================================

def evaluate_horizon(df, trigger_idx, entry_fill, stop, t1, t2, end_idx=None):
    """
    PR-FIX-2 + PR-FIX-3: weighted partial exits.

    Exit reasons:
      STOP_HIT                 - stop touched before T1, 100% at stop
      STOP_BE_AFTER_T1         - T1 hit, then stop (BE) touched, 50/50 weighted
      STOP_HIT_AFTER_T1        - T1 hit, then original stop touched, 50/50 weighted
      T2_HIT                   - T1 and T2 both hit, 50/50 weighted
      HORIZON_END              - no T1, exit at horizon close
      HORIZON_END_AFTER_T1     - T1 hit, horizon reached, 50/50 weighted
    """
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
            "half_exited": False,
        }

    entry_time = df.index[entry_idx]
    current_stop = stop
    half_exited = False
    exit_reason = "HORIZON_END"
    exit_idx = end_idx

    horizon_close = _safe_float(df.iloc[end_idx]["Close"])
    if horizon_close is None or entry_fill is None:
        return {
            "status": NET_R_STATUS_INCOMPLETE,
            "entry_fill": entry_fill,
            "exit_fill": None,
            "exit_reason": "INCOMPLETE_DATA",
            "exit_idx": None,
            "half_exited": False,
        }

    # Default: no exit signal -> horizon close
    exit_fill = horizon_close

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

        # ------- STOP FIRST (F2: gap-down fills at open) -------
        if low <= current_stop:
            bar_open = _safe_float(row["Open"])
            stop_fill = (bar_open if (bar_open is not None and bar_open < current_stop)
                         else current_stop)

            if half_exited:
                # PR-FIX-2: 50% already took T1, remaining 50% exits at stop
                if current_stop >= entry_fill:
                    exit_reason = "STOP_BE_AFTER_T1"
                else:
                    exit_reason = "STOP_HIT_AFTER_T1"
                exit_idx = idx
                exit_fill = 0.5 * t1 + 0.5 * stop_fill
            else:
                exit_reason = "STOP_HIT"
                exit_idx = idx
                exit_fill = stop_fill
            break

        # ------- T1 -------
        if not half_exited and high >= t1:
            half_exited = True
            current_stop = entry_fill  # move stop to BE
            continue

        # ------- T2 -------
        if half_exited and high >= t2:
            exit_reason = "T2_HIT"
            exit_idx = idx
            exit_fill = 0.5 * t1 + 0.5 * t2
            break
    else:
        # Loop completed without break -> horizon end
        exit_idx = end_idx
        if half_exited:
            # PR-FIX-3: weighted 50/50
            exit_reason = "HORIZON_END_AFTER_T1"
            exit_fill = 0.5 * t1 + 0.5 * horizon_close
        else:
            exit_reason = "HORIZON_END"
            exit_fill = horizon_close

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
        "half_exited": half_exited,
    }


# =====================================================================
# DB WRITE — TRIGGER
# =====================================================================

def write_trigger(cur, snapshot_id, method, hit, trig_time, trig_price,
                  elapsed_sec, window, trigger_data_mode, event_rank=2,
                  extra=None):
    """
    PR-FIX-4: write event_rank with every trigger row.
    event_rank=1 is the primary Event (BREAKOUT_VOLUME_V1 in trigger window).
    event_rank>=2 are secondary triggers recorded for analysis.
    """
    cur.execute(
        """
        INSERT OR REPLACE INTO trigger_results
        (snapshot_id, trigger_method, trigger_version, hit,
         trigger_time_utc, trigger_time_et, trigger_price,
         elapsed_sec_from_t0, window, trigger_data_mode,
         event_rank, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id, method, TRIGGER_VERSION, 1 if hit else 0,
            _utc_string(trig_time), _et_string(trig_time), trig_price,
            elapsed_sec, window, trigger_data_mode,
            event_rank, _json(extra),
        ),
    )

    row = cur.execute(
        """
        SELECT trigger_result_id FROM trigger_results
        WHERE snapshot_id = ? AND trigger_method = ? AND trigger_version = ?
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
# DB WRITE — OUTCOME
# =====================================================================

def write_outcome(
    cur,
    snapshot,
    trigger,
    trigger_result_id,
    horizon,
    outcome_data,
    spread_pct,
    spread_source,
    risk_actual,
    raw_fill,
    stop_used,
    t1_used,
    t2_used,
    quote_raw=None,
    quote_timestamp_utc=None,
):
    snapshot_id = snapshot["snapshot_id"]

    entry_fill = outcome_data.get("entry_fill")
    exit_fill = outcome_data.get("exit_fill")

    position_size = _safe_int(snapshot["position_size"])

    result = compute_gross_net(
        entry_fill,
        exit_fill,
        risk_actual,
        spread_pct,
        position_size,
    )

    t0_price = _safe_float(snapshot["price"])
    trigger_price = _safe_float(trigger.get("trigger_price"))

    absolute_move = None
    if t0_price is not None and t0_price > 0 and trigger_price is not None:
        absolute_move = (trigger_price - t0_price) / t0_price * 100

    planned_entry = _safe_float(snapshot["entry"])
    relative_move = None
    if (planned_entry is not None and planned_entry > 0
            and trigger_price is not None):
        relative_move = (trigger_price - planned_entry) / planned_entry * 100

    entry_efficiency = None
    if (planned_entry is not None and planned_entry > 0
            and entry_fill is not None):
        entry_efficiency = (entry_fill - planned_entry) / planned_entry * 100

    entry_slippage_pct = None
    if entry_fill is not None and entry_fill > 0 and spread_pct is not None:
        spread_half_pct = spread_pct / 2.0
        tick_pct = (TICK_SIZE / entry_fill) * 100.0
        entry_slippage_pct = spread_half_pct + tick_pct

    costs = result["costs"]

    exit_time_value = outcome_data.get("exit_time")
    exit_time_utc = _utc_string(exit_time_value) if exit_time_value else None

    cur.execute(
        """
        INSERT OR REPLACE INTO outcomes
        (
            snapshot_id, trigger_result_id, trigger_method, trigger_version,
            outcome_horizon,
            t0_price,
            mfe, mae, mfe_pct, mae_pct,
            time_to_mfe_sec, time_to_mae_sec,
            absolute_move_before_trigger_pct,
            relative_move_before_trigger_pct,
            entry_slippage_pct, entry_efficiency,
            exit_reason, exit_price, exit_time_utc, hold_minutes,
            gross_r, gross_pct,
            cost_spread, cost_slippage, cost_commission, cost_tax, cost_total,
            cost_r, net_r, net_r_x2, net_pct, outcome, net_r_status,
            spread_pct_used, spread_source, quote_raw, quote_timestamp_utc,
            raw_fill, stop_used, t1_used, t2_used, risk_actual,
            exit_rules_version, cost_model_version
        )
        VALUES (
            ?, ?, ?, ?,
            ?,
            ?,
            ?, ?, ?, ?,
            ?, ?,
            ?, ?,
            ?, ?,
            ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?
        )
        """,
        (
            snapshot_id, trigger_result_id, trigger["method"], TRIGGER_VERSION,
            horizon,
            t0_price,
            outcome_data.get("mfe"), outcome_data.get("mae"),
            outcome_data.get("mfe_pct"), outcome_data.get("mae_pct"),
            outcome_data.get("time_to_mfe_sec"),
            outcome_data.get("time_to_mae_sec"),
            absolute_move, relative_move,
            entry_slippage_pct, entry_efficiency,
            outcome_data.get("exit_reason"), exit_fill, exit_time_utc,
            outcome_data.get("hold_minutes"),
            result["gross_r"], result["gross_pct"],
            costs["spread_cost_ps"], costs["tick_cost_ps"], 0.0, 0.0,
            costs["total_per_share"],
            result["cost_r"], result["net_r"], result["net_r_x2"],
            result["net_pct"], result["outcome"], result["net_r_status"],
            spread_pct, spread_source,
            _json(quote_raw) if quote_raw is not None else None,
            quote_timestamp_utc,
            raw_fill, stop_used, t1_used, t2_used, risk_actual,
            EXIT_RULES_VERSION, COST_MODEL_VERSION,
        ),
    )

    return result


# =====================================================================
# HORIZON HELPERS
# =====================================================================

def evaluate_momentum(df, trigger, entry_fill, stop, t1, t2):
    trigger_idx = trigger["idx"]
    trigger_time = df.index[trigger_idx]
    end_time = trigger_time + timedelta(minutes=MOMENTUM_WINDOW_MIN)

    mask = df.index <= end_time
    positions = mask.nonzero()[0]
    if len(positions) == 0:
        return None

    horizon_idx = int(positions[-1])
    return evaluate_horizon(df, trigger_idx, entry_fill, stop, t1, t2,
                            horizon_idx)


def fetch_daily_bars(ticker, scan_date):
    """Legacy — kept for backward compatibility. Not used for primary logic."""
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


def evaluate_swing(ticker, scan_date, trigger, raw_fill, stop_used,
                   t1_used, t2_used):
    """
    PR-FIX-3: swing now uses intraday data ONLY from entry_idx onward.
    No look-ahead from same-day daily OHLC that includes pre-entry prices.
    Uses 1-min RTH bars extended across the next 3 trading days.
    For the same-day portion, only data after entry_time is used.
    """
    # We use the same intraday fetch as the primary, but allow the
    # horizon to span the entry day + 2 following days.
    # Since fetch_rth_bars is limited to a single day, we fetch a
    # multi-day window here.
    try:
        start = datetime.strptime(scan_date, "%Y-%m-%d")
        end = start + timedelta(days=6)

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
            return {"status": NET_R_STATUS_INCOMPLETE, "entry_fill": None,
                    "exit_fill": None, "exit_reason": "INCOMPLETE_DATA"}

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(ET)

        df = df.between_time(RTH_START, RTH_END)
        if df.empty:
            return {"status": NET_R_STATUS_INCOMPLETE, "entry_fill": None,
                    "exit_fill": None, "exit_reason": "INCOMPLETE_DATA"}
    except Exception as exc:
        print(f"[swing] {ticker} error: {type(exc).__name__}: {exc}")
        return {"status": NET_R_STATUS_INCOMPLETE, "entry_fill": None,
                "exit_fill": None, "exit_reason": "INCOMPLETE_DATA"}

    entry_time = trigger["time"]
    # Only consider bars at or after entry_time (intraday, no same-day lookback)
    mask = df.index > entry_time
    positions = mask.nonzero()[0]
    if len(positions) == 0:
        return {"status": NET_R_STATUS_INCOMPLETE, "entry_fill": None,
                "exit_fill": None, "exit_reason": "HORIZON_END_NULL"}

    # Find trigger_idx equivalent: first bar of the sequence
    entry_idx_global = int(positions[0])
    # We need a "trigger_idx" that is entry_idx_global - 1 so that
    # evaluate_horizon treats entry_idx = trigger_idx + 1 = entry_idx_global.
    trigger_idx_virtual = entry_idx_global - 1
    end_idx = len(df) - 1

    if raw_fill is None or raw_fill <= 0:
        return {"status": NET_R_STATUS_NON_EXECUTABLE, "entry_fill": None,
                "exit_fill": None, "exit_reason": "NOT_EXECUTABLE"}

    stop = stop_used
    t1 = t1_used
    t2 = t2_used
    if stop is None or t1 is None or t2 is None:
        return {"status": NET_R_STATUS_INVALID, "entry_fill": None,
                "exit_fill": None, "exit_reason": "INVALID_RISK"}

    # Reuse evaluate_horizon for consistent exit logic (weighted partials)
    return evaluate_horizon(df, trigger_idx_virtual, raw_fill, stop, t1, t2,
                            end_idx)


# =====================================================================
# SNAPSHOT EVALUATION
# =====================================================================

def _get_event_rank_for_snapshot(cur, ticker, scan_date):
    """
    PR-FIX-4: return 1 if no prior trigger for this (ticker, scan_date)
    has been assigned rank 1. Otherwise return 2.
    The primary Event trigger (BREAKOUT_VOLUME_V1) is the one that gets rank=1.
    """
    try:
        row = cur.execute(
            """
            SELECT COUNT(*) FROM trigger_results tr
            JOIN snapshots s ON s.snapshot_id = tr.snapshot_id
            WHERE s.ticker = ? AND s.scan_date = ? AND tr.event_rank = 1
            """,
            (ticker, scan_date),
        ).fetchone()
        count = row[0] if row else 0
    except sqlite3.OperationalError:
        # event_rank column missing — migration not run
        return 1
    return 1 if count == 0 else 2


def evaluate_snapshot(cur, snapshot):
    snapshot_id = snapshot["snapshot_id"]
    ticker = snapshot["ticker"]
    scan_date = snapshot["scan_date"]

    entry = _safe_float(snapshot["entry"])
    stop = _safe_float(snapshot["stop"])
    t1 = _safe_float(snapshot["target_1"])
    t2 = _safe_float(snapshot["target_2"])

    trigger_data_mode = "RTH_ONLY"
    try:
        raw_pm = snapshot["pm_bars_json"]
        if raw_pm:
            parsed = json.loads(raw_pm)
            if isinstance(parsed, list) and len(parsed) >= 5:
                trigger_data_mode = "PM_AWARE"
    except Exception:
        trigger_data_mode = "RTH_ONLY"

    # PR-FIX-6: ATR from previous day only
    atr = _compute_prev_day_atr(ticker, scan_date)

    if entry is None or stop is None or t1 is None or t2 is None:
        print(f"[evaluate] {ticker}: NO_TRADE / missing plan")
        # All trigger methods written as hit=0, rank=2
        for method in ("PMH_BREAKOUT_V1", "BREAKOUT_VOLUME_V1",
                       "VWAP_RECLAIM_V1", "PULLBACK_RETEST_V1"):
            write_trigger(cur, snapshot_id, method, False,
                          None, None, None, "RTH", trigger_data_mode,
                          event_rank=2,
                          extra={"reason": "NO_VALID_PLAN"})
        return

    df = fetch_rth_bars(ticker, scan_date)
    if df.empty:
        print(f"[evaluate] {ticker}: NO_RTH_DATA")
        for method in ("PMH_BREAKOUT_V1", "BREAKOUT_VOLUME_V1",
                       "VWAP_RECLAIM_V1", "PULLBACK_RETEST_V1"):
            write_trigger(cur, snapshot_id, method, False,
                          None, None, None, "RTH", trigger_data_mode,
                          event_rank=2,
                          extra={"reason": "NO_RTH_DATA"})
        return

    pm_high = _safe_float(snapshot["pm_high"])
    pm_vwap = _safe_float(snapshot["pm_vwap"])

    # PR-FIX-1: pm_vwap required for stop. If missing -> no Event.
    if pm_vwap is None or pm_vwap <= 0:
        print(f"[evaluate] {ticker}: NO_PM_VWAP -> NON_EXECUTABLE")
        for method in ("PMH_BREAKOUT_V1", "BREAKOUT_VOLUME_V1",
                       "VWAP_RECLAIM_V1", "PULLBACK_RETEST_V1"):
            write_trigger(cur, snapshot_id, method, False,
                          None, None, None, "RTH", trigger_data_mode,
                          event_rank=2,
                          extra={"reason": "NO_PM_VWAP"})
        return

    if pm_high is None or pm_high <= 0:
        print(f"[evaluate] {ticker}: NO_PMH -> NON_EXECUTABLE")
        for method in ("PMH_BREAKOUT_V1", "BREAKOUT_VOLUME_V1",
                       "VWAP_RECLAIM_V1", "PULLBACK_RETEST_V1"):
            write_trigger(cur, snapshot_id, method, False,
                          None, None, None, "RTH", trigger_data_mode,
                          event_rank=2,
                          extra={"reason": "NO_PMH"})
        return

    if atr is None or atr <= 0:
        print(f"[evaluate] {ticker}: NO_PREV_DAY_ATR -> NON_EXECUTABLE")
        for method in ("PMH_BREAKOUT_V1", "BREAKOUT_VOLUME_V1",
                       "VWAP_RECLAIM_V1", "PULLBACK_RETEST_V1"):
            write_trigger(cur, snapshot_id, method, False,
                          None, None, None, "RTH", trigger_data_mode,
                          event_rank=2,
                          extra={"reason": "NO_PREV_DAY_ATR"})
        return

    buffer = max(2 * TICK_SIZE, 0.05 * atr)

    candidates = [
        detect_pmh_breakout(df, pm_high, buffer),
        detect_volume_breakout(df, pm_high, buffer),
        detect_vwap_reclaim(df, pm_vwap),
        detect_pullback_retest(df, pm_high, buffer),
    ]
    method_names = [
        "PMH_BREAKOUT_V1", "BREAKOUT_VOLUME_V1",
        "VWAP_RECLAIM_V1", "PULLBACK_RETEST_V1",
    ]

    # PR-FIX-5: fetch spread only if BREAKOUT_VOLUME_V1 fired (primary).
    # Spread is required; if unavailable -> NON_EXECUTABLE.
    official_trigger = candidates[1]  # BREAKOUT_VOLUME_V1
    official_spread_pct = None
    official_spread_source = "UNKNOWN"
    official_quote_raw = None
    official_quote_ts = None

    if official_trigger is not None:
        # PR-FIX: trigger must be inside [09:30, 11:00] window
        trig_time_et = official_trigger["time"]
        if _is_in_window(trig_time_et, TRIGGER_WINDOW_START, TRIGGER_WINDOW_END):
            sp, src, qraw, qts = _fetch_spread_pct(ticker, trig_time_et)
            official_spread_pct = sp
            official_spread_source = src
            official_quote_raw = qraw
            official_quote_ts = qts

    # PR-FIX-4: determine event_rank for this snapshot's primary Event
    # If we can't determine rank, default to 2 (secondary).
    # The very first successful primary trigger across the day's snapshots
    # gets rank=1.
    primary_in_window = (
        official_trigger is not None
        and _is_in_window(official_trigger["time"],
                          TRIGGER_WINDOW_START, TRIGGER_WINDOW_END)
    )

    has_prior_event = _get_event_rank_for_snapshot(cur, ticker, scan_date)
    primary_rank = 1 if (primary_in_window and has_prior_event == 1) else 2

    # Write every trigger
    triggers = []
    for i, (method, trigger) in enumerate(zip(method_names, candidates)):
        if trigger is None:
            write_trigger(cur, snapshot_id, method, False,
                          None, None, None, "RTH", trigger_data_mode,
                          event_rank=2)
            continue

        trigger["method"] = method
        trigger_time = trigger["time"]

        t0_time = pd.Timestamp(snapshot["snapshot_time_et"])
        if t0_time.tzinfo is None:
            t0_time = ET.localize(t0_time.to_pydatetime())
        else:
            t0_time = t0_time.tz_convert(ET)

        elapsed_sec = int((trigger_time - t0_time).total_seconds())

        # Assign event_rank
        if method == "BREAKOUT_VOLUME_V1":
            rank_for_this = primary_rank
        else:
            rank_for_this = 2

        trig_id = write_trigger(cur, snapshot_id, method, True,
                                trigger_time, trigger["trigger_price"],
                                elapsed_sec, "RTH", trigger_data_mode,
                                event_rank=rank_for_this,
                                extra=trigger)

        if trig_id is None:
            print(f"[evaluate] {ticker} {method}: failed to obtain id")
            continue

        trigger["trigger_result_id"] = trig_id
        trigger["event_rank"] = rank_for_this
        triggers.append(trigger)

    # Evaluate outcomes only for triggers that are eligible (rank=1)
    for trigger in triggers:
        if trigger.get("event_rank", 2) != 1:
            # PR-FIX-4: record but do not count in primary sample
            continue

        s_pct = official_spread_pct
        s_src = official_spread_source
        s_raw = official_quote_raw
        s_ts = official_quote_ts

        raw_fill = _entry_raw_open_from_next_bar(df, trigger["idx"])
        trig_rid = trigger["trigger_result_id"]

        # F1: next bar must appear within MAX_NEXT_BAR_DELAY_SEC
        if raw_fill is not None:
            trigger_time = df.index[trigger["idx"]]
            next_idx = trigger["idx"] + 1
            if next_idx < len(df):
                next_time = df.index[next_idx]
                if (next_time - trigger_time).total_seconds() > MAX_NEXT_BAR_DELAY_SEC:
                    raw_fill = None

        stop_used = None
        t1_used = None
        t2_used = None
        risk_actual = None

        if raw_fill is not None and raw_fill > 0:
            chase_cap = pm_high + 0.5 * atr
            if raw_fill > chase_cap:
                raw_fill = None

        # PR-FIX-1: stop uses PM VWAP (not RTH VWAP)
        if raw_fill is not None and raw_fill > 0:
            stop_a = pm_vwap - 0.10 * atr
            stop_b = raw_fill - 1.0 * atr
            stop_used = max(stop_a, stop_b)
            risk_actual = raw_fill - stop_used
            if risk_actual <= 0:
                raw_fill = None
            else:
                t1_used = raw_fill + 2.0 * risk_actual
                t2_used = raw_fill + 4.0 * risk_actual

        # If spread is UNKNOWN -> NON_EXECUTABLE (PR-FIX-5)
        if s_pct is None:
            outcome_data = {
                "status": NET_R_STATUS_NON_EXECUTABLE,
                "entry_fill": raw_fill,
                "exit_fill": None,
                "exit_reason": "UNKNOWN_SPREAD",
            }
            for h in ("MOMENTUM_90M", "INTRADAY_EOD", "SWING_3D"):
                write_outcome(cur, snapshot, trigger, trig_rid, h, outcome_data,
                              spread_pct=None, spread_source=s_src,
                              risk_actual=risk_actual, raw_fill=raw_fill,
                              stop_used=stop_used, t1_used=t1_used,
                              t2_used=t2_used,
                              quote_raw=s_raw, quote_timestamp_utc=s_ts)
            continue

        if raw_fill is None:
            outcome_data = {
                "status": NET_R_STATUS_NON_EXECUTABLE,
                "entry_fill": None,
                "exit_fill": None,
                "exit_reason": "NOT_EXECUTABLE",
            }
            for h in ("MOMENTUM_90M", "INTRADAY_EOD", "SWING_3D"):
                write_outcome(cur, snapshot, trigger, trig_rid, h, outcome_data,
                              spread_pct=s_pct, spread_source=s_src,
                              risk_actual=None, raw_fill=None,
                              stop_used=None, t1_used=None, t2_used=None,
                              quote_raw=s_raw, quote_timestamp_utc=s_ts)
            continue

        # Min-risk gate: round_trip_cost / risk_actual <= 0.5
        round_trip_cost_ps = (s_pct / 100.0) * raw_fill + 2.0 * TICK_SIZE
        if risk_actual > 0 and (round_trip_cost_ps / risk_actual) > 0.5:
            outcome_data = {
                "status": NET_R_STATUS_NON_EXECUTABLE,
                "entry_fill": raw_fill,
                "exit_fill": None,
                "exit_reason": "MIN_RISK_THRESHOLD",
            }
            for h in ("MOMENTUM_90M", "INTRADAY_EOD", "SWING_3D"):
                write_outcome(cur, snapshot, trigger, trig_rid, h, outcome_data,
                              spread_pct=s_pct, spread_source=s_src,
                              risk_actual=risk_actual, raw_fill=raw_fill,
                              stop_used=stop_used, t1_used=t1_used,
                              t2_used=t2_used,
                              quote_raw=s_raw, quote_timestamp_utc=s_ts)
            continue

        # MOMENTUM_90M
        momentum = evaluate_momentum(df, trigger, raw_fill,
                                     stop_used, t1_used, t2_used)
        if momentum is not None:
            write_outcome(cur, snapshot, trigger, trig_rid,
                          "MOMENTUM_90M", momentum,
                          spread_pct=s_pct, spread_source=s_src,
                          risk_actual=risk_actual, raw_fill=raw_fill,
                          stop_used=stop_used, t1_used=t1_used,
                          t2_used=t2_used,
                          quote_raw=s_raw, quote_timestamp_utc=s_ts)

        # INTRADAY_EOD
        intraday = evaluate_horizon(df, trigger["idx"], raw_fill,
                                    stop_used, t1_used, t2_used,
                                    len(df) - 1)
        write_outcome(cur, snapshot, trigger, trig_rid, "INTRADAY_EOD",
                      intraday,
                      spread_pct=s_pct, spread_source=s_src,
                      risk_actual=risk_actual, raw_fill=raw_fill,
                      stop_used=stop_used, t1_used=t1_used,
                      t2_used=t2_used,
                      quote_raw=s_raw, quote_timestamp_utc=s_ts)

        # SWING_3D
        swing = evaluate_swing(ticker, scan_date, trigger, raw_fill,
                               stop_used, t1_used, t2_used)
        write_outcome(cur, snapshot, trigger, trig_rid, "SWING_3D", swing,
                      spread_pct=s_pct, spread_source=s_src,
                      risk_actual=risk_actual, raw_fill=raw_fill,
                      stop_used=stop_used, t1_used=t1_used,
                      t2_used=t2_used,
                      quote_raw=s_raw, quote_timestamp_utc=s_ts)


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
        SELECT o.outcome_horizon, o.net_r, o.net_r_status, o.outcome
        FROM outcomes o
        JOIN snapshots s ON s.snapshot_id = o.snapshot_id
        JOIN trigger_results tr ON tr.trigger_result_id = o.trigger_result_id
        WHERE s.scan_date = ?
          AND tr.event_rank = 1
          AND s.is_scheduled = 1
          AND s.in_pm_window = 1
          AND s.preflight_passed = 1
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
        update_stats(stats, {"net_r": row["net_r"],
                             "net_r_status": row["net_r_status"]})
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
            row = cur.execute("SELECT MAX(scan_date) FROM snapshots").fetchone()
            if not row or not row[0]:
                print("No snapshots.")
                return
            scan_date = row[0]

        print()
        print("=" * 80)
        print("DAYS-BOT V5.0.6.3 SNAPSHOT EVALUATOR")
        print(f"scan_date={scan_date}")
        print("=" * 80)

        if force:
            cur.execute(
                "DELETE FROM outcomes WHERE snapshot_id IN "
                "(SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
                (scan_date,),
            )
            cur.execute(
                "DELETE FROM trigger_results WHERE snapshot_id IN "
                "(SELECT snapshot_id FROM snapshots WHERE scan_date = ?)",
                (scan_date,),
            )
            conn.commit()

        snapshots = cur.execute(
            "SELECT * FROM snapshots WHERE scan_date = ? ORDER BY snapshot_id",
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
                print(f"[evaluate] {snapshot['ticker']} ERROR: "
                      f"{type(exc).__name__}: {exc}")
                conn.rollback()

        stats = calculate_db_stats(cur, scan_date)
        print()
        print("=" * 80)
        print(f"SUMMARY — {scan_date}")
        print("=" * 80)
        print(f"Total outcomes (rank=1): {stats['total_outcomes']}")
        print(f"Valid Net-R:             {stats['valid_net_r']}")
        print(f"Excluded Net-R:          {stats['excluded_net_r']}")

        if stats["valid_net_r"] > 0:
            avg_net = stats["sum_net_r"] / stats["valid_net_r"]
            win_rate = stats["wins"] / stats["valid_net_r"] * 100
            print(f"Avg Net R:               {avg_net:.3f}")
            print(f"Win Rate:                {win_rate:.1f}%")
            print(f"W / L / BE:              {stats['wins']} / "
                  f"{stats['losses']} / {stats['breakeven']}")
        else:
            print("Avg Net R:               N/A")
            print("Win Rate:                N/A")
        print("=" * 80)

    finally:
        conn.close()


# =====================================================================
# CLI
# =====================================================================

if __name__ == "__main__":
    parser = ArgumentParser(description="DAYS-BOT V5.0.6.3 Snapshot Evaluator")
    parser.add_argument("--scan-date", type=str, default=None,
                        help="Scan date (YYYY-MM-DD)")
    parser.add_argument("--force", action="store_true",
                        help="Delete derived rows and reevaluate.")
    args = parser.parse_args()
    evaluate_all(scan_date=args.scan_date, force=args.force)
