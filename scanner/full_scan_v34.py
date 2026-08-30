"""
V3.4 Full Scan – מחזיר 5 מועמדים מובילים תמיד (גם אם לא עברו Hard Filters)
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
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31


def full_scan_v34(manual=False, debug=False) -> list:
    """
    סריקה מלאה V3.4 – מחזירה תמיד 5 מועמדים (גם אם לא עברו Hard Filters)
    debug=True: מדפיסה מידע נוסף
    """
    print("\n[FullScan V3.4] Starting comprehensive analysis...")

    # 1. Premarket Scan
    candidates = scan_premarket()
    if not candidates:
        return []

    # 2. Analyze Top 30 candidates
    enriched = []
    for c in candidates[:30]:
        if debug:
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

        # V3.4: Stock Personality
        analysis['personality'] = get_stock_personality(c['ticker'], c.get('gap_pct', 0))

        # V3.4: VWAP
        vwap_data = calculate_vwap(c['ticker'], lookback_minutes=30)
        if not vwap_data:
            vwap_data = calculate_pm_vwap_from_candidate(c)
        analysis['vwap'] = vwap_data

        # V3.4: Sympathy
        analysis['sympathy'] = find_sympathy_candidates(c, max_candidates=3)

        # Trade Plan V3.4
        plan = build_trade_plan_v34(c, vwap_data)
        c.update(plan)
        c['account_size'] = ACCOUNT_SIZE
        c['risk_pct'] = MAX_RISK_PER_TRADE_V31

        # Personality bonus
        personality = analysis['personality']
        personality_bonus = 0
        if personality.get('personality') == "STRONG_FOLLOWER":
            personality_bonus = 15
        elif personality.get('personality') == "FOLLOWER":
            personality_bonus = 8
        elif personality.get('personality') == "GAP_AND_CRAP":
            personality_bonus = -20

        c['composite_score'] = calculate_composite_score(c, analysis) + personality_bonus

        # ============================================================
        # Hard Filter Check (למטרות דיווח בלבד – לא פסילה)
        # ============================================================
        filter_results = []
        failed_filters = []
        passed_filters = []

        # Gap > 10%
        if c.get('gap_pct', 0) >= 10:
            passed_filters.append("Gap > 10%")
        else:
            failed_filters.append(f"Gap {c.get('gap_pct', 0):.1f}% < 10%")

        # Float < 50M
        float_val = analysis.get('float', 0)
        if float_val and float_val < 50_000_000:
            passed_filters.append("Float < 50M")
        elif float_val:
            failed_filters.append(f"Float {float_val/1_000_000:.1f}M > 50M")
        else:
            failed_filters.append("Float not available")

        # RVOL > 3
        rvol = analysis.get('rvol', 0)
        if rvol and rvol >= 3:
            passed_filters.append("RVOL > 3x")
        elif rvol:
            failed_filters.append(f"RVOL {rvol:.1f}x < 3x")
        else:
            failed_filters.append("RVOL not available")

        # SEC Risk – לא HIGH
        sec_risk = analysis.get('sec_risk', {}).get('risk_level', 'LOW')
        if sec_risk != 'HIGH':
            passed_filters.append("No HIGH SEC risk")
        else:
            failed_filters.append("HIGH SEC risk (offering detected)")

        # Personality – לא GAP_AND_CRAP
        if personality.get('personality') != "GAP_AND_CRAP":
            passed_filters.append("Personality not GAP_AND_CRAP")
        else:
            failed_filters.append("Personality: GAP_AND_CRAP")

        c['filter_passed'] = passed_filters
        c['filter_failed'] = failed_filters
        c['filter_count'] = len(passed_filters)
        c['analysis'] = analysis
        enriched.append(c)

    # 3. Sort by composite_score – תמיד מחזירים Top 5
    enriched.sort(key=lambda x: x['composite_score'], reverse=True)
    top5 = enriched[:5]

    # 4. Add AI Summary for Top 5
    for c in top5:
        c['ai_summary'] = summarize_candidate(c, c['analysis'])

    # 5. Debug Output
    if debug:
        print("\n[FullScan V3.4] Debug Output:")
        for c in top5:
            print(f"  {c['ticker']}: Score={c['composite_score']}, Filters passed={c['filter_count']}/5")
            if c['filter_failed']:
                print(f"    Failed: {', '.join(c['filter_failed'])}")

    print(f"[FullScan V3.4] Returning {len(top5)} candidates (always top 5).")
    return top5
