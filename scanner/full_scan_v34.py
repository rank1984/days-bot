"""
V3.4 Full Scan – Analyzes candidates, computes composite score, returns Top 5
Always returns at least some candidates (fallback)
"""
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


def full_scan_v34(candidates, manual=False) -> list:
    """Accepts premarket candidates, enriches with analysis, returns Top 5"""
    if not candidates:
        return []

    enriched = []
    for c in candidates[:25]:
        analysis = {}

        # Float & Short
        analysis['float_data'] = get_float_and_short(c['ticker'])
        analysis['float'] = analysis['float_data'].get('float')
        analysis['short_interest'] = analysis['float_data'].get('short_interest')

        # RVOL & RS
        analysis['rvol'] = calculate_rvol(c)
        analysis['rs'] = get_relative_strength(c['ticker'])

        # News & Catalyst
        analysis['news'] = fetch_news(c['ticker'])
        analysis['catalyst'] = classify_catalyst(analysis['news'])

        # Sentiment
        analysis['sentiment'] = get_stocktwits_sentiment(c['ticker'])

        # SEC Risk
        analysis['sec_risk'] = check_offering_risk(c['ticker'])

        # Personality
        analysis['personality'] = get_stock_personality(c['ticker'], c.get('gap_pct', 0))

        # VWAP
        vwap_data = calculate_vwap(c['ticker'], lookback_minutes=30)
        if not vwap_data:
            vwap_data = calculate_pm_vwap_from_candidate(c)
        analysis['vwap'] = vwap_data

        # Sympathy
        analysis['sympathy'] = find_sympathy_candidates(c, max_candidates=3)

        # Composite Score
        c['composite_score'] = calculate_composite_score(c, analysis)

        c['analysis'] = analysis
        enriched.append(c)

    # Sort by composite score
    enriched.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

    # Take Top 5, but if fewer, take all
    top5 = enriched[:5] if len(enriched) >= 5 else enriched

    # Always return at least something (fallback)
    return top5 if top5 else candidates[:5]