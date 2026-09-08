"""
DAYS-BOT V5.0.4 – Full Scan Engine (Type-Safe)
"""
from datetime import datetime
from typing import List, Dict, Any
import pytz

from scanner.pm_engine import get_premarket_minute_data
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
from scanner.early_move import calculate_early_move_score
from risk.trade_plan_v34 import build_trade_plan
from scanner.scoring_engine import calculate_composite_score
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT

ET = pytz.timezone("America/New_York")


def _safe_call(func, default, *args, expected_type=None, name=None, **kwargs):
    """
    Type-safe wrapper: ensures result is of expected_type, otherwise returns default.
    """
    label = name or getattr(func, "__name__", "unknown")

    try:
        result = func(*args, **kwargs)

        if expected_type is not None and not isinstance(result, expected_type):
            print(
                f"[FullScan] ⚠️ {label}: "
                f"expected {expected_type.__name__}, "
                f"got {type(result).__name__}"
            )
            return default

        return result

    except Exception as e:
        print(f"[FullScan] ❌ {label}: {type(e).__name__}: {e}")
        return default


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
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

    pm_high = candidate.get('pm_high')
    if pm_high is None or pm_high == 0:
        if "PM High" not in missing:
            missing.append("PM High")

    status = "ACTIONABLE" if len(missing) == 0 else "WATCH" if len(missing) <= 2 else "NO_TRADE"

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

        # ------------------------------------------------------------
        # 1. PM DATA (Alpaca 1-min bars)
        # ------------------------------------------------------------
        pm_data = _safe_call(get_premarket_minute_data, {}, ticker, expected_type=dict, name=f"pm:{ticker}")
        if pm_data and pm_data.get('error') is None:
            c['pm_high'] = pm_data.get('pm_high')
            c['pm_low'] = pm_data.get('pm_low')
            c['pm_vwap'] = pm_data.get('pm_vwap')
            c['pm_volume'] = pm_data.get('pm_volume')
            c['pm_bars'] = pm_data.get('pm_bars_count', 0)
            c['pm_data_quality'] = pm_data.get('pm_data_quality', 'LOW_DATA')
            c['pm_dist_signed'] = ((_safe_float(c['price']) - _safe_float(c['pm_high'])) / _safe_float(c['pm_high'])) * 100.0 if c['pm_high'] and _safe_float(c['pm_high']) > 0 else None
        else:
            c['pm_high'] = None
            c['pm_low'] = None
            c['pm_vwap'] = None
            c['pm_bars'] = 0
            c['pm_data_quality'] = 'UNAVAILABLE'
            c['pm_dist_signed'] = None

        analysis['pm_data_quality'] = c['pm_data_quality']

        # ------------------------------------------------------------
        # 2. EARLY MOVE ENGINE
        # ------------------------------------------------------------
        early_data = _safe_call(
            calculate_early_move_score,
            {"early_score": 0, "state": "UNKNOWN", "components": {}, "data_quality": "UNKNOWN"},
            ticker,
            c.get('pm_high'),
            c.get('pm_vwap'),
            expected_type=dict,
            name=f"early:{ticker}"
        )

        c['early_score'] = early_data.get('early_score', 0)
        c['early_state'] = early_data.get('state', 'UNKNOWN')
        c['early_components'] = early_data.get('components', {})
        c['early_data_quality'] = early_data.get('data_quality', 'UNKNOWN')
        analysis['early'] = early_data

        # ------------------------------------------------------------
        # 3. BASIC FIELDS
        # ------------------------------------------------------------
        c['price'] = _safe_float(c.get('price', 0))
        c['gap_pct'] = _safe_float(c.get('gap_pct', 0))

        # Spread
        spread = c.get('spread_pct')
        if spread is None or spread == "UNAVAILABLE":
            c['spread_pct'] = None
        analysis['spread_pct'] = c['spread_pct']

        c['bid'] = c.get('bid', None)
        c['ask'] = c.get('ask', None)
        analysis['bid'] = c['bid']
        analysis['ask'] = c['ask']

        # ------------------------------------------------------------
        # 4. RVOL (INFORMATIONAL – with rvol_data dict)
        # ------------------------------------------------------------
        rvol_data = _safe_call(
            calculate_rvol,
            {"rvol": None, "status": "UNAVAILABLE", "method": "DEFAULT"},
            c,
            expected_type=dict,
            name=f"rvol:{ticker}"
        )

        if not isinstance(rvol_data, dict):
            rvol_data = {"rvol": None, "status": "UNAVAILABLE", "method": "INVALID_RESPONSE"}

        c['rvol'] = rvol_data.get('rvol')
        c['rvol_status'] = rvol_data.get('status', 'UNAVAILABLE')
        c['rvol_method'] = rvol_data.get('method', 'UNAVAILABLE')

        # Store full dict for scoring
        analysis['rvol_data'] = rvol_data
        analysis['rvol'] = c['rvol']
        analysis['rvol_status'] = c['rvol_status']

        # ------------------------------------------------------------
        # 5. RS
        # ------------------------------------------------------------
        analysis['rs'] = _safe_call(get_relative_strength, None, ticker, expected_type=(float, int, type(None)), name=f"rs:{ticker}")
        c['rs'] = analysis['rs']

        # ------------------------------------------------------------
        # 6. NEWS & CATALYST
        # ------------------------------------------------------------
        analysis['news'] = _safe_call(fetch_news, [], ticker, expected_type=list, name=f"news:{ticker}")
        c['news'] = analysis['news']

        catalyst = _safe_call(
            classify_catalyst,
            {},
            analysis['news'],
            expected_type=dict,
            name=f"catalyst:{ticker}"
        )
        if isinstance(catalyst, dict):
            c['catalyst_type'] = catalyst.get('type', 'UNAVAILABLE')
            c['catalyst_score'] = catalyst.get('score', 0)
            c['catalyst_summary'] = catalyst.get('summary', '')
        else:
            c['catalyst_type'] = 'UNAVAILABLE'
            c['catalyst_score'] = 0
            c['catalyst_summary'] = ''
        analysis['catalyst'] = catalyst

        # ------------------------------------------------------------
        # 7. SENTIMENT (optional)
        # ------------------------------------------------------------
        analysis['sentiment'] = _safe_call(get_stocktwits_sentiment, {}, ticker, expected_type=dict, name=f"sentiment:{ticker}")
        c['sentiment'] = analysis['sentiment']

        # ------------------------------------------------------------
        # 8. SEC RISK
        # ------------------------------------------------------------
        sec_risk = _safe_call(
            check_offering_risk,
            {"has_offering": False, "risk_level": "UNAVAILABLE"},
            ticker,
            expected_type=dict,
            name=f"sec:{ticker}"
        )
        analysis['sec_risk'] = sec_risk
        c['sec_risk'] = sec_risk
        c['sec_risk_level'] = sec_risk.get('risk_level', 'UNAVAILABLE')
        c['sec_has_offering'] = sec_risk.get('has_offering', False)

        # ------------------------------------------------------------
        # 9. FLOAT & SHORT
        # ------------------------------------------------------------
        float_data = _safe_call(
            get_float_and_short,
            {},
            ticker,
            expected_type=dict,
            name=f"float:{ticker}"
        )
        analysis['float_data'] = float_data
        c['float'] = float_data.get('float')
        c['short_interest'] = float_data.get('short_interest')
        c['short_ratio'] = float_data.get('short_ratio')
        analysis['float'] = c['float']
        analysis['short_interest'] = c['short_interest']

        # ------------------------------------------------------------
        # 10. PERSONALITY (CRITICAL: store as dict, not string)
        # ------------------------------------------------------------
        personality = _safe_call(
            get_stock_personality,
            {"personality": "UNKNOWN", "failure_rate": 0, "sample_size": 0},
            ticker,
            c.get('gap_pct', 0),
            expected_type=dict,
            name=f"personality:{ticker}"
        )

        if isinstance(personality, dict):
            c['personality'] = personality.get('personality', 'UNKNOWN')
            c['personality_failure_rate'] = personality.get('failure_rate', 0)
            c['personality_sample_size'] = personality.get('sample_size', 0)
        else:
            c['personality'] = 'UNKNOWN'
            c['personality_failure_rate'] = 0
            c['personality_sample_size'] = 0
            personality = {"personality": "UNKNOWN", "failure_rate": 0, "sample_size": 0}

        analysis['personality'] = personality  # store dict, not string

        # ------------------------------------------------------------
        # 11. VWAP
        # ------------------------------------------------------------
        if c.get('pm_high') is not None and _safe_float(c['pm_high']) > 0:
            vwap_data = {
                "vwap": c.get('pm_vwap'),
                "vwap_high": c.get('pm_high'),
                "vwap_low": c.get('pm_low'),
                "vwap_support": _safe_float(c.get('pm_vwap')) * 0.995 if c.get('pm_vwap') else None,
                "vwap_resistance": _safe_float(c.get('pm_vwap')) * 1.005 if c.get('pm_vwap') else None,
                "source": "premarket"
            }
        else:
            vwap_data = _safe_call(calculate_vwap, {}, ticker, 30, expected_type=dict, name=f"vwap:{ticker}")
        analysis['vwap'] = vwap_data
        c['vwap_data'] = vwap_data
        c['vwap'] = vwap_data.get('vwap', 0) if vwap_data else None

        # ------------------------------------------------------------
        # 12. SYMPATHY (optional)
        # ------------------------------------------------------------
        analysis['sympathy'] = _safe_call(find_sympathy_candidates, [], c, 3, expected_type=list, name=f"sympathy:{ticker}")
        c['sympathy'] = analysis['sympathy']

        # ------------------------------------------------------------
        # 13. TRADE PLAN
        # ------------------------------------------------------------
        plan = _safe_call(
            build_trade_plan,
            {},
            c,
            ACCOUNT_SIZE,
            MAX_RISK_PER_TRADE_V31,
            MAX_POSITION_VALUE_PCT,
            expected_type=dict,
            name=f"tradeplan:{ticker}"
        )
        if plan:
            c.update(plan)
        else:
            c['plan_valid'] = False
            c['plan_error'] = 'Trade plan build failed'

        c['account_size'] = ACCOUNT_SIZE
        c['risk_pct'] = MAX_RISK_PER_TRADE_V31

        # ------------------------------------------------------------
        # 14. COMPOSITE SCORE (with error distinction)
        # ------------------------------------------------------------
        score = _safe_call(
            calculate_composite_score,
            None,
            c,
            analysis,
            expected_type=(int, float, type(None)),
            name=f"score:{ticker}"
        )

        if score is None:
            c['composite_score'] = None
            c['score_status'] = 'ERROR'
        else:
            c['composite_score'] = round(float(score), 1)
            c['score_status'] = 'OK'

        # ------------------------------------------------------------
        # 15. DATA COMPLETENESS GATE
        # ------------------------------------------------------------
        completeness = _check_data_completeness(c)
        c['data_completeness'] = completeness
        c['data_status'] = completeness['status']

        if completeness['status'] == 'NO_TRADE':
            c['trade_type'] = 'NO_TRADE'
        elif completeness['status'] == 'WATCH':
            c['trade_type'] = 'WATCH'

        # ------------------------------------------------------------
        # 16. DIAGNOSTICS CONTRACT
        # ------------------------------------------------------------
        c['diagnostics'] = {
            'pm': c.get('pm_data_quality'),
            'early': c.get('early_data_quality'),
            'rvol': c.get('rvol_status'),
            'catalyst': c.get('catalyst_type'),
            'sec': c.get('sec_risk_level'),
            'score': c.get('score_status'),
        }

        c['analysis'] = analysis
        enriched.append(c)

    # Sort: handle None scores
    enriched.sort(
        key=lambda x: x.get('composite_score') if isinstance(x.get('composite_score'), (int, float)) else -1,
        reverse=True
    )

    return enriched[:5] if len(enriched) >= 5 else enriched
