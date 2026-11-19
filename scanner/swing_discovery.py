"""
DAYS-BOT V5.0.10 — Swing Discovery
CHANGES:
1. Drops partial daily bar (if fetched before market close)
2. Adds data_date (actual bar date) to candidate
3. Adds data_is_final flag
4. Excludes weekends
"""
import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime, timedelta, time as dtime
from typing import List, Dict, Tuple
import math

ET = pytz.timezone("America/New_York")
ATR_PERIOD = 14
MARKET_CLOSE = dtime(16, 0)


def _safe_float(val, default=0.0):
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default


def _compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    if df is None or len(df) < period + 1:
        return 0.0
    high = df['High']; low = df['Low']; close = df['Close']
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = float(tr.iloc[-period:].mean())
    return atr if atr > 0 else 0.0


def _is_partial_bar(last_bar_date, now_et: datetime) -> bool:
    """Returns True if last bar is today AND market is still open (partial)."""
    if last_bar_date != now_et.date():
        return False  # Not today → it's a closed bar
    # It's today. Is the market closed?
    if now_et.time() < MARKET_CLOSE:
        return True  # Still open → partial bar
    return False


def run_swing_discovery(universe_tickers: List[str]) -> Tuple[List[dict], dict]:
    now_et = datetime.now(ET)
    print(f"[SwingDiscovery] Starting daily scan on {len(universe_tickers)} symbols...")
    print(f"[SwingDiscovery] Current ET time: {now_et.strftime('%Y-%m-%d %H:%M:%S')}")

    # 🚨 NEW: Block weekends
    if now_et.weekday() >= 5:
        print("[SwingDiscovery] Weekend detected. Aborting scan.")
        return [], {"error": "weekend", "universe": len(universe_tickers)}

    print("[SwingDiscovery] Fetching daily bars via yfinance...")
    data = yf.download(
        tickers=" ".join(universe_tickers),
        period="2mo",
        interval="1d",
        group_by='ticker',
        progress=False,
        threads=True,
        auto_adjust=False,
    )

    candidates = []
    diagnostics = {
        "universe": len(universe_tickers),
        "passed_filters": 0,
        "reject_price": 0,
        "reject_volume": 0,
        "reject_trend": 0,
        "reject_gap": 0,
        "reject_atr": 0,
        "reject_partial_bar": 0,  # NEW
    }

    for ticker in universe_tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.levels[0]:
                    continue
                df = data[ticker]
            else:
                df = data

            df = df.dropna()
            if len(df) < 20:
                continue

            # 🚨 NEW: Drop partial last bar
            last_bar_date = df.index[-1].date() if hasattr(df.index[-1], 'date') else df.index[-1]
            if _is_partial_bar(last_bar_date, now_et):
                df = df.iloc[:-1]
                diagnostics["reject_partial_bar"] += 1
                if len(df) < 20:
                    continue
                print(f"[SwingDiscovery] {ticker}: dropped partial bar from {last_bar_date}")

            # Now `latest` is guaranteed to be a CLOSED bar
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            data_date = df.index[-1].strftime("%Y-%m-%d")

            price = _safe_float(latest['Close'])
            latest_open = _safe_float(latest['Open'])
            prev_close = _safe_float(prev['Close'])
            volume = _safe_float(latest['Volume'])
            avg_volume_5d = _safe_float(df['Volume'].tail(5).mean())

            if price < 1.0 or price > 100.0:
                diagnostics["reject_price"] += 1
                continue

            if avg_volume_5d < 500_000:
                diagnostics["reject_volume"] += 1
                continue

            sma20 = _safe_float(df['Close'].tail(20).mean())
            if price < sma20:
                diagnostics["reject_trend"] += 1
                continue

            gap_pct = ((latest_open - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            if gap_pct > 10.0:
                diagnostics["reject_gap"] += 1
                continue

            atr = _compute_atr(df)
            if atr <= 0:
                diagnostics["reject_atr"] += 1
                continue

            diagnostics["passed_filters"] += 1
            candidates.append({
                "ticker": ticker,
                "price": price,
                "prev_close": prev_close,
                "gap_pct": gap_pct,
                "volume": int(volume),
                "avg_volume": int(avg_volume_5d),
                "sma20": sma20,
                "atr": atr,
                "float": None,
                "spread_pct": 0.5,
                "data_status": "ACTIONABLE",
                "trade_type": "SWING_1_3D",
                "data_date": data_date,           # 🚨 NEW
                "data_is_final": True,            # 🚨 NEW (always True after drop)
                "market_session": "CLOSE",         # 🚨 NEW
            })

        except Exception:
            continue

    print(f"[SwingDiscovery] Found {len(candidates)} candidates.")
    print(f"[SwingDiscovery] Diagnostics: {diagnostics}")
    return candidates, diagnostics
