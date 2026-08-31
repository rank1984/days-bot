"""
DAYS-BOT V3.5 – Research Engine
- Discovery without hard time gates (always returns candidates)
- Filter Funnel tracking
- Top 5 Discovery
- Near Misses
- Market Regime
- Learning Data
"""
from datetime import datetime, time
from typing import List, Dict, Any
import pytz
import pandas as pd
import yfinance as yf

from scanner.universe import load_universe
from scanner.premarket import scan_premarket
from scanner.full_scan_v34 import full_scan_v34
from scanner.analyzers.float_analyzer import get_float_and_short
from scanner.analyzers.volume_analyzer import calculate_rvol

ET = pytz.timezone("America/New_York")


def get_market_regime() -> Dict[str, Any]:
    """Return market regime: SPY/IWM performance, small cap strength"""
    try:
        spy = yf.download("SPY", period="2d", interval="1d", progress=False)
        iwm = yf.download("IWM", period="2d", interval="1d", progress=False)
        spy_change = (spy['Close'].iloc[-1] / spy['Close'].iloc[-2] - 1) * 100 if len(spy) >= 2 else 0
        iwm_change = (iwm['Close'].iloc[-1] / iwm['Close'].iloc[-2] - 1) * 100 if len(iwm) >= 2 else 0
        regime = "BULL" if spy_change > 0.2 else "BEAR" if spy_change < -0.2 else "NEUTRAL"
        small_caps = "STRONG" if iwm_change > 0.3 else "WEAK" if iwm_change < -0.3 else "NEUTRAL"
        return {
            "regime": regime,
            "spy_change": round(spy_change, 2),
            "iwm_change": round(iwm_change, 2),
            "small_caps": small_caps,
            "description": f"SPY: {spy_change:+.2f}% | IWM: {iwm_change:+.2f}% | Small Caps: {small_caps}"
        }
    except:
        return {"regime": "UNKNOWN", "description": "Could not fetch market data"}


def build_discovery_universe() -> List[dict]:
    """Always returns a list of candidates (even if PM data is missing)"""
    universe = load_universe()
    if not universe:
        return []

    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")
    is_after_hours = now_et.time() >= time(9, 30)

    # First try PM scan (if within window)
    if not is_after_hours:
        candidates = scan_premarket(today, manual=True)
        if candidates:
            return candidates

    # Fallback: use regular market data (last 30 mins)
    candidates = []
    for ticker in universe[:20]:  # Limit for speed
        try:
            data = yf.download(ticker, period="1d", interval="5m", progress=False)
            if data.empty:
                continue
            data.index = pd.to_datetime(data.index)
            if data.index.tz is None:
                data.index = data.index.tz_localize("UTC")
            data.index = data.index.tz_convert(ET)
            # Last 30 min
            data = data[data.index >= now_et - pd.Timedelta(minutes=30)]
            if data.empty:
                continue
            price = float(data['Close'].iloc[-1])
            volume = int(data['Volume'].sum())

            # Get previous close
            prev_data = yf.download(ticker, period="2d", interval="1d", progress=False)
            if not prev_data.empty:
                prev_close = float(prev_data['Close'].iloc[-1])
                gap_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            else:
                gap_pct = 0

            candidate = {
                "ticker": ticker,
                "price": price,
                "gap_pct": gap_pct,
                "pm_volume": volume,
                "pm_high": float(data['High'].max()),
                "pm_low": float(data['Low'].min()),
                "pm_vwap": float((data['Close'] * data['Volume']).sum() / data['Volume'].sum()) if data['Volume'].sum() > 0 else price,
                "pm_dist_signed": 0,
                "pm_bars": len(data),
                "event_score": 50,  # Neutral
                "state": "POST_MARKET",
                "pm_data_quality": "LOW_DATA" if len(data) < 3 else "GOOD_DATA",
                "mode": "RESEARCH",
                "strategy_version": "V3.5",
                "data_version": "YFINANCE_V35",
                "scan_date": today,
            }
            candidates.append(candidate)
        except:
            continue

    # Sort by volume (or gap)
    candidates.sort(key=lambda x: x.get('pm_volume', 0), reverse=True)
    return candidates[:20]


def run_research_engine() -> Dict[str, Any]:
    """
    Main research engine - always returns structured output
    """
    candidates = build_discovery_universe()
    if not candidates:
        return {
            "top5": [],
            "funnel": {"universe": 103, "discovery": 0, "analysis": 0, "trade": 0},
            "near_misses": [],
            "regime": get_market_regime(),
            "trade_candidates": [],
            "decision": "NO_DATA"
        }

    # Run full analysis on top 20
    enriched = full_scan_v34(candidates, manual=True)

    # Compute filter funnel
    funnel = {
        "universe": len(candidates) + 10,  # approximate
        "discovery": len(candidates),
        "analysis": len(enriched),
        "trade": sum(1 for c in enriched if c.get('plan_valid', False))
    }

    # Top 5 Discovery (by composite score)
    if enriched:
        enriched.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
        top5 = enriched[:5]
    else:
        # Fallback: top 5 candidates
        candidates.sort(key=lambda x: x.get('event_score', 0), reverse=True)
        top5 = candidates[:5]

    # Near misses: candidates that passed most gates but failed one
    near_misses = []
    for c in enriched[:10]:
        score = c.get('composite_score', 0)
        if score > 60 and not c.get('plan_valid', False):
            reasons = []
            if c.get('analysis', {}).get('personality', {}).get('personality') == "GAP_AND_CRAP":
                reasons.append("Personality = GAP_AND_CRAP")
            if c.get('analysis', {}).get('sec_risk', {}).get('has_offering'):
                reasons.append("SEC risk")
            if c.get('analysis', {}).get('rvol', 0) < 3:
                reasons.append("RVOL below threshold")
            if c.get('pm_dist_signed', 0) < 0:
                reasons.append("Below PM High")
            if reasons:
                near_misses.append({
                    "ticker": c['ticker'],
                    "score": score,
                    "reason": ", ".join(reasons[:2]),
                    "candidate": c
                })

    # Trade candidates (valid plans)
    trade_candidates = [c for c in enriched if c.get('plan_valid', False)]

    return {
        "top5": top5,
        "funnel": funnel,
        "near_misses": near_misses[:3],
        "regime": get_market_regime(),
        "trade_candidates": trade_candidates,
        "decision": "TRADE" if trade_candidates else "NO_TRADE",
        "all_candidates": enriched if enriched else candidates
    }
