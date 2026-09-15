"""
DAYS-BOT V5.0.5.2.6 – Full Scan Engine
FIXES:
- V5.0.5.2.1: Float Hard Gate (<=20M); UNKNOWN → WATCH (not Strict)
- V5.0.5.2.2: Reuse float from Discovery (avoids double fetch)
- V5.0.5.2.5: Tag-only gap fields (gap_sign, gap_bucket, is_extreme_gap)
- V5.0.5.2.6: Live Capture — save pm_bars_json (raw PM bars list)
"""
import json
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
from scanner.analyzers.corporate_action_analyzer import check_corporate_action
from scanner.vwap_engine import calculate_vwap
from scanner.early_move import calculate_early_move_score
from risk.trade_plan_v34 import build_trade_plan
from scanner.scoring_engine import calculate_composite_score
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT

ET = pytz.timezone("America/New_York")

LIQUIDITY_MAX_SPREAD_PCT = 8.0
LIQUIDITY_MIN_PRICE = 1.0

FLOAT_MAX_HARD_GATE = 20_000_000


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
    hard_reasons = []
    soft_reasons = []

    price = _safe_float(candidate.get('price', 0))
    spread = candidate.get('spread_pct')

    if price < LIQUIDITY_MIN_PRICE:
        hard_reasons.append(f"PRICE_TOO_LOW ({price:.2f})")

    if spread is None:
        soft_reasons.append("SPREAD_UNKNOWN")
    else:
        try:
            spread_val = float(spread)
            if spread_val > LIQUIDITY_MAX_SPREAD_PCT:
                hard_reasons.append(f"SPREAD_TOO_WIDE ({spread_val:.2f}%)")
        except (TypeError, ValueError):
            soft_reasons.append("SPREAD_INVALID")

    return {
        "passed": len(hard_reasons) == 0,
        "hard_reasons": hard_reasons,
        "soft_reasons": soft_reasons,
    }


def _check_data_completeness(candidate: dict) -> dict:
    missing = []
    soft_flags = []

    price = candidate.get('price')
    if price is None or _safe_float(price) <= 0:
        missing.append("מחיר")

    if candidate.get('gap_pct') is None:
        missing.append("גאפ")

    pm_vol_status = candidate.get('pm_volume_status', 'UNAVAILABLE')
    if pm_vol_status == "UNAVAILABLE":
        missing.append("נפח PM (חסר מקור)")
    elif pm_vol_status == "VOLUME_UNAVAILABLE":
        soft_flags.append("נפח PM (yfinance לא מדווח)")

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
        missing.append("סיכון SEC")

    if len(missing) == 0 and len(soft_flags) == 0:
        status = "ACTIONABLE"
    elif len(missing) <= 2:
        status = "WATCH"
    else:
        status = "NO_TRADE"

    display_missing = missing + soft_flags if (missing or soft_flags) else ["ללא חוסרים"]

    return {
        "complete": len(missing) == 0 and len(soft_flags) == 0,
        "missing": display_missing,
        "hard_missing": missing,
        "soft_flags": soft_flags,
        "status": status,
    }


def _reject_candidate(c, scored, analysis, gate_name, trade_type, reason,
                      float_gate_reason=None):
    c['float_gate_passed'] = (gate_name != 'FLOAT_OVER_20M' and gate_name != 'FLOAT_UNAVAILABLE')
    c['float_gate_reason'] = float_gate_reason if float_gate_reason is not None else gate_name
    c['qualified'] = False
    c['trade_type'] = trade_type
    c['plan_valid'] = False
    c['plan_error'] = f'{gate_name}: {reason}'
    c['composite_score'] = None
    c['score_status'] = 'REJECTED_GATE'
    c['data_completeness'] = {
        'complete': False,
        'missing': [gate_name],
        'hard_missing': [gate_name] if trade_type == 'NO_TRADE' else [],
        'soft_flags': [gate_name] if trade_type == 'WATCH' else [],
        'status': trade_type,
    }
    c['data_status'] = trade_type
    c['diagnostics'] = {
        'pm': c.get('pm_data_quality'),
        'pm_volume_status': c.get('pm_volume_status'),
        'early': c.get('early_data_quality'),
        'rvol': c.get('rvol_status'),
        'catalyst': c.get('catalyst_type'),
        'sec': c.get('sec_risk_level'),
        'score': 'REJECTED_GATE',
        'float_gate': gate_name,
    }
    c['analysis'] = analysis
    scored.append(c)


def _classify_gap(gap_pct: float) -> dict:
    gap = _safe_float(gap_pct, 0.0)
    abs_gap = abs(gap)

    if gap > 0.05:
        sign = "POS"
    elif gap < -0.05:
        sign = "NEG"
    else:
        sign = "FLAT"

    if abs_gap < 3:
        bucket = "<3"
    elif abs_gap < 5:
        bucket = "3-5"
    elif abs_gap < 10:
        bucket = "5-10"
    elif abs_gap < 25:
        bucket = "10-25"
    elif abs_gap < 40:
        bucket = "25-40"
    else:
        bucket = "40+"

    return {
        "gap_sign": sign,
        "gap_bucket": bucket,
        "is_extreme_gap": abs_gap >= 40.0,
    }


def full_scan_v34(candidates: List[dict], manual: bool = False) -> List[dict]:
    if not candidates:
        return []

    total_to_analyze = len(candidates)
    print(f"[FullScan] Analyzing ALL {total_to_analyze} strict candidates...")

    corp_action_rejects = 0
    liquidity_rejects = 0
    float_rejects = 0
    float_cache_hits = 0
    float_live_fetches = 0
    passed_gates = 0
    scored = []

    for idx, c in enumerate(candidates):
        ticker = c.get('ticker', 'UNKNOWN')
        print(f"[FullScan] {idx+1}/{total_to_analyze} {ticker}")

        analysis = {}

        # V5.0.5.2.5 – gap tags
        gap_tags = _classify_gap(c.get('gap_pct', 0))
        c['gap_sign'] = gap_tags['gap_sign']
        c['gap_bucket'] = gap_tags['gap_bucket']
        c['is_extreme_gap'] = gap_tags['is_extreme_gap']

        # GATE 1: Corporate Action
        corp_action = _safe_call(check_corporate_action, {}, ticker,
                                 expected_type=dict, name=f"corp_action:{ticker}")
        c['corporate_action'] = corp_action.get('corporate_action', False)
        c['corporate_action_type'] = corp_action.get('corporate_action_type')
        c['halt_flag'] = corp_action.get('halt_flag', False)

        if corp_action.get('corporate_action'):
            corp_action_rejects += 1
            print(f"[FullScan] ❌ {ticker} | CorpAction: {corp_action.get('corporate_action_type')} | NO_TRADE")
            c.update({
                "trade_type": "NO_TRADE", "plan_valid": False,
                "plan_error": f"CORPORATE_ACTION: {corp_action.get('reason')}",
                "data_status": "NO_TRADE", "composite_score": None,
                "score_status": "REJECTED_GATE",
                "data_completeness": {"complete": False, "missing": ["CORPORATE_ACTION"], "status": "NO_TRADE"},
            })
            c['analysis'] = analysis
            scored.append(c)
            continue

        # GATE 2: Liquidity
        liquidity = _check_liquidity_gate(c)
        c['liquidity_gate'] = liquidity

        if not liquidity.get('passed'):
            liquidity_rejects += 1
            print(f"[FullScan] ❌ {ticker} | Liquidity: {', '.join(liquidity.get('hard_reasons', []))} | NO_TRADE")
            c.update({
                "trade_type": "NO_TRADE", "plan_valid": False,
                "plan_error": f"LIQUIDITY: {', '.join(liquidity.get('hard_reasons', []))}",
                "data_status": "NO_TRADE", "composite_score": None,
                "score_status": "REJECTED_GATE",
                "data_completeness": {"complete": False, "missing": liquidity.get('hard_reasons', []), "status": "NO_TRADE"},
            })
            c['analysis'] = analysis
            scored.append(c)
            continue

        if liquidity.get('soft_reasons'):
            c['liquidity_soft_flags'] = liquidity.get('soft_reasons')

        passed_gates += 1

        # PM DATA
        pm_data = _safe_call(get_premarket_minute_data, {}, ticker,
                             expected_type=dict, name=f"pm:{ticker}")

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

            # V5.0.5.2.6 – Live Capture: raw PM bars JSON
            c['pm_bars_json'] = json.dumps(
                pm_data.get('pm_bars_list', []),
                default=str,
            )

            if c['pm_volume'] == 0:
                if pm_source == 'yfinance':
                    c['pm_volume_status'] = "VOLUME_UNAVAILABLE"
                else:
                    c['pm_volume_status'] = "ZERO"
            else:
                c['pm_volume_status'] = "OK"
        else:
            c.update({
                "pm_high": None, "pm_low": None, "pm_vwap": None,
                "pm_volume": 0, "pm_bars": 0,
                "pm_bars_json": None,
                "pm_data_quality": "UNAVAILABLE", "pm_source": pm_source,
                "pm_dist_signed": None, "pm_volume_status": "UNAVAILABLE",
            })

        analysis['pm_data_quality'] = c['pm_data_quality']
        analysis['pm_volume_status'] = c['pm_volume_status']
        analysis['pm_bars_received'] = pm_bars_received
        analysis['pm_source'] = pm_source

        # Early Move
        early_data = _safe_call(calculate_early_move_score,
            {"early_score": 0, "state": "UNKNOWN", "components": {}, "data_quality": "UNKNOWN"},
            ticker, c.get('pm_high'), c.get('pm_vwap'),
            expected_type=dict, name=f"early:{ticker}")
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
        rvol_data = _safe_call(calculate_rvol,
            {"rvol": None, "status": "UNAVAILABLE", "method": "DEFAULT"},
            c, expected_type=dict, name=f"rvol:{ticker}")
        if not isinstance(rvol_data, dict):
            rvol_data = {"rvol": None, "status": "UNAVAILABLE", "method": "INVALID"}
        c['rvol'] = rvol_data.get('rvol')
        c['rvol_status'] = rvol_data.get('status', 'UNAVAILABLE')
        c['rvol_method'] = rvol_data.get('method', 'UNAVAILABLE')
        analysis['rvol_data'] = rvol_data
        analysis['rvol'] = c['rvol']

        analysis['rs'] = _safe_call(get_relative_strength, None, ticker,
            expected_type=(float, int, type(None)), name=f"rs:{ticker}")
        c['rs'] = analysis['rs']

        analysis['news'] = _safe_call(fetch_news, [], ticker,
                                      expected_type=list, name=f"news:{ticker}")
        c['news'] = analysis['news']

        catalyst = _safe_call(classify_catalyst, {}, analysis['news'],
                              expected_type=dict, name=f"catalyst:{ticker}")
        c['catalyst_type'] = catalyst.get('type', 'UNAVAILABLE') if isinstance(catalyst, dict) else 'UNAVAILABLE'
        c['catalyst_score'] = catalyst.get('score', 0) if isinstance(catalyst, dict) else 0
        c['catalyst_summary'] = catalyst.get('summary', '') if isinstance(catalyst, dict) else ''
        analysis['catalyst'] = catalyst

        analysis['sentiment'] = _safe_call(get_stocktwits_sentiment, {}, ticker,
                                           expected_type=dict, name=f"sentiment:{ticker}")
        c['sentiment'] = analysis['sentiment']

        sec_risk = _safe_call(check_offering_risk,
            {"has_offering": False, "risk_level": "UNAVAILABLE"},
            ticker, expected_type=dict, name=f"sec:{ticker}")
        c['sec_risk'] = sec_risk
        c['sec_risk_level'] = sec_risk.get('risk_level', 'UNAVAILABLE')
        c['sec_has_offering'] = sec_risk.get('has_offering', False)
        analysis['sec_risk'] = sec_risk

        # FLOAT: reuse from Discovery if injected
        float_from_discovery = c.get('float')
        float_source_from_discovery = c.get('float_source')

        if float_from_discovery is not None:
            float_cache_hits += 1
            analysis['float_data'] = {
                'float': float_from_discovery,
                'short_interest': c.get('short_interest'),
                'short_ratio': c.get('short_ratio'),
                'source': float_source_from_discovery or 'discovery_cache',
                'status': 'CACHED_FROM_DISCOVERY',
            }
            analysis['float'] = float_from_discovery
            analysis['short_interest'] = c.get('short_interest')
        else:
            float_live_fetches += 1
            float_data = _safe_call(get_float_and_short, {}, ticker,
                                    expected_type=dict, name=f"float:{ticker}")
            analysis['float_data'] = float_data
            c['float'] = float_data.get('float')
            c['short_interest'] = float_data.get('short_interest')
            c['short_ratio'] = float_data.get('short_ratio')
            c['float_source'] = float_data.get('source', 'fmp_or_yfinance')
            analysis['float'] = c['float']
            analysis['short_interest'] = c['short_interest']

        # FLOAT HARD GATE
        raw_float = c.get('float')
        float_num = None
        if raw_float is not None:
            try:
                float_num = float(raw_float)
            except (TypeError, ValueError):
                float_num = None

        if float_num is None:
            float_rejects += 1
            print(f"[FullScan] ⚠️ {ticker} | Float: FLOAT_UNAVAILABLE | WATCH (not Strict)")
            _reject_candidate(
                c, scored, analysis,
                gate_name='FLOAT_UNAVAILABLE',
                trade_type='WATCH',
                reason='FLOAT_UNAVAILABLE',
                float_gate_reason='FLOAT_UNAVAILABLE',
            )
            continue
        elif float_num > FLOAT_MAX_HARD_GATE:
            float_rejects += 1
            reason = f"FLOAT_OVER_20M ({float_num:,.0f})"
            print(f"[FullScan] ❌ {ticker} | Float: {reason} | NO_TRADE")
            _reject_candidate(
                c, scored, analysis,
                gate_name='FLOAT_OVER_20M',
                trade_type='NO_TRADE',
                reason=reason,
                float_gate_reason=reason,
            )
            continue
        else:
            c['float_gate_passed'] = True
            c['float_gate_reason'] = 'PASS'
            c['qualified'] = True
            analysis['float_gate'] = {'passed': True, 'reason': 'PASS'}

        personality = _safe_call(get_stock_personality,
            {"personality": "UNKNOWN", "failure_rate": 0, "sample_size": 0},
            ticker, c.get('gap_pct', 0), expected_type=dict, name=f"personality:{ticker}")
        c['personality'] = personality.get('personality', 'UNKNOWN') if isinstance(personality, dict) else 'UNKNOWN'
        c['personality_failure_rate'] = personality.get('failure_rate', 0) if isinstance(personality, dict) else 0
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
            vwap_data = _safe_call(calculate_vwap, {}, ticker, 30,
                                   expected_type=dict, name=f"vwap:{ticker}")
        analysis['vwap'] = vwap_data
        c['vwap_data'] = vwap_data
        c['vwap'] = vwap_data.get('vwap', 0) if vwap_data else None

        analysis['sympathy'] = _safe_call(find_sympathy_candidates, [], c, 3,
                                          expected_type=list, name=f"sympathy:{ticker}")
        c['sympathy'] = analysis['sympathy']

        plan = _safe_call(build_trade_plan, {}, c, ACCOUNT_SIZE,
                          MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT,
                          expected_type=dict, name=f"tradeplan:{ticker}")
        if plan:
            c.update(plan)
        else:
            c['plan_valid'] = False
            c['plan_error'] = 'Trade plan build failed'

        c['account_size'] = ACCOUNT_SIZE
        c['risk_pct'] = MAX_RISK_PER_TRADE_V31

        score = _safe_call(calculate_composite_score, None, c, analysis,
            expected_type=(int, float, type(None)), name=f"score:{ticker}")
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
            'score': c.ge