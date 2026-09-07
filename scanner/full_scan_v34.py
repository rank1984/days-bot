"""
DAYS-BOT V4.3 – Full Scan Engine
- Propagates ALL fields from candidate → analysis → DB → Telegram
- Implements Data Completeness Gate: missing critical data prevents TRADE
"""
from datetime import datetime
from typing import List, Dict, Any
import pytz

from scanner.analyzers.float_analyzer import get_float_and_short
from scanner.analyzers.sec_analyzer import check_offering_risk
from scanner.analyzers.catalyst_analyzer import classify_catalyst
from scanner.analyzers.sentiment_social import get_stocktwits_sentiment
from scanner.analyzers.news_analyzer import fetch_news
from scanner.analyzers.volume_analyzer import calculate_rvol
from scanner.analyzers.rs_analyzer import get_relative_strength
from scanner.analyzers.personality_analyzer import get_stock_personality
from scanner.analyzers.sympathy_scanner import find_sympathy_candidates
from scanner.vwap_engine import calculate_vwap, calculate_pm_vwap_from_candidate
from risk.trade_plan_v34 import build_trade_plan
from scanner.scoring_engine import calculate_composite_score
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT

ET = pytz.timezone("America/New_York")


def _safe_call(func, default, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[FullScan] Call error: {e}")
        return default


def _check_data_completeness(candidate: dict) -> dict:
    """
    Check if critical data is available.
    Returns: {"complete": bool, "missing": list, "status": "ACTIONABLE"|"WATCH"|"NO_TRADE"}
    """
    missing = []
    critical_fields = [
        ("price", "מחיר"),
        ("gap_pct", "גאפ"),
        ("pm_volume", "נפח PM"),
        ("pm_high", "PM High"),
        ("pm_vwap", "VWAP"),
        ("spread_pct", "מרווח"),
        ("rvol", "RVOL"),
        ("catalyst_type", "קטליזטור"),
        ("sec_risk_level", "SEC Risk"),
    ]

    for field, label in critical_fields:
        value = candidate.get(field)
        if value is None or value == "UNAVAILABLE" or value == "":
            missing.append(label)

    # Special case: spread_pct can be None (UNAVAILABLE) but if it's a number, it's ok
    if candidate.get("spread_pct") is not None and candidate.get("spread_pct") != "UNAVAILABLE":
        if field == "spread_pct":
            missing.remove("מרווח") if "מרווח" in missing else None

    # Determine status
    if len(missing) == 0:
        status = "ACTIONABLE"
    elif len(missing) <= 2:
        status = "WATCH"
    else:
        status = "NO_TRADE"

    return {
        "complete": len(missing) == 0,
        "missing": missing,
        "status": status
    }


def full_scan_v34(candidates: List[dict], manual: bool = False) -> List[dict]:
    if not candidates:
        return []

    print(f"[FullScan] Analyzing {len(candidates)} candidates...")
    enriched = []

    for idx, c in enumerate(candidates[:25]):
        ticker = c.get('ticker', 'UNKNOWN')
        print(f"[FullScan] {idx+1}/{min(len(candidates), 25)} {ticker}")

        analysis = {}

        # Ensure basic fields exist
        if 'pm_data_quality' not in c or c['pm_data_quality'] is None:
            c['pm_data_quality'] = 'UNKNOWN_PM_DATA'
        analysis['pm_data_quality'] = c['pm_data_quality']

        c['price'] = c.get('price', 0)
        c['gap_pct'] = c.get('gap_pct', 0)
        c['pm_volume'] = c.get('pm_volume', 0)
        c['pm_high'] = c.get('pm_high', 0)
        c['pm_vwap'] = c.get('pm_vwap', 0)

        # Spread – from discovery
        spread = c.get('spread_pct')
        if spread is None or spread == "UNAVAILABLE":
            c['spread_pct'] = None
        analysis['spread_pct'] = c['spread_pct']

        c['bid'] = c.get('bid', None)
        c['ask'] = c.get('ask', None)
        analysis['bid'] = c['bid']
        analysis['ask'] = c['ask']

        # RVOL
        rvol_data = _safe_call(calculate_rvol, {}, c)
        if isinstance(rvol_data, dict):
            c['rvol'] = rvol_data.get('rvol', None)
            c['rvol_status'] = rvol_data.get('status', 'UNAVAILABLE')
            c['rvol_method'] = rvol_data.get('method', 'UNAVAILABLE')
        else:
            c['rvol'] = None
            c['rvol_status'] = 'UNAVAILABLE'
            c['rvol_method'] = 'UNAVAILABLE'
        analysis['rvol'] = c['rvol']
        analysis['rvol_status'] = c['rvol_status']
        analysis['rvol_method'] = c['rvol_method']

        # RS
        analysis['rs'] = _safe_call(get_relative_strength, None, ticker)
        c['rs'] = analysis['rs']

        # News & Catalyst
        analysis['news'] = _safe_call(fetch_news, [], ticker)
        c['news'] = analysis['news']

        catalyst = _safe_call(classify_catalyst, {}, analysis['news'])
        if isinstance(catalyst, dict):
            c['catalyst_type'] = catalyst.get('type', 'UNAVAILABLE')
            c['catalyst_score'] = catalyst.get('score', 0)
            c['catalyst_summary'] = catalyst.get('summary', '')
        else:
            c['catalyst_type'] = 'UNAVAILABLE'
            c['catalyst_score'] = 0
            c['catalyst_summary'] = ''
        analysis['catalyst'] = catalyst

        # Sentiment
        analysis['sentiment'] = _safe_call(get_stocktwits_sentiment, {}, ticker)
        c['sentiment'] = analysis['sentiment']

        # SEC Risk
        analysis['sec_risk'] = _safe_call(check_offering_risk, {}, ticker)
        c['sec_risk'] = analysis['sec_risk']
        if isinstance(analysis['sec_risk'], dict):
            c['sec_risk_level'] = analysis['sec_risk'].get('risk_level', 'LOW')
            c['sec_has_offering'] = analysis['sec_risk'].get('has_offering', False)
        else:
            c['sec_risk_level'] = 'LOW'
            c['sec_has_offering'] = False

        # Float & Short
        analysis['float_data'] = _safe_call(get_float_and_short, {}, ticker)
        c['float'] = analysis['float_data'].get('float')
        c['short_interest'] = analysis['float_data'].get('short_interest')
        c['short_ratio'] = analysis['float_data'].get('short_ratio')
        analysis['float'] = c['float']
        analysis['short_interest'] = c['short_interest']

        # Personality
        analysis['personality'] = _safe_call(get_stock_personality, {}, ticker, c.get('gap_pct', 0))
        c['personality'] = analysis['personality']

        # VWAP
        vwap_data = _safe_call(calculate_vwap, {}, ticker, 30)
        if not vwap_data:
            vwap_data = _safe_call(calculate_pm_vwap_from_candidate, {}, c)
        analysis['vwap'] = vwap_data
        c['vwap_data'] = vwap_data
        if isinstance(vwap_data, dict):
            c['vwap'] = vwap_data.get('vwap', 0)
            c['vwap_support'] = vwap_data.get('vwap_support', 0)
            c['vwap_resistance'] = vwap_data.get('vwap_resistance', 0)
        else:
            c['vwap'] = 0

        # Sympathy
        analysis['sympathy'] = _safe_call(find_sympathy_candidates, [], c, 3)
        c['sympathy'] = analysis['sympathy']

        # Trade Plan
        plan = _safe_call(
            build_trade_plan,
            {},
            c,
            ACCOUNT_SIZE,
            MAX_RISK_PER_TRADE_V31,
            MAX_POSITION_VALUE_PCT
        )
        if plan:
            c.update(plan)
        else:
            c['plan_valid'] = False
            c['plan_error'] = 'Trade plan build failed'

        c['account_size'] = ACCOUNT_SIZE
        c['risk_pct'] = MAX_RISK_PER_TRADE_V31

        # Composite Score
        c['composite_score'] = _safe_call(calculate_composite_score, 0, c, analysis)

        # Data Completeness Gate
        completeness = _check_data_completeness(c)
        c['data_completeness'] = completeness
        c['data_status'] = completeness['status']

        # Override trade_type if data is incomplete
        if completeness['status'] == 'NO_TRADE':
            c['trade_type'] = 'NO_TRADE'
        elif completeness['status'] == 'WATCH' and c.get('trade_type') in ['INTRADAY', 'SWING_1_3D', 'BOTH']:
            c['trade_type'] = 'WATCH'

        # Store analysis
        c['analysis'] = analysis
        enriched.append(c)

    # Sort by composite score
    enriched.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

    top5 = enriched[:5] if len(enriched) >= 5 else enriched

    print(f"[FullScan] Returning {len(top5)} candidates")
    return top5