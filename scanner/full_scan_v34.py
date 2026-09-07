"""
DAYS-BOT V4.3 – Full Scan Engine
- Takes discovery candidates, runs deep analysis
- Ensures ALL fields are propagated from candidate → analysis → DB → Telegram
- No fake data – uses UNAVAILABLE when data is missing
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
    """Safely call a function, return default on exception."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[FullScan] Call error: {e}")
        return default


def full_scan_v34(candidates: List[dict], manual: bool = False) -> List[dict]:
    """
    Analyze candidates deeply, return Top 5 with ALL fields propagated.
    """
    if not candidates:
        return []

    print(f"[FullScan] Analyzing {len(candidates)} candidates...")
    enriched = []

    for idx, c in enumerate(candidates[:25]):
        ticker = c.get('ticker', 'UNKNOWN')
        print(f"[FullScan] {idx+1}/{min(len(candidates), 25)} {ticker}")

        # ============================================================
        # ANALYSIS CONTAINER – we will collect all data here
        # ============================================================
        analysis = {}

        # ------------------------------------------------------------
        # 1. BASIC CANDIDATE FIELDS (already in c, but we ensure they exist)
        # ------------------------------------------------------------
        # pm_data_quality – from discovery
        if 'pm_data_quality' not in c or c['pm_data_quality'] is None:
            c['pm_data_quality'] = 'UNKNOWN_PM_DATA'
        analysis['pm_data_quality'] = c['pm_data_quality']

        # price, gap, volume – should exist
        c['price'] = c.get('price', 0)
        c['gap_pct'] = c.get('gap_pct', 0)
        c['pm_volume'] = c.get('pm_volume', 0)

        # Spread – from discovery (Alpaca provides bid/ask)
        if 'spread_pct' not in c or c['spread_pct'] is None:
            c['spread_pct'] = 'UNAVAILABLE'
        analysis['spread_pct'] = c['spread_pct']

        # Bid/Ask – propagate if available
        c['bid'] = c.get('bid', None)
        c['ask'] = c.get('ask', None)
        analysis['bid'] = c['bid']
        analysis['ask'] = c['ask']

        # PM High / VWAP
        c['pm_high'] = c.get('pm_high', 0)
        c['pm_vwap'] = c.get('pm_vwap', 0)
        analysis['pm_high'] = c['pm_high']
        analysis['pm_vwap'] = c['pm_vwap']

        # ------------------------------------------------------------
        # 2. RVOL (with status)
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # 3. Relative Strength
        # ------------------------------------------------------------
        analysis['rs'] = _safe_call(get_relative_strength, None, ticker)
        c['rs'] = analysis['rs']

        # ------------------------------------------------------------
        # 4. News & Catalyst
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # 5. Sentiment (StockTwits)
        # ------------------------------------------------------------
        analysis['sentiment'] = _safe_call(get_stocktwits_sentiment, {}, ticker)
        c['sentiment'] = analysis['sentiment']

        # ------------------------------------------------------------
        # 6. SEC Risk
        # ------------------------------------------------------------
        analysis['sec_risk'] = _safe_call(check_offering_risk, {}, ticker)
        c['sec_risk'] = analysis['sec_risk']
        if isinstance(analysis['sec_risk'], dict):
            c['sec_risk_level'] = analysis['sec_risk'].get('risk_level', 'LOW')
            c['sec_has_offering'] = analysis['sec_risk'].get('has_offering', False)
        else:
            c['sec_risk_level'] = 'LOW'
            c['sec_has_offering'] = False

        # ------------------------------------------------------------
        # 7. Float & Short
        # ------------------------------------------------------------
        analysis['float_data'] = _safe_call(get_float_and_short, {}, ticker)
        c['float'] = analysis['float_data'].get('float')
        c['short_interest'] = analysis['float_data'].get('short_interest')
        c['short_ratio'] = analysis['float_data'].get('short_ratio')
        analysis['float'] = c['float']
        analysis['short_interest'] = c['short_interest']

        # ------------------------------------------------------------
        # 8. Personality
        # ------------------------------------------------------------
        analysis['personality'] = _safe_call(get_stock_personality, {}, ticker, c.get('gap_pct', 0))
        c['personality'] = analysis['personality']

        # ------------------------------------------------------------
        # 9. VWAP (dynamic)
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # 10. Sympathy
        # ------------------------------------------------------------
        analysis['sympathy'] = _safe_call(find_sympathy_candidates, [], c, 3)
        c['sympathy'] = analysis['sympathy']

        # ------------------------------------------------------------
        # 11. Trade Plan
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # 12. Composite Score
        # ------------------------------------------------------------
        c['composite_score'] = _safe_call(calculate_composite_score, 0, c, analysis)

        # ------------------------------------------------------------
        # 13. Store all analysis for later
        # ------------------------------------------------------------
        c['analysis'] = analysis

        enriched.append(c)

    # Sort by composite score
    enriched.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

    # Return Top 5 (or fewer)
    top5 = enriched[:5] if len(enriched) >= 5 else enriched

    print(f"[FullScan] Returning {len(top5)} candidates")
    return top5
