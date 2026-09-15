#!/usr/bin/env python3
"""
DAYS-BOT V5.0.6 – Snapshot Evaluator

Evaluates snapshots (S0) against post-trigger market data.
Produces:
    trigger_results  — one row per (snapshot, method)
    outcomes         — up to 3 rows per trigger_result (MOM_90M, INTRADAY_EOD, SWING_3D)

Trigger Methods (independent, all evaluated):
    A — PMH_BREAKOUT_V1     : intrabar high >= PMH + buffer
    B — BREAKOUT_VOLUME_V1  : close-based + volume confirmation
    C — VWAP_RECLAIM_V1     : close crosses VWAP + volume confirmation
    D — PULLBACK_RETEST_V1  : Breakout → Pullback → Hold → Reclaim (separate bars)

Entry: next bar open (Long: × (1 + slippage))
Exit V1 (INTRADAY_EOD): T1=2R (50%), Stop→BE, T2=4R (50%), EOD close, Stop-first
MOM_90M / SWING_3D: horizon-only (exit at horizon close)

NULL semantics:
    hit = 1   → HIT
    hit = 0   → MISS (checked, not found)
    hit = NULL→ UNKNOWN (data insufficient)

Usage:
    python evaluate_snapshots.py                       # latest scan_date
    python evaluate_snapshots.py --scan-date 2026-09-15
    python evaluate_snapshots.py --force               # delete + recompute
    python evaluate_snapshots.py --dry-run             # no DB writes
    python evaluate_snapshots.py --ticker HQ           # single ticker
"""
import sys
import json
import math
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from argparse import ArgumentParser

import pytz
import pandas as pd
import yfinance as yf

# ============================================================
# CONFIG
# ============================================================
ET = pytz.timezone("America/New_York")
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "alerts.db"

# Trigger methods
TRIGGER_A = "PMH_BREAKOUT_V1"
TRIGGER_B = "BREAKOUT_VOLUME_V1"
TRIGGER_C = "VWAP_RECLAIM_V1"
TRIGGER_D = "PULLBACK_RETEST_V1"

TRIGGER_VERSION = "1.0"

# Horizons
HORIZON_MOM = "MOMENTUM_90M"
HORIZON_INTRA = "INTRADAY_EOD"
HORIZON_SWING = "SWING_3D"

# Versions
EXIT_RULES_VERSION = "EXIT_V1"
COST_MODEL_VERSION = "COST_V1_FIXED_15BPS"
HORIZON_RULES_VERSION = "HORIZON_ONLY"

# Cost model
SLIPPAGE_PCT = 0.0015   # 15 bps
BLINK_FEE_PER_SHARE = 0.01
BLINK_MIN_FEE = 1.50
BLINK_MAX_FEE_PCT = 0.018

# Constants
TICK_SIZE = 0.01
MIN_VALID_VOLUMES = 3
VOLUME_CONFIRM_MULT = 1.20
MOMENTUM_HORIZON_MIN = 90
D_TIMEOUT_MIN = 60
T1_R = 2.0
T2_R = 4.0

# Session windows
PM_START = "04:00"
PM_END = "09:29"
RTH_START = "09:30"
RTH_END = "15:59"


# ============================================================
# HELPERS
# ============================================================
def _safe_float(v, default=None):
    try:
        if v is None:
            return default
        f = float(v)
        if not math.isfinite(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _safe_int(v, default=None):
    try:
        if v is None:
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _is_rth_complete(scan_date_str: str) -> bool:
    """
    Return True if RTH (09:30-16:00 ET) for scan_date has closed.
    Used only as a warning gate — manual override via --scan-date still allowed.
    """
    try:
        now_et = datetime.now(ET)
        scan_d = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
        today = now_et.date()

        if scan_d < today:
            return True
        if scan_d > today:
            return False
        # Same day: RTH closes at 16:00 ET
        return now_et.hour >= 16
    except Exception:
        return False


# ============================================================
# SAFE SCHEMA MIGRATION — relax hit NOT NULL
# ============================================================
def _relax_hit_nullable():
    """trigger_results.hit must be nullable to represent UNKNOWN."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(trigger_results)")
    cols = cur.fetchall()
    hit_col = [c for c in cols if c[1] == "hit"]
    if not hit_col:
        conn.close()
        return
    if hit_col[0][3] == 0:
        conn.close()
        return  # already nullable

    n = cur.execute("SELECT COUNT(*) FROM trigger_results").fetchone()[0]
    if n > 0:
        print(f"[migrate] WARNING: trigger_results has {n} rows — cannot relax safely")
        conn.close()
        return

    cur.execute("DROP TABLE trigger_results")
    cur.execute("""
        CREATE TABLE trigger_results (
            trigger_result_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id           INTEGER NOT NULL,
            trigger_method        TEXT    NOT NULL,
            trigger_version       TEXT    NOT NULL,
            hit                   INTEGER,
            trigger_time_utc      TEXT,
            trigger_time_et       TEXT,
            trigger_price         REAL,
            elapsed_sec_from_t0   INTEGER,
            window                TEXT,
            trigger_data_mode     TEXT,
            metadata_json         TEXT,
            created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id),
            UNIQUE(snapshot_id, trigger_method, trigger_version)
        )
    """)
    conn.commit()
    conn.close()
    print("[migrate] trigger_results.hit relaxed to nullable (V5.0.6)")


# ============================================================
# DATA RESOLUTION
# ============================================================
def parse_pm_bars(pm_bars_json):
    """Convert pm_bars_json text to DataFrame (or None)."""
    if not pm_bars_json:
        return None
    try:
        bars = json.loads(pm_bars_json)
        if not isinstance(bars, list) or len(bars) == 0:
            return None

        rows = []
        for b in bars:
            if not all(k in b for k in ("t", "o", "h", "l", "c", "v")):
                return None
            rows.append({
                "time": pd.Timestamp(b["t"]),
                "open": float(b["o"]),
                "high": float(b["h"]),
                "low": float(b["l"]),
                "close": float(b["c"]),
                "volume": int(b["v"]),
            })

        df = pd.DataFrame(rows)
        df = df.set_index("time").sort_index()

        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert(ET)

        return df
    except Exception as e:
        print(f"[evaluate] pm_bars_json parse error: {type(e).__name__}: {e}")
        return None


def is_pm_aware(pm_bars_df):
    """PM_AWARE if >=5 chronological, valid OHLC bars."""
    if pm_bars_df is None or len(pm_bars_df) < 5:
        return False
    if not pm_bars_df.index.is_monotonic_increasing:
        return False
    for col in ("open", "high", "low", "close"):
        if pm_bars_df[col].isna().any():
            return False
    return True


def fetch_rth_bars(ticker, scan_date):
    """Fetch 1-min RTH bars for scan_date."""
    try:
        end_date = (datetime.strptime(scan_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        df = yf.download(
            ticker,
            start=scan_date,
            end=end_date,
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

        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df = df.tz_convert(ET)
        df = df.between_time(RTH_START, RTH_END)
        return df
    except Exception as e:
        print(f"[evaluate] {ticker} RTH fetch error: {type(e).__name__}: {e}")
        return pd.DataFrame()


def fetch_daily_bars(ticker, scan_date, n_days=6):
    """Fetch daily bars for SWING_3D evaluation."""
    try:
        start = datetime.strptime(scan_date, "%Y-%m-%d")
        end = start + timedelta(days=n_days + 5)
        df = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception as e:
        print(f"[evaluate] {ticker} daily fetch error: {type(e).__name__}: {e}")
        return pd.DataFrame()


# ============================================================
# VOLUME RESOLVER
# ============================================================
def resolve_volume_median(prev_bars):
    """Median of valid volumes (>0). None if <MIN_VALID_VOLUMES valid."""
    if prev_bars is None or len(prev_bars) < 5:
        return None
    vols = [float(v) for v in prev_bars["volume"] if _safe_float(v, 0) > 0]
    if len(vols) < MIN_VALID_VOLUMES:
        return None
    vols_sorted = sorted(vols)
    return vols_sorted[len(vols_sorted) // 2]


# ============================================================
# TRIGGER ENGINES
# ============================================================
def detect_A(bars_df, pm_high, atr):
    """Intrabar: high >= PMH + buffer."""
    if pm_high is None or atr is None:
        return (None, None, None, "NO_PMH_ATR")
    buffer = max(2 * TICK_SIZE, 0.05 * atr)
    level = pm_high + buffer
    for i in range(len(bars_df)):
        if float(bars_df.iloc[i]["high"]) >= level:
            return (1, i, level, None)
    return (0, None, None, None)


def detect_B(bars_df, pm_high, atr):
    """Close-based + volume confirmation."""
    if pm_high is None or atr is None:
        return (None, None, None, "NO_PMH_ATR")
    buffer = max(2 * TICK_SIZE, 0.05 * atr)
    level = pm_high + buffer

    checkable = 0
    for i in range(5, len(bars_df)):
        prev_5 = bars_df.iloc[i - 5:i]
        vol_med = resolve_volume_median(prev_5)
        if vol_med is None:
            continue
        checkable += 1
        bar = bars_df.iloc[i]
        if float(bar["close"]) >= level and float(bar["volume"]) >= VOLUME_CONFIRM_MULT * vol_med:
            return (1, i, float(bar["close"]), None)

    if checkable == 0:
        return (None, None, None, "VOLUME_UNAVAILABLE")
    return (0, None, None, None)


def detect_C(bars_df, pm_vwap, pm_low, pm_volume):
    """VWAP Reclaim: prev.close < VWAP <= curr.close + volume."""
    if pm_vwap is None or pm_vwap <= 0:
        return (None, None, None, "VWAP_UNAVAILABLE")
    if pm_low is not None and pm_vwap <= pm_low:
        return (None, None, None, "VWAP_UNAVAILABLE")
    if pm_volume is not None and pm_volume == 0:
        return (None, None, None, "VWAP_UNAVAILABLE")

    checkable = 0
    for i in range(5, len(bars_df)):
        prev_5 = bars_df.iloc[i - 5:i]
        vol_med = resolve_volume_median(prev_5)
        if vol_med is None:
            continue
        checkable += 1
        prev_bar = bars_df.iloc[i - 1]
        curr_bar = bars_df.iloc[i]
        if (float(prev_bar["close"]) < pm_vwap
                and float(curr_bar["close"]) >= pm_vwap
                and float(curr_bar["volume"]) >= VOLUME_CONFIRM_MULT * vol_med):
            return (1, i, float(curr_bar["close"]), None)

    if checkable == 0:
        return (None, None, None, "VOLUME_UNAVAILABLE")
    return (0, None, None, None)


def detect_D(bars_df, pm_high, atr):
    """Breakout → Pullback → Hold → Reclaim (separate bars)."""
    if pm_high is None or atr is None:
        return (None, None, None, "NO_PMH_ATR")

    buffer = max(2 * TICK_SIZE, 0.05 * atr)
    breakout_level = pm_high + buffer
    pullback_lo = pm_high + 0.10 * atr
    hold_floor = pm_high - 0.10 * atr

    state = "IDLE"
    breakout_idx = None
    pullback_time = None

    for i in range(len(bars_df)):
        bar = bars_df.iloc[i]

        if state == "IDLE":
            if float(bar["high"]) >= breakout_level:
                state = "BREAKOUT_SEEN"
                breakout_idx = i
            continue

        if state == "BREAKOUT_SEEN":
            if i <= breakout_idx:
                continue
            if float(bar["low"]) <= pullback_lo:
                state = "PULLBACK_SEEN"
                pullback_time = bars_df.index[i]
            continue

        if state == "PULLBACK_SEEN":
            elapsed_min = (bars_df.index[i] - pullback_time).total_seconds() / 60.0
            if elapsed_min > D_TIMEOUT_MIN:
                return (0, None, None, "TIMEOUT")
            if float(bar["close"]) < hold_floor:
                return (0, None, None, "PULLBACK_FAILED")
            if float(bar["close"]) > breakout_level:
                return (1, i, float(bar["close"]), None)

    return (0, None, None, None)


# ============================================================
# ENTRY EXECUTION
# ============================================================
def execute_entry(bars_df, trigger_idx):
    """Entry = next bar open × (1 + slippage)."""
    next_idx = trigger_idx + 1
    if next_idx >= len(bars_df):
        return (None, None, None)
    bar = bars_df.iloc[next_idx]
    raw_open = float(bar["open"])
    if raw_open <= 0:
        return (None, None, None)
    entry_fill = raw_open * (1 + SLIPPAGE_PCT)
    return (entry_fill, bars_df.index[next_idx], next_idx)


# ============================================================
# MFE / MAE
# ============================================================
def compute_mfe_mae(bars_slice, entry_fill):
    """MFE/MAE over provided bars slice."""
    if bars_slice is None or len(bars_slice) == 0:
        return (entry_fill, entry_fill, 0, 0)
    mfe = float(bars_slice["high"].max())
    mae = float(bars_slice["low"].min())
    mfe_time_idx = bars_slice["high"].idxmax()
    mae_time_idx = bars_slice["low"].idxmin()
    return (mfe, mae, mfe_time_idx, mae_time_idx)


# ============================================================
# EXIT V1
# ============================================================
def run_exit_v1(bars_df, entry_idx, entry_fill, stop, t1, t2):
    """Full Exit V1 state machine. Same-bar: Stop-first."""
    t1_hit = False
    stop_level = stop
    exit_reason = "EOD_CLOSE"
    exit_price_raw = None
    exit_idx = len(bars_df) - 1

    for i in range(entry_idx, len(bars_df)):
        bar = bars_df.iloc[i]
        high = float(bar["high"])
        low = float(bar["low"])

        # Stop-first
        if low <= stop_level:
            exit_reason = "STOP_HIT" if not t1_hit else "BE_HIT"
            exit_price_raw = stop_level
            exit_idx = i
            break

        # T2
        if not t1_hit and high >= t2:
            exit_reason = "T2_HIT"
            exit_price_raw = t2
            exit_idx = i
            break

        # T1 → BE
        if not t1_hit and high >= t1:
            t1_hit = True
            stop_level = entry_fill

    if exit_price_raw is None:
        exit_price_raw = float(bars_df.iloc[-1]["close"])
        exit_idx = len(bars_df) - 1

    exit_fill = exit_price_raw * (1 - SLIPPAGE_PCT)
    exit_time = bars_df.index[exit_idx]
    hold_min = int((exit_time - bars_df.index[entry_idx]).total_seconds() / 60)

    return {
        "exit_reason": exit_reason,
        "exit_price_raw": exit_price_raw,
        "exit_fill": exit_fill,
        "exit_time": exit_time,
        "exit_idx": exit_idx,
        "hold_min": hold_min,
        "t1_hit": t1_hit,
    }


# ============================================================
# HORIZON EXITS
# ============================================================
def run_horizon_exit(bars_df, entry_idx, horizon_min):
    """Exit at close of bar <= entry_time + horizon_min."""
    if entry_idx >= len(bars_df):
        return None
    entry_time = bars_df.index[entry_idx]
    target_time = entry_time + timedelta(minutes=horizon_min)

    mask = bars_df.index <= target_time
    window = bars_df[mask]
    if len(window) == 0:
        return None

    exit_bar = window.iloc[-1]
    exit_time = window.index[-1]
    exit_fill = float(exit_bar["close"]) * (1 - SLIPPAGE_PCT)

    return {
        "exit_fill": exit_fill,
        "exit_price_raw": float(exit_bar["close"]),
        "exit_time": exit_time,
        "exit_reason": "HORIZON_END",
        "hold_min": int((exit_time - entry_time).total_seconds() / 60),
        "window_bars": window,
    }


# ============================================================
# COST MODEL V1
# ============================================================
def blink_fee(value_abs):
    max_fee = abs(value_abs) * BLINK_MAX_FEE_PCT
    return max(BLINK_MIN_FEE, max_fee)


def compute_costs(entry_fill, exit_fill, position_size, spread_pct):
    """All costs computed separately. Fills are RAW."""
    entry_value = entry_fill * position_size
    exit_value = exit_fill * position_size

    cost_slippage = SLIPPAGE_PCT * (entry_value + exit_value)

    half_spread = (spread_pct or 0) / 100.0 / 2.0
    cost_spread = half_spread * (entry_value + exit_value)

    cost_commission = blink_fee(entry_value) + blink_fee(exit_value)

    cost_tax = 0.0

    return {
        "cost_spread": cost_spread,
        "cost_slippage": cost_slippage,
        "cost_commission": cost_commission,
        "cost_tax": cost_tax,
        "cost_total": cost_spread + cost_slippage + cost_commission + cost_tax,
    }


# ============================================================
# DB WRITES
# ============================================================
def write_trigger_result(cur, snapshot_id, method, hit, trigger_time,
                          trigger_price, window, data_mode, reason, elapsed_sec):
    meta = json.dumps({"reason": reason}) if reason else None

    tt_utc = None
    tt_et = None
    if trigger_time is not None:
        tt_utc = trigger_time.astimezone(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
        tt_et = trigger_time.strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        INSERT INTO trigger_results
        (snapshot_id, trigger_method, trigger_version, hit,
         trigger_time_utc, trigger_time_et, trigger_price,
         elapsed_sec_from_t0, window, trigger_data_mode, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        snapshot_id, method, TRIGGER_VERSION, hit,
        tt_utc, tt_et, trigger_price,
        elapsed_sec, window, data_mode, meta,
    ))
    return cur.lastrowid


def write_outcome(cur, snapshot_id, trigger_result_id, method, horizon,
                   t0_price, mfe, mae, mfe_pct, mae_pct,
                   exit_reason, exit_price, exit_time_utc, hold_min,
                   gross_r, gross_pct, net_r, net_pct, outcome_label,
                   costs, entry_slippage_pct, entry_efficiency,
                   abs_before_trigger, rel_before_trigger):
    cur.execute("""
        INSERT INTO outcomes
        (snapshot_id, trigger_result_id, trigger_method, trigger_version,
         outcome_horizon, t0_price, mfe, mae, mfe_pct, mae_pct,
         absolute_move_before_trigger_pct, relative_move_before_trigger_pct,
         entry_slippage_pct, entry_efficiency,
         exit_reason, exit_price, exit_time_utc, hold_minutes,
         gross_r, gross_pct,
         cost_spread, cost_slippage, cost_commission, cost_tax, cost_total,
         net_r, net_pct, outcome,
         exit_rules_version, cost_model_version)
        VALUES (?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?)
    """, (
        snapshot_id, trigger_result_id, method, TRIGGER_VERSION,
        horizon, t0_price, mfe, mae, mfe_pct, mae_pct,
        abs_before_trigger, rel_before_trigger,
        entry_slippage_pct, entry_efficiency,
        exit_reason, exit_price, exit_time_utc, hold_min,
        round(gross_r, 4), round(gross_pct, 4),
        round(costs["cost_spread"], 4),
        round(costs["cost_slippage"], 4),
        round(costs["cost_commission"], 4),
        round(costs["cost_tax"], 4),
        round(costs["cost_total"], 4),
        round(net_r, 4), round(net_pct, 4), outcome_label,
        EXIT_RULES_VERSION if horizon == HORIZON_INTRA else HORIZON_RULES_VERSION,
        COST_MODEL_VERSION,
    ))


# ============================================================
# GROSS/NET COMPUTATION
# ============================================================
def _compute_gross_net(entry_fill, exit_fill, risk_per_share,
                       position_size, spread_pct):
    gross_per_share = exit_fill - entry_fill
    gross_r = gross_per_share / risk_per_share if risk_per_share > 0 else 0
    gross_pct = (gross_per_share / entry_fill) * 100 if entry_fill > 0 else 0

    costs = compute_costs(entry_fill, exit_fill, position_size, spread_pct)

    net_pnl = (gross_per_share * position_size) - costs["cost_total"]
    net_per_share = net_pnl / position_size if position_size > 0 else 0
    net_r = net_per_share / risk_per_share if risk_per_share > 0 else 0
    entry_value = entry_fill * position_size
    net_pct = (net_pnl / entry_value * 100) if entry_value > 0 else 0

    if net_r > 0.05:
        label = "WIN"
    elif net_r < -0.05:
        label = "LOSS"
    else:
        label = "BREAKEVEN"

    return {
        "gross_r": gross_r, "gross_pct": gross_pct,
        "net_r": net_r, "net_pct": net_pct,
        "costs": costs, "label": label,
    }


# ============================================================
# HORIZON WRITERS
# ============================================================
def _write_horizon(cur, dry_run, snap_id, trig_id, method, horizon,
                   bars_df, entry_idx, entry_fill, r, t0_price, s0_price,
                   position_size, spread_pct,
                   exit_fill, exit_time, exit_reason, hold_min,
                   abs_before, rel_before, stats):
    if exit_time is not None:
        mask = (bars_df.index >= bars_df.index[entry_idx]) & (bars_df.index <= exit_time)
        window = bars_df[mask]
    else:
        window = bars_df.iloc[entry_idx:]
    mfe, mae, _, _ = compute_mfe_mae(window, entry_fill)
    mfe_pct = (mfe - entry_fill) / entry_fill * 100 if entry_fill > 0 else 0
    mae_pct = (mae - entry_fill) / entry_fill * 100 if entry_fill > 0 else 0

    entry_slippage_pct = (entry_fill - t0_price) / t0_price * 100 if t0_price else 0
    if mfe > t0_price and mfe > entry_fill:
        entry_eff = (mfe - entry_fill) / (mfe - t0_price)
    else:
        entry_eff = None

    result = _compute_gross_net(entry_fill, exit_fill, r, position_size, spread_pct)

    if not dry_run and trig_id:
        write_outcome(
            cur, snap_id, trig_id, method, horizon,
            t0_price, mfe, mae, mfe_pct, mae_pct,
            exit_reason, exit_fill,
            exit_time.strftime("%Y-%m-%d %H:%M:%S") if exit_time is not None else None,
            hold_min,
            result["gross_r"], result["gross_pct"],
            result["net_r"], result["net_pct"], result["label"],
            result["costs"], entry_slippage_pct, entry_eff,
            abs_before, rel_before,
        )

    stats["sum_net_r"] += result["net_r"]
    if result["label"] == "WIN":
        stats["wins"] += 1
    elif result["label"] == "LOSS":
        stats["losses"] += 1
    else:
        stats["be"] += 1


def _write_swing_horizon(cur, dry_run, snap_id, trig_id, method,
                         ticker, scan_date, entry_time, entry_fill,
                         r, t0_price, s0_price, position_size, spread_pct,
                         abs_before, rel_before, stats):
    daily = fetch_daily_bars(ticker, scan_date, n_days=6)
    if daily.empty:
        return

    entry_date = entry_time.date() if entry_time else None
    if entry_date is None:
        return

    daily_idx = daily.index
    entry_pos = None
    for i, d in enumerate(daily_idx):
        if d.date() >= entry_date:
            entry_pos = i
            break
    if entry_pos is None:
        return

    exit_pos = entry_pos + 3
    if exit_pos >= len(daily):
        exit_pos = len(daily) - 1

    window = daily.iloc[entry_pos:exit_pos + 1]
    mfe = float(window["high"].max())
    mae = float(window["low"].min())
    mfe_pct = (mfe - entry_fill) / entry_fill * 100 if entry_fill > 0 else 0
    mae_pct = (mae - entry_fill) / entry_fill * 100 if entry_fill > 0 else 0

    exit_close = float(daily.iloc[exit_pos]["close"])
    exit_fill = exit_close * (1 - SLIPPAGE_PCT)
    exit_date = daily.index[exit_pos]

    days_held = exit_pos - entry_pos + 1
    hold_min = days_held * 390

    entry_slippage_pct = (entry_fill - t0_price) / t0_price * 100 if t0_price else 0
    if mfe > t0_price and mfe > entry_fill:
        entry_eff = (mfe - entry_fill) / (mfe - t0_price)
    else:
        entry_eff = None

    result = _compute_gross_net(entry_fill, exit_fill, r, position_size, spread_pct)

    if not dry_run and trig_id:
        write_outcome(
            cur, snap_id, trig_id, method, HORIZON_SWING,
            t0_price, mfe, mae, mfe_pct, mae_pct,
            "HORIZON_END", exit_fill,
            f"{exit_date.strftime('%Y-%m-%d')} 16:00:00",
            hold_min,
            result["gross_r"], result["gross_pct"],
            result["net_r"], result["net_pct"], result["label"],
            result["costs"], entry_slippage_pct, entry_eff,
            abs_before, rel_before,
        )

    stats["sum_net_r"] += result["net_r"]
    if result["label"] == "WIN":
        stats["wins"] += 1
    elif result["label"] == "LOSS":
        stats["losses"] += 1
    else:
        stats["be"] += 1


# ============================================================
# SINGLE SNAPSHOT
# ============================================================
def evaluate_snapshot(snapshot, cur, dry_run=False):
    ticker = snapshot["ticker"]
    snap_id = snapshot["snapshot_id"]
    scan_date = snapshot["scan_date"]

    pm_bars_df = parse_pm_bars(snapshot["pm_bars_json"])
    pm_aware = is_pm_aware(pm_bars_df)

    rth_df = fetch_rth_bars(ticker, scan_date)
    if rth_df.empty:
        print(f"  [{ticker}] RTH data unavailable — skipping")
        if not dry_run:
            for method in (TRIGGER_A, TRIGGER_B, TRIGGER_C, TRIGGER_D):
                write_trigger_result(cur, snap_id, method, None, None, None,
                                      None, "RTH_ONLY", "FETCH_FAILED", None)
        return {"ticker": ticker, "status": "no_data"}

    if pm_aware:
        combined = pd.concat([pm_bars_df, rth_df])
        combined = combined[~combined.index.duplicated(keep="first")]
        combined = combined.sort_index()
        data_mode = "PM_AWARE"
    else:
        combined = rth_df
        data_mode = "RTH_ONLY"

    pm_high = _safe_float(snapshot["pm_high"])
    pm_low = _safe_float(snapshot["pm_low"])
    pm_vwap = _safe_float(snapshot["pm_vwap"])
    pm_volume = _safe_int(snapshot["pm_volume"])
    atr = _safe_float(snapshot["atr"]) or 0.10
    position_size = _safe_int(snapshot["position_size"]) or 0
    spread_pct = _safe_float(snapshot["spread_pct"]) or 0.0
    stop_ref = _safe_float(snapshot["stop"])
    s0_price = _safe_float(snapshot["price"])

    if not pm_high or pm_high <= 0:
        print(f"  [{ticker}] No PMH — cannot trigger")
        if not dry_run:
            for method in (TRIGGER_A, TRIGGER_B, TRIGGER_C, TRIGGER_D):
                write_trigger_result(cur, snap_id, method, None, None, None,
                                      None, data_mode, "NO_PMH", None)
        return {"ticker": ticker, "status": "no_pmh"}

    results = {
        TRIGGER_A: detect_A(combined, pm_high, atr),
        TRIGGER_B: detect_B(combined, pm_high, atr),
        TRIGGER_C: detect_C(combined, pm_vwap, pm_low, pm_volume),
        TRIGGER_D: detect_D(combined, pm_high, atr),
    }

    stats = {"ticker": ticker, "triggered": 0, "missed": 0, "unknown": 0,
             "wins": 0, "losses": 0, "be": 0, "sum_net_r": 0.0}

    print(f"\n  ── {ticker} (snap_id={snap_id}, mode={data_mode}) ──")
    print(f"    PMH={pm_high} ATR={atr:.4f} VWAP={pm_vwap} PM_vol={pm_volume}")

    for method, (hit, idx, price, reason) in results.items():
        window = None
        trig_time = None
        elapsed_sec = None
        if hit == 1 and idx is not None:
            trig_time = combined.index[idx]
            elapsed_sec = int((trig_time - combined.index[0]).total_seconds())
            trig_hour = trig_time.hour + trig_time.minute / 60
            window = "PM" if trig_hour < 9.5 else "RTH"

        hit_label = "HIT" if hit == 1 else ("MISS" if hit == 0 else "UNKNOWN")
        print(f"    {method:22s} → {hit_label:8s} "
              f"{'@ ' + str(round(price, 2)) if price else ''} "
              f"{'[' + (reason or '') + ']' if reason else ''}")

        if hit == 1:
            stats["triggered"] += 1
        elif hit == 0:
            stats["missed"] += 1
        else:
            stats["unknown"] += 1

        trig_id = None
        if not dry_run:
            trig_id = write_trigger_result(cur, snap_id, method, hit,
                                            trig_time, price,
                                            window, data_mode, reason,
                                            elapsed_sec)

        if hit != 1:
            continue

        entry_fill, entry_time, entry_idx = execute_entry(combined, idx)
        if entry_fill is None:
            print(f"      └─ NOT_EXECUTABLE (no next bar)")
            if not dry_run and trig_id:
                for hz in (HORIZON_MOM, HORIZON_INTRA, HORIZON_SWING):
                    write_outcome(
                        cur, snap_id, trig_id, method, hz,
                        price, None, None, None, None,
                        "NOT_EXECUTABLE", None, None, None,
                        0, 0, 0, 0, "NOT_EXECUTABLE",
                        {"cost_spread": 0, "cost_slippage": 0,
                         "cost_commission": 0, "cost_tax": 0, "cost_total": 0},
                        None, None, None, None,
                    )
            continue

        if stop_ref is None or stop_ref >= entry_fill:
            stop_final = entry_fill * 0.985
        else:
            stop_final = stop_ref

        r = entry_fill - stop_final
        if r <= 0:
            print(f"      └─ Invalid risk (r={r})")
            continue
        t1 = entry_fill + T1_R * r
        t2 = entry_fill + T2_R * r

        print(f"      └─ entry={entry_fill:.4f} stop={stop_final:.4f} "
              f"T1={t1:.4f} T2={t2:.4f} R={r:.4f}")

        if price and s0_price:
            abs_before = (price - s0_price) / s0_price * 100
        else:
            abs_before = None
        rel_before = None

        # INTRADAY_EOD
        intra = run_exit_v1(combined, entry_idx, entry_fill, stop_final, t1, t2)
        _write_horizon(cur, dry_run, snap_id, trig_id, method, HORIZON_INTRA,
                       combined, entry_idx, entry_fill, r, price, s0_price,
                       position_size, spread_pct,
                       intra["exit_fill"], intra["exit_time"],
                       intra["exit_reason"], intra["hold_min"],
                       abs_before, rel_before, stats)

        # MOMENTUM_90M
        mom = run_horizon_exit(combined, entry_idx, MOMENTUM_HORIZON_MIN)
        if mom:
            _write_horizon(cur, dry_run, snap_id, trig_id, method, HORIZON_MOM,
                           combined, entry_idx, entry_fill, r, price, s0_price,
                           position_size, spread_pct,
                           mom["exit_fill"], mom["exit_time"],
                           mom["exit_reason"], mom["hold_min"],
                           abs_before, rel_before, stats)

        # SWING_3D
        _write_swing_horizon(cur, dry_run, snap_id, trig_id, method,
                             ticker, scan_date, entry_time, entry_fill,
                             r, price, s0_price, position_size, spread_pct,
                             abs_before, rel_before, stats)

    return stats


# ============================================================
# MAIN
# ============================================================
def evaluate_all(scan_date=None, force=False, dry_run=False, ticker=None):
    if not DB_PATH.exists():
        print(f"❌ DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    from database.snapshot_schema import init_snapshot_schema
    init_snapshot_schema()

    _relax_hit_nullable()

    # Determine scan_date
    if scan_date is None:
        rows = cur.execute(
            "SELECT DISTINCT scan_date FROM snapshots ORDER BY scan_date DESC"
        ).fetchall()
        if not rows:
            print("No snapshots in DB.")
            conn.close()
            return

        scan_date = None
        for r in rows:
            if _is_rth_complete(r[0]):
                scan_date = r[0]
                break

        if scan_date is None:
            scan_date = rows[0][0]
            print(f"  ⚠️ No scan_date with complete RTH found.")
            print(f"     Using latest: {scan_date} (data will be partial).")

    # Warning for explicitly-requested incomplete RTH
    if not _is_rth_complete(scan_date):
        now_et = datetime.now(ET)
        print(f"  ⚠️ WARNING: RTH for {scan_date} not complete yet.")
        print(f"     Now: {now_et.strftime('%Y-%m-%d %H:%M ET')} | RTH closes 16:00 ET.")
        print(f"     RTH bars will be missing or partial.")

    print(f"\n{'=' * 74}")
    print(f"SNAPSHOT EVALUATOR — scan_date={scan_date}")
    print(f"  mode: {'DRY-RUN' if dry_run else 'WRITE'}, force={force}, ticker={ticker}")
    print(f"{'=' * 74}")

    if force and not dry_run:
        cur.execute("""
            DELETE FROM outcomes WHERE snapshot_id IN
            (SELECT snapshot_id FROM snapshots WHERE scan_date = ?)
        """, (scan_date,))
        cur.execute("""
            DELETE FROM trigger_results WHERE snapshot_id IN
            (SELECT snapshot_id FROM snapshots WHERE scan_date = ?)
        """, (scan_date,))
        conn.commit()
        print(f"  [force] deleted existing trigger_results + outcomes for {scan_date}")

    sql = "SELECT * FROM snapshots WHERE scan_date = ?"
    params = [scan_date]
    if ticker:
        sql += " AND ticker = ?"
        params.append(ticker)
    if not force and not dry_run:
        sql += """ AND snapshot_id NOT IN
                   (SELECT DISTINCT snapshot_id FROM trigger_results)"""
    sql += " ORDER BY snapshot_id"

    snapshots = cur.execute(sql, params).fetchall()
    print(f"  Snapshots to evaluate: {len(snapshots)}\n")

    if not snapshots:
        print("  Nothing to do.")
        conn.close()
        return

    total_stats = {
        "triggered": 0, "missed": 0, "unknown": 0,
        "wins": 0, "losses": 0, "be": 0, "sum_net_r": 0.0,
        "snapshots": 0,
    }

    for snap in snapshots:
        total_stats["snapshots"] += 1
        try:
            stats = evaluate_snapshot(snap, cur, dry_run=dry_run)
            if stats:
                for k in ("triggered", "missed", "unknown",
                          "wins", "losses", "be"):
                    total_stats[k] += stats.get(k, 0)
                total_stats["sum_net_r"] += stats.get("sum_net_r", 0)
            if not dry_run:
                conn.commit()
        except Exception as e:
            print(f"  [{snap['ticker']}] ERROR: {type(e).__name__}: {e}")
            conn.rollback()
            continue

    print(f"\n{'=' * 74}")
    print(f"SUMMARY — {scan_date}")
    print(f"{'=' * 74}")
    print(f"  Snapshots processed:    {total_stats['snapshots']}")
    print(f"  Triggers HIT:           {total_stats['triggered']}")
    print(f"  Triggers MISS:          {total_stats['missed']}")
    print(f"  Triggers UNKNOWN:       {total_stats['unknown']}")
    print()
    n_outcomes = total_stats["wins"] + total_stats["losses"] + total_stats["be"]
    if n_outcomes > 0:
        wr = total_stats["wins"] / n_outcomes * 100
        avg_net_r = total_stats["sum_net_r"] / n_outcomes
        print(f"  Outcomes evaluated:     {n_outcomes}")
        print(f"  Win / Loss / BE:        {total_stats['wins']} / {total_stats['losses']} / {total_stats['be']}")
        print(f"  Win Rate:               {wr:.1f}%")
        print(f"  Avg Net R:              {avg_net_r:+.3f}")
    print(f"{'=' * 74}")

    conn.close()


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    parser = ArgumentParser(description="DAYS-BOT V5.0.6 Snapshot Evaluator")
    parser.add_argument("--scan-date", type=str, default=None,
                        help="Scan date (YYYY-MM-DD). Default: latest with complete RTH.")
    parser.add_argument("--force", action="store_true",
                        help="Delete + recompute all results for scan_date.")
    parser.add_argument("--dry-run", action="store_true",
                        help="No DB writes; print results only.")
    parser.add_argument("--ticker", type=str, default=None,
                        help="Evaluate a single ticker only.")
    args = parser.parse_args()

    evaluate_all(
        scan_date=args.scan_date,
        force=args.force,
        dry_run=args.dry_run,
        ticker=args.ticker,
    )
