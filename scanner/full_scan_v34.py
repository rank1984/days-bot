"""
DAYS-BOT V5.0 – Full Scan Engine (with Dynamic Scoring)
"""
from datetime import datetime
from typing import List, Dict, Any
import pytz

from scanner.pm_engine import get_premarket_minute_data
from scanner.early_move import calculate_early_move_score
from scanner.scoring_dynamic import calculate_dynamic_scores
from scanner.analyzers.float_analyzer import get_float_and_short
from scanner.analyzers.sec_analyzer import check_offering_risk
from scanner.analyzers.catalyst_analyzer import classify_catalyst
from scanner.analyzers.sentiment_social import get_stocktwits_sentiment
from scanner.analyzers.news_analyzer import fetch_news
from scanner.analyzers.volume_analyzer import calculate_rvol
from scanner.analyzers.rs_analyzer import get_relative_strength
from scanner.analyzers.personality_analyzer import get_stock_personality
from scanner.analyzers.sympathy_scanner import find_sympathy_candidates
from scanner.vwap_engine import calculate_vwap
from risk.trade_plan_v34 import build_trade_plan
from scanner.scoring_engine import calculate_composite_score  # legacy, keep for fallback
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT

ET = pytz.timezone("America/New_York")


def _safe_call(func, default, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[FullScan] Call error: {e}")
        return default


def _check_data_completeness(candidate: dict) -> dict:
    missing = []
    critical_fields = [
        ("price", "מחיר"),
        ("gap_pct", "גאפ"),
        ("pm_volume", "נפח PM"),
        ("pm_high", "PM High"),
        ("pm_vwap", "VWAP"),
        ("catalyst_type", "קטליזטור"),
        ("sec_risk_level", "SEC Risk"),
    ]
    for field, label in critical_fields:
        value = candidate.get(field)
        if value is None or value == "UNAVAILABLE" or value == "":
            missing.append(label)
    if candidate.get('pm_high') is None or candidate.get('pm_high') == 0:
        if "PM High" not in missing:
            missing.append("PM High")
    status = "ACTIONABLE" if len(missing) == 0 else "WATCH" if len(missing) <= 2 else "NO_TRADE"
    return {"complete": len(missing) == 0, "missing": missing, "status": status}


def full_scan_v34(candidates: List[dict], manual: bool = False) -> List[dict]:
    if not candidates:
        return []

    print(f"[FullScan] Analyzing {len(candidates)} candidates...")
    enriched = []

    for idx, c in enumerate(candidates[:25]):
        ticker = c.get('ticker', 'UNKNOWN')
        print(f"[FullScan] {idx+1}/{min(len(candidates), 25)} {ticker}")

        analysis = {}

        # ------------------------------------------------------------
        # 1. REAL PM DATA
        # ------------------------------------------------------------
        pm_data = _safe_call(get_premarket_minute_data, {}, ticker)
        if pm_data and pm_data.get('error') is None:
            c['pm_high'] = pm_data.get('pm_high')
            c['pm_low'] = pm_data.get('pm_low')
            c['pm_vwap'] = pm_data.get('pm_vwap')
            c['pm_volume'] = pm_data.get('pm_volume')
            c['pm_bars'] = pm_data.get('pm_bars_count', 0)
            c['pm_data_quality'] = pm_data.get('pm_data_quality', 'LOW_DATA')
            c['pm_dist_signed'] = ((c['price'] - c['pm_high']) / c['pm_high']) * 100.0 if c['pm_high'] and c['pm_high'] > 0 else None
        else:
            c['pm_high'] = None
            c['pm_low'] = None
            c['pm_vwap'] = None
            c['pm_bars'] = 0
            c['pm_data_quality'] = 'UNAVAILABLE'
            c['pm_dist_signed'] = None

        analysis['pm_data_quality'] = c['pm_data_quality']

        # Ensure basic fields exist
        c['price'] = c.get('price', 0)
        c['gap_pct'] = c.get('gap_pct', 0)

        # Spread
        spread = c.get('spread_pct')
        if spread is None or spread == "UNAVAILABLE":
            c['spread_pct'] = None
        analysis['spread_pct'] = c['spread_pct']

        c['bid'] = c.get('bid', None)
        c['ask'] = c.get('ask', None)
        analysis['bid'] = c['bid']
        analysis['ask'] = c['ask']

        # RVOL (informational)
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
        if c.get('pm_high') is not None and c.get('pm_high') > 0:
            vwap_data = {
                "vwap": c.get('pm_vwap'),
                "vwap_high": c.get('pm_high'),
                "vwap_low": c.get('pm_low'),
                "vwap_support": c.get('pm_vwap') * 0.995 if c.get('pm_vwap') else None,
                "vwap_resistance": c.get('pm_vwap') * 1.005 if c.get('pm_vwap') else None,
                "source": "premarket"
            }
        else:
            vwap_data = _safe_call(calculate_vwap, {}, ticker, 30)
        analysis['vwap'] = vwap_data
        c['vwap_data'] = vwap_data
        c['vwap'] = vwap_data.get('vwap', 0) if vwap_data else None

        # Sympathy
        analysis['sympathy'] = _safe_call(find_sympathy_candidates, [], c, 3)
        c['sympathy'] = analysis['sympathy']

        # Early Move (NEW)
        early_data = _safe_call(
            calculate_early_move_score,
            {},
            ticker,
            c.get('pm_high'),
            c.get('pm_vwap'),
            None  # bars will be fetched internally
        )
        if early_data:
            c['early_score'] = early_data.get('early_score', 0)
            c['early_state'] = early_data.get('state', 'UNKNOWN')
            c['early_components'] = early_data.get('components', {})
        else:
            c['early_score'] = 0
            c['early_state'] = 'UNKNOWN'
            c['early_components'] = {}
        analysis['early'] = early_data

        # Dynamic Scores (NEW)
        dynamic = _safe_call(
            calculate_dynamic_scores,
            {},
            c,
            analysis,
            early_data or {}
        )
        if dynamic:
            c['day_trade_score'] = dynamic.get('day_trade_score', 0)
            c['swing_score'] = dynamic.get('swing_score', 0)
            c['early_score'] = dynamic.get('early_score', 0)
            c['early_state'] = dynamic.get('early_state', 'UNKNOWN')
            c['early_components'] = dynamic.get('early_components', {})
        else:
            c['day_trade_score'] = 0
            c['swing_score'] = 0

        # Trade Plan (still uses legacy trade plan)
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

        # Legacy Composite Score (keep for fallback)
        legacy_score = _safe_call(calculate_composite_score, 0, c, analysis)
        c['composite_score'] = legacy_score

        # Data Completeness Gate
        completeness = _check_data_completeness(c)
        c['data_completeness'] = completeness
        c['data_status'] = completeness['status']

        if completeness['status'] == 'NO_TRADE':
            c['trade_type'] = 'NO_TRADE'
        elif completeness['status'] == 'WATCH':
            c['trade_type'] = 'WATCH'
        else:
            # ACTIONABLE – use dynamic to determine trade type
            if c.get('day_trade_score', 0) >= 70 and c.get('swing_score', 0) >= 70:
                c['trade_type'] = 'BOTH'
            elif c.get('day_trade_score', 0) >= 70:
                c['trade_type'] = 'INTRADAY'
            elif c.get('swing_score', 0) >= 70:
                c['trade_type'] = 'SWING_1_3D'
            else:
                c['trade_type'] = 'WATCH'

        c['analysis'] = analysis
        enriched.append(c)

    enriched.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
    return enriched[:5] if len(enriched) >= 5 else enriched
