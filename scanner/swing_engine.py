"""
DAYS-BOT V5.0.4 – Swing Engine (1–3 Days)

Evaluates candidates for swing holding period.
- Trend: 20 EMA, 50 EMA, slope
- Relative Strength vs SPY
- Volume (RVOL, accumulation)
- Structure (breakout, consolidation)
- Catalyst quality & freshness
- Risk (SEC, Earnings)

All pandas values are explicitly converted to Python scalars.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time

ET = pytz.timezone("America/New_York")


def _safe_float(value, default=0.0):
    """Safely convert pandas/numpy values to float."""
    try:
        if value is None:
            return default
        if isinstance(value, (pd.Series, pd.DataFrame)):
            if value.empty:
                return default
            value = value.iloc[0]
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        if isinstance(value, (pd.Series, pd.DataFrame)):
            if value.empty:
                return default
            value = value.iloc[0]
        if pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_spy_data():
    """Fetch SPY daily data once per run (cached)."""
    if not hasattr(_get_spy_data, "cache"):
        try:
            spy = yf.download("SPY", period="60d", interval="1d", progress=False)
            _get_spy_data.cache = spy
        except Exception:
            _get_spy_data.cache = pd.DataFrame()
    return _get_spy_data.cache


def _qualify_swing(candidate: dict, analysis: dict, swing_score: float) -> bool:
    """
    Swing Qualification Gate.
    Uses candidate + analysis to check data completeness.
    """
    if swing_score < 75:
        return False

    # Data status from Completeness Gate
    data_status = candidate.get('data_status', 'NO_TRADE')
    if data_status == 'NO_TRADE':
        return False

    # SEC Risk
    sec_risk = candidate.get('sec_risk_level', 'LOW')
    if sec_risk == 'HIGH':
        return False

    # Spread
    spread = candidate.get('spread_pct')
    if spread is not None and spread > 5.0:
        return False

    # Catalyst
    catalyst_type = candidate.get('catalyst_type')
    catalyst_ok = catalyst_type not in (None, 'UNAVAILABLE', 'NO_NEWS')

    # Early Move
    early_state = candidate.get('early_state')
    early_score = candidate.get('early_score', 0)
    early_ok = early_state not in (None, 'UNAVAILABLE') and early_score > 60

    # Float – from analysis['float_data']
    float_data = analysis.get('float_data', {})
    float_val = _safe_float(float_data.get('float', 0), 0)
    float_ok = float_val > 0 and float_val < 20_000_000

    # Short Interest – from analysis['float_data']
    short_interest = _safe_float(float_data.get('short_interest', 0), 0)
    short_ok = short_interest > 0 and short_interest >= 0.15

    # Breakout structure
    structure = candidate.get('swing_data', {}).get('structure', '')
    structure_ok = structure in ('BREAKOUT', 'CONSOLIDATION')

    # At least one criterion must be met
    return catalyst_ok or early_ok or float_ok or short_ok or structure_ok


def calculate_swing_score(candidate: dict, analysis: dict = None) -> dict:
    """
    Swing Score (0-100) for 1-3 day holding period.
    analysis parameter is passed from full_scan_v34.py.
    """
    ticker = candidate.get('ticker', 'UNKNOWN')
    price = _safe_float(candidate.get('price', 0))
    gap_pct = _safe_float(candidate.get('gap_pct', 0))

    if analysis is None:
        analysis = {}

    try:
        # Fetch daily data for last 60 days
        data = yf.download(ticker, period="60d", interval="1d", progress=False)
        if data.empty or len(data) < 20:
            return {"swing_score": 0, "swing_type": "INSUFFICIENT_DATA"}

        # SPY for RS
        spy = _get_spy_data()
        if spy.empty:
            spy_ret = 0
        else:
            spy_ret = _safe_float((spy['Close'].iloc[-1] / spy['Close'].iloc[-20] - 1) * 100) if len(spy) >= 20 else 0

        close = data['Close']
        volume = data['Volume']

        # 20 EMA & 50 EMA
        ema20 = _safe_float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = _safe_float(close.ewm(span=50, adjust=False).mean().iloc[-1]) if len(close) >= 50 else ema20

        # Price vs EMAs
        above_20 = price > ema20
        above_50 = price > ema50
        ema_cross = ema20 > ema50

        # EMA slope (20-day)
        ema20_series = close.ewm(span=20, adjust=False).mean()
        if len(ema20_series) >= 10:
            ema_slope = _safe_float((ema20_series.iloc[-1] / ema20_series.iloc[-10] - 1) * 100)
        else:
            ema_slope = 0.0

        # Price vs 20 EMA distance
        pct_from_ema20 = _safe_float(((price - ema20) / ema20) * 100) if ema20 > 0 else 0.0

        # Relative Strength vs SPY (20-day)
        stock_ret = _safe_float((close.iloc[-1] / close.iloc[-20] - 1) * 100) if len(close) >= 20 else 0.0
        rs = stock_ret - spy_ret if spy_ret else stock_ret

        # Volume – RVOL (last 5 days avg vs 50 day avg)
        avg_vol_50 = _safe_float(volume.iloc[-50:].mean()) if len(volume) >= 50 else _safe_float(volume.mean())
        avg_vol_5 = _safe_float(volume.iloc[-5:].mean())
        rvol = avg_vol_5 / avg_vol_50 if avg_vol_50 > 0 else 1.0

        # Structure: Higher highs/lows (last 10 days)
        recent_highs = _safe_float(close.iloc[-10:].max())
        recent_lows = _safe_float(close.iloc[-10:].min())
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
        cat_type = candidate.get('catalyst_type', '')
        if cat_type in ['FDA_APPROVAL', 'M&A']:
            catalyst_score = 15
        elif cat_type in ['EARNINGS', 'CONTRACT', 'PARTNERSHIP']:
            catalyst_score = 12
        elif cat_type == 'STRONG':
            catalyst_score = 10
        else:
            catalyst_score = 5
        catalyst_score = min(catalyst_score, 15)

        risk_penalty = 0
        sec_level = candidate.get('sec_risk_level', 'LOW')
        if sec_level == 'HIGH':
            risk_penalty -= 30
        elif sec_level == 'MEDIUM':
            risk_penalty -= 15
        # Earnings risk
        earnings_date = candidate.get('earnings_date')
        if earnings_date:
            try:
                ed = pd.to_datetime(earnings_date)
                days_until = (ed - datetime.now(ET)).days
                if days_until <= 2:
                    risk_penalty -= 20
                elif days_until <= 5:
                    risk_penalty -= 10
            except:
                pass

        float_data = analysis.get('float_data', {})
        float_val = _safe_float(float_data.get('float', 0))
        if float_val > 100_000_000:
            risk_penalty -= 10
        elif float_val > 50_000_000:
            risk_penalty -= 5

        total_score = trend_score + rs_score + volume_score + structure_score + catalyst_score + risk_penalty
        total_score = max(0, min(100, total_score))

        # Qualification Gate
        qualified = _qualify_swing(candidate, analysis, total_score)

        result = {
            "swing_score": round(total_score, 1),
            "qualified": qualified,
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

        candidate['qualified'] = qualified
        return result

    except Exception as e:
        print(f"[Swing] Error for {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return {"swing_score": 0, "swing_type": "ERROR", "error": str(e)}
