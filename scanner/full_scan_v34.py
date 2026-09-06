"""
DAYS-BOT V4.2 – Full Scan Engine
Takes discovery candidates, runs deep analysis, returns Top 5
"""
from datetime import datetime
from typing import List, Dict, Any
import pytz
import yfinance as yf

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
    """Safely call a function, return default on exception."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[FullScan] Call error: {e}")
        return default


def full_scan_v34(candidates: List[dict], manual: bool = False) -> List[dict]:
    """
    Analyze candidates deeply, return Top 5 with trade plans.
    """
    if not candidates:
        return []

    print(f"[FullScan] Analyzing {len(candidates)} candidates...")
    enriched = []

    for idx, c in enumerate(candidates[:25]):
        ticker = c.get('ticker', 'UNKNOWN')
        print(f"[FullScan] {idx+1}/{min(len(candidates), 25)} {ticker}")

        analysis = {}

        # Float & Short (with safe fallback)
        analysis['float_data'] = _safe_call(get_float_and_short, {}, ticker)
        analysis['float'] = analysis['float_data'].get('float')
        analysis['short_interest'] = analysis['float_data'].get('short_interest')

        # RVOL & RS
        analysis['rvol'] = _safe_call(calculate_rvol, None, c)
        analysis['rs'] = _safe_call(get_relative_strength, None, ticker)

        # News & Catalyst
        analysis['news'] = _safe_call(fetch_news, [], ticker)
        analysis['catalyst'] = _safe_call(classify_catalyst, {}, analysis['news'])

        # Sentiment
        analysis['sentiment'] = _safe_call(get_stocktwits_sentiment, {}, ticker)

        # SEC Risk
        analysis['sec_risk'] = _safe_call(check_offering_risk, {}, ticker)

        # Personality
        analysis['personality'] = _safe_call(get_stock_personality, {}, ticker, c.get('gap_pct', 0))

        # VWAP – FIXED: properly handle lookback_minutes
        vwap_data = _safe_call(calculate_vwap, {}, ticker, 30)
        if not vwap_data:
            vwap_data = _safe_call(calculate_pm_vwap_from_candidate, {}, c)
        analysis['vwap'] = vwap_data

        # Sympathy
        analysis['sympathy'] = _safe_call(find_sympathy_candidates, [], c, 3)

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

        c['account_size'] = ACCOUNT_SIZE
        c['risk_pct'] = MAX_RISK_PER_TRADE_V31

        # Composite Score
        c['composite_score'] = _safe_call(calculate_composite_score, 0, c, analysis)

        # Store analysis
        c['analysis'] = analysis
        enriched.append(c)

    # Sort by composite score
    enriched.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

    # Return Top 5 (or fewer)
    top5 = enriched[:5] if len(enriched) >= 5 else enriched

    print(f"[FullScan] Returning {len(top5)} candidates")
    return top5
