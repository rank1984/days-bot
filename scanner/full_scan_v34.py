"""
V3.4 Full Scan – משלב Personality, Sympathy, VWAP, and all metrics
"""
from scanner.premarket import scan_premarket
from scanner.analyzers.float_analyzer import get_float_and_short
from scanner.analyzers.sec_analyzer import check_offering_risk
from scanner.analyzers.catalyst_analyzer import classify_catalyst
from scanner.analyzers.sentiment_social import get_stocktwits_sentiment
from scanner.analyzers.news_analyzer import fetch_news
from scanner.analyzers.volume_analyzer import calculate_rvol
from scanner.analyzers.rs_analyzer import get_relative_strength
from scanner.analyzers.ai_summarizer import summarize_candidate
from scanner.analyzers.personality_analyzer import get_stock_personality
from scanner.analyzers.sympathy_scanner import find_sympathy_candidates
from scanner.vwap_engine import calculate_vwap, calculate_pm_vwap_from_candidate
from risk.trade_plan_v34 import build_trade_plan_v34
from scanner.scoring_engine import calculate_composite_score
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31, LEARNING_MODE


def full_scan_v34(manual=False) -> list:
    """
    סריקה מלאה V3.4 – מחזירה Top 5 עם Personality + Sympathy + VWAP
    """
    print("\n[FullScan V3.4] Starting comprehensive analysis...")

    # 1. Premarket Scan
    candidates = scan_premarket()
    if not candidates:
        return []

    # 2. Analyze Top 25 candidates
    enriched = []
    for c in candidates[:25]:
        print(f"[FullScan] Analyzing {c['ticker']}...")
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

        # ============================================================
        # NEW V3.4: Stock Personality
        # ============================================================
        analysis['personality'] = get_stock_personality(c['ticker'], c.get('gap_pct', 0))

        # ============================================================
        # NEW V3.4: VWAP (dynamic)
        # ============================================================
        vwap_data = calculate_vwap(c['ticker'], lookback_minutes=30)
        if not vwap_data:
            vwap_data = calculate_pm_vwap_from_candidate(c)
        analysis['vwap'] = vwap_data

        # ============================================================
        # NEW V3.4: Sympathy Candidates
        # ============================================================
        analysis['sympathy'] = find_sympathy_candidates(c, max_candidates=3)

        # ============================================================
        # Trade Plan V3.4 (VWAP-based)
        # ============================================================
        plan = build_trade_plan_v34(c, vwap_data)
        c.update(plan)
        c['account_size'] = ACCOUNT_SIZE
        c['risk_pct'] = MAX_RISK_PER_TRADE_V31

        # ============================================================
        # Composite Score (V3.4 – עם Personality)
        # ============================================================
        c['composite_score'] = calculate_composite_score(c, analysis)

        # Store analysis
        c['analysis'] = analysis
        enriched.append(c)

    # 3. Hard Filters (בהתאם ל-LEARNING_MODE)
    filtered = []
    for c in enriched:
        float_val = c['analysis'].get('float', 0)
        gap = c.get('gap_pct', 0)
        rvol = c['analysis'].get('rvol', 0)
        personality = c['analysis']['personality'].get('personality', 'NEUTRAL')
        sec_risk = c['analysis']['sec_risk'].get('risk_level', 'LOW')

        # ב-LEARNING_MODE – לא פוסלים, רק מנכים ציון (כבר נעשה ב-scoring_engine)
        if not LEARNING_MODE:
            if float_val and float_val > 50_000_000:
                continue
            if gap < 10:
                continue
            if rvol and rvol < 3:
                continue
            if sec_risk == 'HIGH':
                continue
            if personality == "GAP_AND_CRAP":
                continue

        filtered.append(c)

    # 4. Sort by composite_score and take Top 5
    filtered.sort(key=lambda x: x['composite_score'], reverse=True)
    top5 = filtered[:5]

    # 5. Add AI Summary for Top 5
    for c in top5:
        c['ai_summary'] = summarize_candidate(c, c['analysis'])

    print(f"[FullScan V3.4] Found {len(top5)} qualified candidates.")
    return top5
