"""
DAYS-BOT V5.0.5.1 – Full Scan Engine
FIX A: pm_volume_status → ZERO vs VOLUME_UNAVAILABLE (yfinance)
"""
from datetime import datetime
from typing import List, Dict, Any, Tuple
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
from scanner.analyzers.corporate_action_analyzer import check_corporate_action
from scanner.vwap_engine import calculate_vwap
from scanner.early_move import calculate_early_move_score
from risk.trade_plan_v34 import build_trade_plan
from scanner.scoring_engine import calculate_composite_score
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT

ET = pytz.timezone("America/New_York")

LIQUIDITY_MAX_SPREAD_PCT = 8.0
LIQUIDITY_MIN_PRICE = 1.0
LIQUIDITY_MIN_ADV = 100_000


def _safe_call(func, default, *args, expected_type=None, name=None, **kwargs):
    label = name or getattr(func, "__name__", "unknown")
    try:
        result = func(*args, **kwargs)
        if expected_type is not None and not isinstance(result, expected_type):
            print(f"[FullScan] ⚠️ {label}: expected {expected_type.__name__}, got {type(result).__name__}")
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


def _check_liquidity_gate(candidate: dict) -> dict:
    reasons = []
    price = _safe_float(candidate.get('price', 0))
    spread = candidate.get('spread_pct')
    adv = candidate.get('average_daily_volume')

    if price < LIQUIDITY_MIN_PRICE:
        reasons.append(f"PRICE_TOO_LOW ({price:.2f})")

    if spread is None:
        reasons.append("SPREAD_UNKNOWN")
    else:
        try:
            spread_val = float(spread)
            if spread_val > LIQUIDITY_MAX_SPREAD_PCT:
                reasons.append(f"SPREAD_TOO_WIDE ({spread_val:.2f}%)")
        except (TypeError, ValueError):
            reasons.append("SPREAD_INVALID")

    if adv is not None:
        try:
            adv_val = int(adv)
            if adv_val > 0 and adv_val < LIQUIDITY_MIN_ADV:
                reasons.append(f"ADV_TOO_LOW ({adv_val:,})")
        except (TypeError, ValueError):
            pass

    return {"passed": len(reasons) == 0, "reasons": reasons}


def _check_data_completeness(candidate: dict) -> dict:
    """V5.0.5.1: uses pm_volume_status to distinguish UNAVAILABLE."""
    missing = []

    price = candidate.get('price')
    if price is None or _safe_float(price) <= 0:
        missing.append("מחיר")

    if candidate.get('gap_pct') is None:
        missing.append("גאפ")

    # PM Volume — only UNAVAILABLE is a hard miss
    pm_vol_status = candidate.get('pm_volume_status', 'UNAVAILABLE')
    if pm_vol_status == "UNAVAILABLE":
        missing.append("נפח PM")

    pm_high = candidate.get('pm_high')
    if pm_high is None or _safe_float(pm_high) <= 0:
        missing.append("PM High")

    pm_vwap = candidate.get('pm_vwap')
    if pm_vwap is None or _safe_float(pm_vwap) <= 0:
        missing.append("VWAP")

    cat_type = candidate.get('catalyst_type')
    if cat_type in (None, "UNAVAILABLE", ""):
        missing.append("קטליזטור")

    sec_level = candidate.get('sec_risk_level')
    if sec_level in (None, "UNAVAILABLE", ""):
        missing.append("SEC Risk")

    # If pm_volume_status is VOLUME_UNAVAILABLE → soft signal (WATCH)
    pm_vol_soft_watch = (pm_vol_status == "VOLUME_UNAVAILABLE")

    if len(missing) == 0 and not pm_vol_soft_watch:
        status = "ACTIONABLE"
    elif len(missing) <= 2:
        status = "WATCH"
    else:
        status = "NO_TRADE"

    return {
        "complete": len(missing) == 0 and not pm_vol_soft_watch,
        "missing": missing,
        "status": status,
        "pm_volume_soft_flag": pm_vol_soft_watch,
    }


def full_scan_v34(candidates: List[dict], manual: bool = False) -> List[dict]:
    if not candidates:
        return []

    total_to_analyze = len(candidates)
    print(f"[FullScan] Analyzing ALL {total_to_analyze} strict candidates...")

    corp_action_rejects = 0
    liquidity_rejects = 0
    passed_gates = 0
    scored = []

    for idx, c in enumerate(candidates):
        ticker = c.get('ticker', 'UNKNOWN')
        print(f"[FullScan] {idx+1}/{total_to_analyze} {ticker}")

        analysis = {}

        # GATE 1: Corporate Action
        corp_action = _safe_call(check_corporate_action, {}, ticker, expected_type=dict, name=f"corp_action:{ticker}")
        c['corporate_action'] = corp_action.get('corporate_action', False)
        c['corporate_action_type'] = corp_action.get('corporate_action_type')
        c['halt_flag'] = corp_action.get('halt_flag', False)

        if corp_action.get('corporate_action'):
            corp_action_rejects += 1
            print(f"[FullScan] ❌ {ticker} | Corporate Action: TRUE | Type: {corp_action.get('corporate_action_type')} | Decision: NO_TRADE")
            c['trade_type'] = 'NO_TRADE'
            c['plan_valid'] = False
            c['plan_error'] = f"CORPORATE_ACTION: {corp_action.get('reason')}"
            c['data_status'] = 'NO_TRADE'
            c['composite_score'] = None
            c['score_status'] = 'REJECTED_GATE'
            c['data_completeness'] = {"complete": False, "missing": ["CORPORATE_ACTION"], "status": "NO_TRADE"}
            c['analysis'] = analysis
            scored.append(c)
            continue

        # GATE 2: Liquidity
        liquidity = _check_liquidity_gate(c)
        c['liquidity_gate'] = liquidity

        if not liquidity.get('passed'):
            liquidity_rejects += 1
            print(f"[FullScan] ❌ {ticker} | Liquidity: FAIL | Reasons: {', '.join(liquidity.get('reasons', []))} | Decision: NO_TRADE")
            c['trade_type'] = 'NO_TRADE'
            c['plan_valid'] = False
            c['plan_error'] = f"LIQUIDITY: {', '.join(liquidity.get('reasons', []))}"
            c['data_status'] = 'NO_TRADE'
            c['composite_score'] = None
            c['score_status'] = 'REJECTED_GATE'
            c['data_completeness'] = {"complete": False, "missing": liquidity.get('reasons', []), "status": "NO_TRADE"}
            c['analysis'] = analysis
            scored.append(c)
            continue

        passed_gates += 1

        # PM DATA — FIX A
        pm_data = _safe_call(get_premarket_minute_data, {}, ticker, expected_type=dict, name=f"pm:{ticker}")

        pm_bars_received = 0
        pm_source = "none"

        if pm_data and pm_data.get('error') is None:
            pm_bars_received = int(pm_data.get('pm_bars_count', 0) or 0)
            pm_source = pm_data.get('source', 'unknown')

        if pm_bars_received > 0:
            c['pm_high'] = pm_data.get('pm_high')
            c['pm_low'] = pm_data.get('pm_low')
            c['pm_vwap'] = pm_data.get('pm_vwap')
            c['pm_volume'] = int(pm_data.get('pm_volume', 0) or 0)
            c['pm_bars'] = pm_bars_received
            c['pm_data_quality'] = pm_data.get('pm_data_quality', 'LOW_DATA')
            c['pm_source'] = pm_source
            c['pm_dist_signed'] = (
                ((_safe_float(c['price']) - _safe_float(c['pm_high'])) / _safe_float(c['pm_high'])) * 100.0
                if c['pm_high'] and _safe_float(c['pm_high']) > 0 else None
            )

            # FIX A: yfinance reports 0 volume → VOLUME_UNAVAILABLE (not ZERO)
            if c['pm_volume'] == 0:
                if pm_source == 'yfinance':
                    c['pm_volume_status'] = "VOLUME_UNAVAILABLE"
                    c['pm_data_quality'] = "PARTIAL"
                else:
                    c['pm_volume_status'] = "ZERO"
            else:
                c['pm_volume_status'] = "OK"
        else:
            c['pm_high'] = None
            c['pm_low'] = None
            c['pm_vwap'] = None
            c['pm_volume'] = 0
            c['pm_bars'] = 0
            c['pm_data_quality'] = 'UNAVAILABLE'
            c['pm_source'] = pm_source
            c['pm_dist_signed'] = None
            c['pm_volume_status'] = "UNAVAILABLE"

        analysis['pm_data_quality'] = c['pm_data_quality']
        analysis['pm_volume_status'] = c['pm_volume_status']
        analysis['pm_bars_received'] = pm_bars_received
        analysis['pm_source'] = pm_source

        # EARLY MOVE
        early_data = _safe_call(
            calculate_early_move_score,
            {"early_score": 0, "state": "UNKNOWN", "components": {}, "data_quality": "UNKNOWN"},
            ticker, c.get('pm_high'), c.get('pm_vwap'),
            expected_type=dict, name=f"early:{ticker}"
        )
        c['early_score'] = early_data.get('early_score', 0)
        c['early_state'] = early_data.get('state', 'UNKNOWN')
        c['early_components'] = early_data.get('components', {})
        c['early_data_quality'] = early_data.get('data_quality', 'UNKNOWN')
        analysis['early'] = early_data

        c['price'] = _safe_float(c.get('price', 0))
        c['gap_pct'] = _safe_float(c.get('gap_pct', 0))

        spread = c.get('spread_pct')
        if spread is None or spread == "UNAVAILABLE":
            c['spread_pct'] = None
        analysis['spread_pct'] = c['spread_pct']

        # RVOL
        rvol_data = _safe_call(calculate_rvol, {"rvol": None, "status": "UNAVAILABLE", "method": "DEFAULT"}, c, expected_type=dict, name=f"rvol:{ticker}")
        if not isinstance(rvol_data, dict):
            rvol_data = {"rvol": None, "status": "UNAVAILABLE", "method": "INVALID_RESPONSE"}
        c['rvol'] = rvol_data.get('rvol')
        c['rvol_status'] = rvol_data.get('status', 'UNAVAILABLE')
        c['rvol_method'] = rvol_data.get('method', 'UNAVAILABLE')
        analysis['rvol_data'] = rvol_data
        analysis['rvol'] = c['rvol']
        analysis['rvol_status'] = c['rvol_status']

        analysis['rs'] = _safe_call(get_relative_strength, None, ticker, expected_type=(float, int, type(None)), name=f"rs:{ticker}")
        c['rs'] = analysis['rs']

        analysis['news'] = _safe_call(fetch_news, [], ticker, expected_type=list, name=f"news:{ticker}")
        c['news'] = analysis['news']

        catalyst = _safe_call(classify_catalyst, {}, analysis['news'], expected_type=dict, name=f"catalyst:{ticker}")
        if isinstance(catalyst, dict):
            c['catalyst_type'] = catalyst.get('type', 'UNAVAILABLE')
            c['catalyst_score'] = catalyst.get('score', 0)
            c['catalyst_summary'] = catalyst.get('summary', '')
        else:
            c['catalyst_type'] = 'UNAVAILABLE'
            c['catalyst_score'] = 0
            c['catalyst_summary'] = ''
        analysis['catalyst'] = catalyst

        analysis['sentiment'] = _safe_call(get_stocktwits_sentiment, {}, ticker, expected_type=dict, name=f"sentiment:{ticker}")
        c['sentiment'] = analysis['sentiment']

        sec_risk = _safe_call(check_offering_risk, {"has_offering": False, "risk_level": "UNAVAILABLE"}, ticker, expected_type=dict, name=f"sec:{ticker}")
        analysis['sec_risk'] = sec_risk
        c['sec_risk'] = sec_risk
        c['sec_risk_level'] = sec_risk.get('risk_level', 'UNAVAILABLE')
        c['sec_has_offering'] = sec_risk.get('has_offering', False)

        float_data = _safe_call(get_float_and_short, {}, ticker, expected_type=dict, name=f"float:{ticker}")
        analysis['float_data'] = float_data
        c['float'] = float_data.get('float')
        c['short_interest'] = float_data.get('short_interest')
        c['short_ratio'] = float_data.get('short_ratio')
        analysis['float'] = c['float']
        analysis['short_interest'] = c['short_interest']

        personality = _safe_call(
            get_stock_personality,
            {"personality": "UNKNOWN", "failure_rate": 0, "sample_size": 0},
            ticker, c.get('gap_pct', 0), expected_type=dict, name=f"personality:{ticker}"
        )
        if isinstance(personality, dict):
            c['personality'] = personality.get('personality', 'UNKNOWN')
            c['personality_failure_rate'] = personality.get('failure_rate', 0)
        else:
            c['personality'] = 'UNKNOWN'
            c['personality_failure_rate'] = 0
            personality = {"personality": "UNKNOWN", "failure_rate": 0}
        analysis['personality'] = personality

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

        analysis['sympathy'] = _safe_call(find_sympathy_candidates, [], c, 3, expected_type=list, name=f"sympathy:{ticker}")
        c['sympathy'] = analysis['sympathy']

        plan = _safe_call(
            build_trade_plan, {}, c,
            ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT,
            expected_type=dict, name=f"tradeplan:{ticker}"
        )
        if plan:
            c.update(plan)
        else:
            c['plan_valid'] = False
            c['plan_error'] = 'Trade plan build failed'

        c['account_size'] = ACCOUNT_SIZE
        c['risk_pct'] = MAX_RISK_PER_TRADE_V31

        score = _safe_call(
            calculate_composite_score, None, c, analysis,
            expected_type=(int, float, type(None)), name=f"score:{ticker}"
        )
        if score is None:
            c['composite_score'] = None
            c['score_status'] = 'ERROR'
        else:
            c['composite_score'] = round(float(score), 1)
            c['score_status'] = 'OK'

        completeness = _check_data_completeness(c)
        c['data_completeness'] = completeness
        c['data_status'] = completeness['status']

        if completeness['status'] == 'NO_TRADE':
            c['trade_type'] = 'NO_TRADE'
        elif completeness['status'] == 'WATCH':
            c['trade_type'] = 'WATCH'

        c['diagnostics'] = {
            'pm': c.get('pm_data_quality'),
            'pm_volume_status': c.get('pm_volume_status'),
            'early': c.get('early_data_quality'),
            'rvol': c.get('rvol_status'),
            'catalyst': c.get('catalyst_type'),
            'sec': c.get('sec_risk_level'),
            'score': c.get('score_status'),
        }

        c['analysis'] = analysis
        scored.append(c)

    print()
    print("=" * 74)
    print("FULLSCAN GATE SUMMARY")
    print("=" * 74)
    print(f"  Total analyzed:                {total_to_analyze}")
    print(f"  Corporate Action rejects:      {corp_action_rejects}")
    print(f"  Liquidity rejects:             {liquidity_rejects}")
    print(f"  Passed Gates (Scored):         {passed_gates}")
    print(f"  Top 5 returned:                {min(5, len(scored))}")
    print("=" * 74)

    # Only include scored candidates (not gate-rejected) in Top 5
    valid_scored = [c for c in scored if isinstance(c.get('composite_score'), (int, float))]
    valid_scored.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

    return valid_scored[:5] if len(valid_scored) >= 5 else valid_scored