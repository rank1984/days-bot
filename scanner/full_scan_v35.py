"""
V3.5 Research Engine – Always returns Top 5 Research Candidates + Trade Candidates
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
from scanner.scoring_engine import calculate_scores
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT


def full_scan_v35(candidates, manual=False) -> dict:
    """
    Returns: {
        "top5_research": [...],   # Always 5
        "trade_candidates": [...], # 0-5
        "filter_funnel": {...},
        "near_misses": [...]
    }
    """
    if not candidates:
        return {"top5_research": [], "trade_candidates": [], "filter_funnel": {}, "near_misses": []}

    enriched = []
    filter_stats = {
        "total": len(candidates),
        "price_ok": 0,
        "gap_ok": 0,
        "pm_ok": 0,
        "rvol_ok": 0,
        "float_ok": 0,
        "sec_ok": 0,
        "personality_ok": 0,
        "trade_candidates": 0,
    }

    for c in candidates[:25]:
        analysis = {}

        # Basic checks
        filter_stats["price_ok"] += 1
        if c.get('gap_pct', 0) >= 10:
            filter_stats["gap_ok"] += 1

        # Float & Short
        analysis['float_data'] = get_float_and_short(c['ticker'])
        analysis['float'] = analysis['float_data'].get('float')
        analysis['short_interest'] = analysis['float_data'].get('short_interest')
        if analysis['float'] and analysis['float'] < 50_000_000:
            filter_stats["float_ok"] += 1

        # RVOL
        analysis['rvol'] = calculate_rvol(c)
        if analysis['rvol'] and analysis['rvol'] >= 3:
            filter_stats["rvol_ok"] += 1

        # News & Catalyst
        analysis['news'] = fetch_news(c['ticker'])
        analysis['catalyst'] = classify_catalyst(analysis['news'])

        # Sentiment
        analysis['sentiment'] = get_stocktwits_sentiment(c['ticker'])

        # SEC Risk
        analysis['sec_risk'] = check_offering_risk(c['ticker'])
        if analysis['sec_risk'].get('risk_level') != "HIGH":
            filter_stats["sec_ok"] += 1

        # Personality
        analysis['personality'] = get_stock_personality(c['ticker'], c.get('gap_pct', 0))
        if analysis['personality'].get('personality') != "GAP_AND_CRAP":
            filter_stats["personality_ok"] += 1

        # VWAP
        vwap_data = calculate_vwap(c['ticker'], lookback_minutes=30)
        if not vwap_data:
            vwap_data = calculate_pm_vwap_from_candidate(c)
        analysis['vwap'] = vwap_data

        # Sympathy
        analysis['sympathy'] = find_sympathy_candidates(c, max_candidates=3)

        # Calculate scores
        scores = calculate_scores(c, analysis)
        c.update(scores)
        c['analysis'] = analysis
        enriched.append(c)

    # Sort by trade_score
    enriched.sort(key=lambda x: x.get('trade_score', 0), reverse=True)

    # Top 5 Research (always)
    top5_research = enriched[:5] if len(enriched) >= 5 else enriched

    # Trade Candidates (only those who passed all gates)
    trade_candidates = [c for c in enriched if c.get('is_trade_candidate', False)]

    # Apply trade plans to trade candidates
    for c in trade_candidates[:5]:
        plan = build_trade_plan(c, ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, MAX_POSITION_VALUE_PCT)
        c.update(plan)

    # Near misses: top 3 that didn't make trade cut
    near_misses = [c for c in enriched[:10] if not c.get('is_trade_candidate', False)][:3]

    # Update filter stats
    filter_stats["trade_candidates"] = len(trade_candidates)

    return {
        "top5_research": top5_research,
        "trade_candidates": trade_candidates[:5],
        "filter_funnel": filter_stats,
        "near_misses": near_misses,
    }
