"""
DAYS-BOT V5.0.7 — Swing Discovery (Daily Data + ATR)
סורק מניות על בסיס נתונים יומיים + מחשב ATR אמיתי לחישוב סיכון.
"""
import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import math

ET = pytz.timezone("America/New_York")
ATR_PERIOD = 14


def _safe_float(val, default=0.0):
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default


def _compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    """ATR אמיתי (True Range) על גבי בארים יומיים."""
    if df is None or len(df) < period + 1:
        return 0.0
    high = df['High']
    low = df['Low']
    close = df['Close']
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = float(tr.iloc[-period:].mean())
    return atr if atr > 0 else 0.0


def run_swing_discovery(universe_tickers: List[str]) -> Tuple[List[dict], dict]:
    print(f"[SwingDiscovery] Starting daily scan on {len(universe_tickers)} symbols...")
    print("[SwingDiscovery] Fetching daily bars via yfinance...")

    data = yf.download(
        tickers=" ".join(universe_tickers),
        period="2mo",       # 2 חודשים = מספיק ל-ATR(14) + SMA20
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

            latest = df.iloc[-1]
            prev = df.iloc[-2]

            price = _safe_float(latest['Close'])
            prev_close = _safe_float(prev['Close'])
            volume = _safe_float(latest['Volume'])
            avg_volume_5d = _safe_float(df['Volume'].tail(5).mean())

            # 1. פילטר מחיר
            if price < 1.0 or price > 100.0:
                diagnostics["reject_price"] += 1
                continue

            # 2. פילטר נפח
            if avg_volume_5d < 500_000:
                diagnostics["reject_volume"] += 1
                continue

            # 3. פילטר מגמה (SMA20)
            sma20 = _safe_float(df['Close'].tail(20).mean())
            if price < sma20:
                diagnostics["reject_trend"] += 1
                continue

            # 4. פילטר Gap
            gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            if gap_pct > 10.0:
                diagnostics["reject_gap"] += 1
                continue

            # 5. ATR אמיתי
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
            })

        except Exception:
            continue

    print(f"[SwingDiscovery] Found {len(candidates)} candidates passing daily filters.")
    print(f"[SwingDiscovery] Diagnostics: {diagnostics}")
    return candidates, diagnostics
