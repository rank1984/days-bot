"""
V3.3 Full Scan – מפעיל את כל האנליזות ומחזיר Top 5
"""
from scanner.premarket import scan_premarket
from scanner.analyzers.float_analyzer import get_float_and_short
from scanner.analyzers.sec_analyzer import check_offering_risk
from scanner.analyzers.catalyst_analyzer import classify_catalyst
from scanner.analyzers.sentiment_social import get_stocktwits_sentiment, get_reddit_sentiment
from scanner.analyzers.news_analyzer import fetch_news
from scanner.analyzers.volume_analyzer import calculate_rvol
from scanner.analyzers.rs_analyzer import get_relative_strength
from scanner.analyzers.ai_summarizer import summarize_candidate
from risk.trade_plan import build_trade_plan
from scanner.scoring_engine import calculate_composite_score
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31


def full_scan_v33(manual=False) -> list:
    """
    סריקה מלאה V3.3 – מחזירה Top 5 עם ניתוח מלא
    """
    print("\n[FullScan V3.3] Starting comprehensive analysis...")

    # 1. Premarket Scan
    candidates = scan_premarket()
    if not candidates:
        return []

    # 2. Analyze Top 20 candidates
    enriched = []
    for c in candidates[:20]:
        print(f"[FullScan] Analyzing {c['ticker']}...")
        analysis = {}

        # Float & Short
        analysis['float_data'] = get_float_and_short(c['ticker'])
        analysis['float'] = analysis['float_data'].get('float')
        analysis['short_interest'] = analysis['float_data'].get('short_interest')
        analysis['short_ratio'] = analysis['float_data'].get('short_ratio')

        # RVOL
        analysis['rvol'] = calculate_rvol(c)

        # RS
        analysis['rs'] = get_relative_strength(c['ticker'])

        # News
        analysis['news'] = fetch_news(c['ticker'])

        # Sentiment
        analysis['sentiment'] = get_stocktwits_sentiment(c['ticker'])
        analysis['reddit'] = get_reddit_sentiment(c['ticker'])

        # Catalyst
        analysis['catalyst'] = classify_catalyst(analysis['news'])

        # SEC Risk
        analysis['sec_risk'] = check_offering_risk(c['ticker'])

        # Trade Plan
        plan = build_trade_plan(c)
        c.update(plan)
        c['account_size'] = ACCOUNT_SIZE
        c['risk_pct'] = MAX_RISK_PER_TRADE_V31

        # Composite Score (V3.3)
        c['composite_score'] = calculate_composite_score(c, analysis)

        # Store analysis
        c['analysis'] = analysis
        enriched.append(c)

    # 3. Filter by Hard Rules (Float < 20M, Gap > 10%, RVOL > 3)
    filtered = []
    for c in enriched:
        float_val = c['analysis'].get('float', 0)
        gap = c.get('gap_pct', 0)
        rvol = c['analysis'].get('rvol', 0)

        # Hard Filters
        if float_val and float_val > 50_000_000:
            print(f"[Filter] {c['ticker']} – Float too high ({float_val:,})")
            continue
        if gap < 10:
            print(f"[Filter] {c['ticker']} – Gap too low ({gap:.1f}%)")
            continue
        if rvol and rvol < 3:
            print(f"[Filter] {c['ticker']} – RVOL too low ({rvol:.1f}x)")
            continue

        # SEC Risk Check – hard reject if HIGH risk
        if c['analysis']['sec_risk'].get('risk_level') == 'HIGH':
            print(f"[Filter] {c['ticker']} – SEC Offering detected (HIGH risk)")
            continue

        filtered.append(c)

    # 4. Sort by composite_score and take Top 5
    filtered.sort(key=lambda x: x['composite_score'], reverse=True)
    top5 = filtered[:5]

    # 5. Add AI Summary for Top 5
    for c in top5:
        c['ai_summary'] = summarize_candidate(c, c['analysis'])

    print(f"[FullScan V3.3] Found {len(top5)} qualified candidates.")
    return top5
