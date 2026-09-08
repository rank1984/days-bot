"""
DAYS-BOT V5.0.4 – Swing Engine (1-3 days)

Uses daily data, not PM data.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

ET = pytz.timezone("America/New_York")


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_series_to_scalar(series):
    """
    Convert pandas Series to scalar, or return 0.
    """
    try:
        if series is None:
            return 0.0
        if isinstance(series, pd.Series):
            if series.empty:
                return 0.0
            return float(series.iloc[-1])
        return float(series)
    except Exception:
        return 0.0


def calculate_swing_score(candidate: dict) -> dict:
    """
    Swing Score (0-100) based on:
    - Trend (20 EMA, 50 EMA)
    - Relative Strength vs SPY
    - Volume (RVOL, accumulation)
    - Structure
    - Catalyst quality & freshness
    - Risk (SEC, Earnings)
    """
    ticker = candidate['ticker']
    price = _safe_float(candidate.get('price', 0))
    gap_pct = _safe_float(candidate.get('gap_pct', 0))

    # Do NOT rely on PM data for swing.
    # Use daily data only.

    try:
        data = yf.download(ticker, period="60d", interval="1d", progress=False)
        if data.empty or len(data) < 20:
            return {"swing_score": 0, "swing_type": "INSUFFICIENT_DATA"}

        # SPY for RS
        spy = yf.download("SPY", period="60d", interval="1d", progress=False)
        if spy.empty:
            spy_ret = 0
        else:
            spy_ret = (spy['Close'].iloc[-1] / spy['Close'].iloc[-20] - 1) * 100 if len(spy) >= 20 else 0

        close = data['Close']
        volume = data['Volume']

        # 20 EMA & 50 EMA
        ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1] if len(close) >= 50 else ema20

        above_20 = price > ema20
        above_50 = price > ema50
        ema_cross = ema20 > ema50

        # EMA slope (20-day)
        ema20_series = close.ewm(span=20, adjust=False).mean()
        if len(ema20_series) >= 10:
            ema_slope = (ema20_series.iloc[-1] / ema20_series.iloc[-10] - 1) * 100
        else:
            ema_slope = 0

        pct_from_ema20 = ((price - ema20) / ema20) * 100 if ema20 > 0 else 0

        # Relative Strength vs SPY (20-day)
        stock_ret = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
        rs = stock_ret - spy_ret if spy_ret else stock_ret

        # Volume – RVOL (last 5 days avg vs 50 day avg)
        avg_vol_50 = volume.iloc[-50:].mean() if len(volume) >= 50 else volume.mean()
        avg_vol_5 = volume.iloc[-5:].mean()
        rvol = avg_vol_5 / avg_vol_50 if avg_vol_50 > 0 else 1.0

        # Structure: Higher highs/lows (last 10 days)
        recent_highs = close.iloc[-10:].max()
        recent_lows = close.iloc[-10:].min()
        if price > recent_highs * 0.98:
            structure = "BREAKOUT"
        elif price < recent_highs * 0.95:
            structure = "CONSOLIDATION"
        else:
            structure = "NEUTRAL"

        # ============================================================
        # Swing Score components
        # ============================================================

        trend_score = 0
        if above_20:
            trend_score += 10
        if above_50:
            trend_score += 10
        if ema_cross:
            trend_score += 10
        if ema_slope > 0.5:
            trend_score += 10
        if -5 < pct_from_ema20 < 5:
            trend_score += 10
        trend_score = min(trend_score, 40)

        rs_score = 0
        if rs > 5:
            rs_score = 25
        elif rs > 2:
            rs_score = 20
        elif rs > 0:
            rs_score = 15
        elif rs > -5:
            rs_score = 5
        else:
            rs_score = 0
        rs_score = min(rs_score, 25)

        volume_score = 0
        if rvol > 2.0:
            volume_score = 20
        elif rvol > 1.5:
            volume_score = 15
        elif rvol > 1.0:
            volume_score = 10
        else:
            volume_score = 5
        volume_score = min(volume_score, 20)

        structure_score = 0
        if structure == "BREAKOUT":
            structure_score = 20
        elif structure == "CONSOLIDATION":
            structure_score = 12
        else:
            structure_score = 8
        structure_score = min(structure_score, 20)

        catalyst_score = 0
        catalyst_type = candidate.get('catalyst_type', 'UNAVAILABLE')
        catalyst_quality = candidate.get('catalyst_score', 0)
        if catalyst_type != 'UNAVAILABLE' and catalyst_quality >= 8:
            catalyst_score = 15
        elif catalyst_type != 'UNAVAILABLE' and catalyst_quality >= 5:
            catalyst_score = 10
        else:
            catalyst_score = 5
        catalyst_score = min(catalyst_score, 15)

        risk_penalty = 0
        if candidate.get('sec_has_offering', False):
            risk_penalty -= 30

        # Float penalty
        float_val = candidate.get('float', 0)
        if float_val > 100_000_000:
            risk_penalty -= 10
        elif float_val > 50_000_000:
            risk_penalty -= 5

        total_score = trend_score + rs_score + volume_score + structure_score + catalyst_score + risk_penalty
        total_score = max(0, min(100, total_score))

        return {
            "swing_score": round(total_score, 1),
            "trend_score": trend_score,
            "rs_score": rs_score,
            "volume_score": volume_score,
            "structure_score": structure_score,
            "catalyst_score": catalyst_score,
            "risk_penalty": risk_penalty,
            "above_20": above_20,
            "above_50": above_50,
            "ema_cross": ema_cross,
            "ema_slope": round(ema_slope, 2),
            "pct_from_ema20": round(pct_from_ema20, 2),
            "rs_vs_spy": round(rs, 2),
            "rvol": round(rvol, 2),
            "structure": structure,
            "price": price,
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
        }

    except Exception as e:
        print(f"[Swing] Error for {ticker}: {e}")
        return {"swing_score": 0, "swing_type": "ERROR", "error": str(e)}
