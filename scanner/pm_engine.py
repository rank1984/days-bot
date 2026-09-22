"""
DAYS-BOT V5.0.6 – Full Scan Engine
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
            print(f"[FullScan] WARN {label}: wrong type")
            return default
        return result
    except Exception as e:
        print(f"[FullScan] ERR {label}: {type(e).__name__}: {e}")
        return default


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _check_liquidity_gate(candidate):
    hard = []
    soft = []
    price = _safe_float(candidate.get('price', 0))
    spread = candidate.get('spread_pct')

    if price < LIQUIDITY_MIN_PRICE:
        hard.append(f"PRICE_TOO_LOW ({price:.2f})")

    if spread is None:
        soft.append("SPREAD_UNKNOWN")
    else:
        try:
            sv = float(spread)
            if sv > LIQUIDITY_MAX_SPREAD_PCT:
                hard.append(f"SPREAD_TOO_WIDE ({sv:.2f}%)")
        except (TypeError, ValueError):
            soft.append("SPREAD_INVALID")

    return {"passed": len(hard) == 0, "hard_reasons": hard, "soft_reasons": soft}


def _check_data_completeness(candidate):
    missing = []
    soft_flags = []

    price = candidate.get('price')
    if price is None or _safe_float(price) <= 0:
        missing.append("price")
    if candidate.get('gap_pct') is None:
        missing.append("gap")

    pm_vol_status = candidate.get('pm_volume_status', 'UNAVAILABLE')
    if pm_vol_status == "UNAVAILABLE":
        missing.append("pm_volume_source")
    elif pm_vol_status == "VOLUME_UNAVAILABLE":
        soft_flags.append("pm_volume_yfinance")

    pm_high = candidate.get('pm_high')
    if pm_high is None or _safe_float(pm_high) <= 0:
        missing.append("PM High")

    pm_vwap = candidate.get('pm_vwap')
    if pm_vwap is None or _safe_float(pm_vwap) <= 0:
        missing.append("VWAP")

    cat_type = candidate.get('catalyst_type')
    if cat_type in (None, "UNAVAILABLE", ""):
        missing.append("catalyst")

    sec_level = candidate.get('sec_risk_level')
    if sec_level in (None, "UNAVAILABLE", ""):
        missing.append("sec")

    if len(missing) == 0 and len(soft_flags) == 0:
        status = "ACTIONABLE"
    elif len(missing) <= 2:
        status = "WATCH"
    else:
        status = "NO_TRADE"

    display_missing = missing + soft_flags if (missing or soft_flags) else ["ok"]

    return {
        "complete": len(missing) == 0 and len(soft_flags) == 0,
        "missing": display_missing,
        "hard_missing": missing,
        "soft_flags": soft_flags,
        "status": status,
    }


def _reject_candidate(c, scored, analysis, gate_name, trade_type, reason,
                      float_gate_reason=None):
    c['float_gate_passed'] = (gate_name not in ('FLOAT_OVER_20M', 'FLOAT_UNAVAILABLE'))
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
        'score': 'REJECTED_GATE',
        'float_gate': gate_name,
    }
    c['analysis'] = analysis
    scored.append(c)


def _classify_gap(gap_pct):
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


def full_scan_v34(candidates, manual=False):
    if not candidates:
        return []

    total = len(candidates)
    print(f"[FullScan] Analyzing ALL {total} strict candidates...")

    corp_rej = 0
    liq_rej = 0
    float_rej = 0
    float_cache = 0
    float_live = 0
    passed_gates = 0
    scored = []

    for idx, c in enumerate(candidates):
        ticker = c.get('ticker', 'UNKNOWN')
        print(f"[FullScan] {idx+1}/{total} {ticker}")

        analysis = {}

        gap_tags = _classify_gap(c.get('gap_pct', 0))
        c['gap_sign'] = gap_tags['gap_sign']
        c['gap_bucket'] = gap_tags['gap_bucket']
        c['is_extreme_gap'] = gap_tags['is_extreme_gap']

        # GATE 1: Corporate Action
        ca = _safe_call(check_corporate_action, {}, ticker,
                        expected_type=dict, name=f"corp:{ticker}")
        c['corporate_action'] = ca.get('corporate_action', False)
        c['corporate_action_type'] = ca.get('corporate_action_type')
        c['halt_flag'] = ca.get('halt_flag', False)

        if ca.get('corporate_action'):
            corp_rej += 1
            print(f"[FullScan] REJECT {ticker} | CorpAction")
            c.update({
                "trade_type": "NO_TRADE", "plan_valid": False,
                "plan_error": f"CORP_ACTION",
                "data_status": "NO_TRADE", "composite_score": None,
                "score_status": "REJECTED_GATE",
            })
            c['analysis'] = analysis
            scored.append(c)
            continue

        # GATE 2: Liquidity
        liq = _check_liquidity_gate(c)
        c['liquidity_gate'] = liq

        if not liq.get('passed'):
            liq_rej += 1
            print(f"[FullScan] REJECT {ticker} | Liquidity")
            c.update({
                "trade_type": "NO_TRADE", "plan_valid": False,
                "plan_error": f"LIQUIDITY",
                "data_status": "NO_TRADE", "composite_score": None,
                "score_status": "REJECTED_GATE",
            })
            c['analysis'] = analysis
            scored.append(c)
            continue

        if liq.get('soft_reasons'):
            c['liquidity_soft_flags'] = liq.get('soft_reasons')

        passed_gates += 1

        # PM DATA
        pm_data = _safe_call(get_premarket_minute_data, {}, ticker,
                             expected_type=dict, name=f"pm:{ticker}")

        pm_bars = 0
        pm_source = "none"
        if pm_data and pm_data.get('error') is None:
            pm_bars = int(pm_data.get('pm_bars_count', 0) or 0)
            pm_source = pm_data.get('source', 'unknown')

        if pm_bars > 0:
            c['pm_high'] = pm_data.get('pm_high')
            c['pm_low'] = pm_data.get('pm_low')
            c['pm_vwap'] = pm_data.get('pm_vwap')

            _raw = pm_data.get('pm_volume')
            if _raw is not None:
                try:
                    c['pm_volume'] = int(_raw)
                except (TypeError, ValueError):
                    c['pm_volume'] = None
            else:
                c['pm_volume'] = None

            c['pm_bars'] = pm_bars
            c['pm_data_quality'] = pm_data.get('pm_data_quality', 'LOW_DATA')
            c['pm_source'] = pm_source
            c['pm_volume_status'] = pm_data.get('pm_volume_status', 'UNAVAILABLE')
            c['pm_vwap_status'] = pm_data.get('pm_vwap_status', 'UNAVAILABLE')

            if c['pm_volume_status'] == 'UNAVAILABLE':
                if pm_source == 'yfinance' and c['pm_volume'] in (None, 0):
                    c['pm_volume_status'] = 'VOLUME_UNAVAILABLE'

            c['pm_dist_signed'] = (
                ((_safe_float(c['price']) - _safe_float(c['pm_high'])) / _safe_float(c['pm_high'])) * 100.0
                if c['pm_high'] and _safe_float(c['pm_high']) > 0 else None
            )

            c['pm_bars_json'] = json.dumps(
                pm_data.get('pm_bars_list', []),
                default=str,
            )
        else:
            c.update({
                "pm_high": None, "pm_low": None, "pm_vwap": None,
                "pm_volume": None, "pm_bars": 0,
                "pm_bars_json": None,
                "pm_data_quality": "UNAVAILABLE", "pm_source": pm_source,
                "pm_dist_signed": None,
                "pm_volume_status": "UNAVAILABLE",
                "pm_vwap_status": "UNAVAILABLE",
            })

        analysis['pm_data_quality'] = c['pm_data_quality']
        analysis['pm_volume_status'] = c['pm_volume_status']

        # EARLY
        early = _safe_call(calculate_early_move_score,
            {"early_score": 0, "state": "UNKNOWN", "components": {}, "data_quality": "UNKNOWN"},
            ticker, c.get('pm_high'), c.get('pm_vwap'),
            expected_type=dict, name=f"early:{ticker}")
        c['early_score'] = early.get('early_score', 0)
        c['early_state'] = early.get('state', 'UNKNOWN')
        c['early_components'] = early.get('components', {})
        c['early_data_quality'] = early.get('data_quality', 'UNKNOWN')
        analysis['early'] = early

        c['price'] = _safe_float(c.get('price', 0))
        c['gap_pct'] = _safe_float(c.get('gap_pct', 0))

        spread = c.get('spread_pct')
        if spread is None or spread == "UNAVAILABLE":
            c['spread_pct'] = None
        analysis['spread_pct'] = c['spread_pct']

        # RVOL
        rvol = _safe_call(calculate_rvol,
            {"rvol": None, "status": "UNAVAILABLE", "method": "DEFAULT"},
            c, expected_type=dict, name=f"rvol:{ticker}")
        if not isinstance(rvol, dict):
            rvol = {"rvol": None, "status": "UNAVAILABLE", "method": "INVALID"}
        c['rvol'] = rvol.get('rvol')
        c['rvol_status'] = rvol.get('status', 'UNAVAILABLE')
        c['rvol_method'] = rvol.get('method', 'UNAVAILABLE')
        analysis['rvol_data'] = rvol

        analysis['rs'] = _safe_call(get_relative_strength, None, ticker,
            expected_type=(float, int, type(None)), name=f"rs:{ticker}")
        c['rs'] = analysis['rs']

        analysis['news'] = _safe_call(fetch_news, [], ticker,
                                      expected_type=list, name=f"news:{ticker}")
        c['news'] = analysis['news']

        cat = _safe_call(classify_catalyst, {}, analysis['news'],
                          expected_type=dict, name=f"catalyst:{ticker}")
        c['catalyst_type'] = cat.get('type', 'UNAVAILABLE') if isinstance(cat, dict) else 'UNAVAILABLE'
        c['catalyst_score'] = cat.get('score', 0) if isinstance(cat, dict) else 0
        c['catalyst_summary'] = cat.get('summary', '') if isinstance(cat, dict) else ''
        analysis['catalyst'] = cat

        analysis['sentiment'] = _safe_call(get_stocktwits_sentiment, {}, ticker,
                                           expected_type=dict, name=f"sentiment:{ticker}")
        c['sentiment'] = analysis['sentiment']

        sec = _safe_call(check_offering_risk,
            {"has_offering": False, "risk_level": "UNAVAILABLE"},
            ticker, expected_type=dict, name=f"sec:{ticker}")
        c['sec_risk'] = sec
        c['sec_risk_level'] = sec.get('risk_level', 'UNAVAILABLE')
        c['sec_has_offering'] = sec.get('has_offering', False)
        analysis['sec_risk'] = sec

        # FLOAT
        float_disc = c.get('float')
        float_src = c.get('float_source')

        if float_disc is not None:
            float_cache += 1
            analysis['float_data'] = {
                'float': float_disc,
                'source': float_src or 'discovery_cache',
                'status': 'CACHED',
            }
            analysis['float'] = float_disc
        else:
            float_live += 1
            fd = _safe_call(get_float_and_short, {}, ticker,
                            expected_type=dict, name=f"float:{ticker}")
            analysis['float_data'] = fd
            c['float'] = fd.get('float')
            c['short_interest'] = fd.get('short_interest')
            c['short_ratio'] = fd.get('short_ratio')
            c['float_source'] = fd.get('source', 'unknown')
            analysis['float'] = c['float']

        # FLOAT GATE
        raw_float = c.get('float')
        float_num = None
        if raw_float is not None:
            try:
                float_num = float(raw_float)
            except (TypeError, ValueError):
                float_num = None

        if float_num is None:
            float_rej += 1
            print(f"[FullScan] WATCH {ticker} | FLOAT_UNAVAILABLE")
            _reject_candidate(c, scored, analysis,
                gate_name='FLOAT_UNAVAILABLE', trade_type='WATCH',
                reason='FLOAT_UNAVAILABLE')
            continue
        elif float_num > FLOAT_MAX_HARD_GATE:
            float_rej += 1
            reason = f"FLOAT_OVER_20M ({float_num:,.0f})"
            print(f"[FullScan] REJECT {ticker} | {reason}")
            _reject_candidate(c, scored, analysis,
                gate_name='FLOAT_OVER_20M', trade_type='NO_TRADE',
                reason=reason)
            continue
        else:
            c['float_gate_passed'] = True
            c['float_gate_reason'] = 'PASS'
            analysis['float_gate'] = {'passed': True, 'reason': 'PASS'}

        # Personality
        pers = _safe_call(get_stock_personality,
            {"personality": "UNKNOWN", "failure_rate": 0, "sample_size": 0},
            ticker, c.get('gap_pct', 0), expected_type=dict, name=f"pers:{ticker}")
        c['personality'] = pers.get('personality', 'UNKNOWN') if isinstance(pers, dict) else 'UNKNOWN'
        c['personality_failure_rate'] = pers.get('failure_rate', 0) if isinstance(pers, dict) else 0
        analysis['personality'] = pers

        # VWAP
        if c.get('pm_high') is not None and _safe_float(c['pm_high']) > 0:
            vwap_data = {
                "vwap": c.get('pm_vwap'),
                "vwap_high": c.get('pm_high'),
                "vwap_low": c.get('pm_low'),
                "source": "premarket"
            }
        else:
            vwap_data = _safe_call(calculate_vwap, {}, ticker, 30,
                                   expected_type=dict, name=f"vwap:{ticker}")
        analysis['vwap'] = vwap_data
        c['vwap_data'] = vwap_data
        c['vwap'] = vwap_data.get('vwap', 0) if vwap_data else None

        # Sympathy
        analysis['sympathy'] = _safe_call(find_sympathy_candidates, [], c, 3,
                                          expected_type=list, name=f"symp:{ticker}")
        c['sympathy'] = analysis['sympathy']

        # ================================================================
        # V5.0.6 — DATA QUALITY GATE (BEFORE Trade Plan)
        # ================================================================
        completeness = _check_data_completeness(c)
        c['data_completeness'] = completeness
        c['data_status'] = completeness['status']

        if completeness['status'] == 'NO_TRADE':
            c['trade_type'] = 'NO_TRADE'
            c['qualified'] = False
            c['plan_valid'] = False
            c['plan_error'] = "DATA_QUALITY_GATE: NO_TRADE"
            c['composite_score'] = None
            c['score_status'] = 'BLOCKED_DATA_QUALITY'
            c['diagnostics'] = {
                'pm': c.get('pm_data_quality'),
                'pm_volume_status': c.get('pm_volume_status'),
                'pm_vwap_status': c.get('pm_vwap_status'),
                'score': 'BLOCKED_DATA_QUALITY',
            }
            c['analysis'] = analysis
            scored.append(c)
            continue

        if completeness['status'] == 'WATCH':
            c['trade_type'] = 'WATCH'
            c['qualified'] = False
            c['plan_valid'] = False
            c['plan_error'] = "DATA_QUALITY_GATE: WATCH"
            c['composite_score'] = None
            c['score_status'] = 'BLOCKED_DATA_QUALITY'
            c['diagnostics'] = {
                'pm': c.get('pm_data_quality'),
                'pm_volume_status': c.get('pm_volume_status'),
                'pm_vwap_status': c.get('pm_vwap_status'),
                'score': 'BLOCKED_DATA_QUALITY',
            }
            c['analysis'] = analysis
            scored.append(c)
            continue

        # ================================================================
        # ACTIONABLE — Trade Plan + Score
        # ================================================================
        c['qualified'] = True

        plan = _safe_call(build_trade_plan, {}, c, ACCOUNT_SIZE,
                          MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT,
                          expected_type=dict, name=f"plan:{ticker}")
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

        c['diagnostics'] = {
            'pm': c.get('pm_data_quality'),
            'pm_volume_status': c.get('pm_volume_status'),
            'pm_vwap_status': c.get('pm_vwap_status'),
            'score': c.get('score_status'),
        }

        c['analysis'] = analysis
        scored.append(c)

    print()
    print("=" * 74)
    print("FULLSCAN GATE SUMMARY")
    print("=" * 74)
    print(f"  Total analyzed:                {total}")
    print(f"  Corporate Action rejects:      {corp_rej}")
    print(f"  Liquidity rejects:             {liq_rej}")
    print(f"  Float rejects (incl. UNKNOWN): {float_rej}")
    print(f"  Float cache hits (Discovery):  {float_cache}")
    print(f"  Float live fetches:            {float_live}")
    print(f"  Passed Gates (Scored):         {passed_gates - float_rej}")
    valid_scored = [x for x in scored if isinstance(x.get('composite_score'), (int, float))]
    print(f"  Top 5 returned:                {min(5, len(valid_scored))}")
    print("=" * 74)

    gate_summary = {
        "corp_action_rejects": corp_rej,
        "liquidity_rejects": liq_rej,
        "float_rejects": float_rej,
        "float_cache_hits": float_cache,
        "float_live_fetches": float_live,
    }
    for x in scored:
        x['_gate_summary'] = gate_summary

    valid_scored.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

    return valid_scored[:5] if len(valid_scored) >= 5 else valid_scored