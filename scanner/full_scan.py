"""
סריקה מלאה – מפעילה את כל האנליזות, מדרגת ובוחרת 5 מובילים
"""
from datetime import datetime, time
import pytz
from scanner.premarket import scan_premarket
from scanner.analyzers.news_analyzer import fetch_news
from scanner.analyzers.volume_analyzer import calculate_rvol
from scanner.analyzers.rs_analyzer import get_relative_strength
from scanner.analyzers.sentiment_analyzer import get_combined_sentiment
from scanner.analyzers.ai_summarizer import summarize_candidate
from risk.trade_plan import build_trade_plan
from utils.config import ACCOUNT_SIZE, MAX_RISK_PER_TRADE_V31

ET = pytz.timezone("America/New_York")

def full_scan(manual=False) -> list:
    """
    מחזיר רשימה של 5 מועמדים מובילים עם ניתוח מלא
    """
    # 1. הפעלת סריקת פרה-מרקט
    candidates = scan_premarket()
    if not candidates:
        return []

    # 2. לכל מועמד – הפעל את כל האנליזות
    enriched = []
    for c in candidates[:15]:  # ניקח 15 ראשונים להרחבה
        print(f"[FullScan] Analyzing {c['ticker']}...")
        analysis = {}

        # RVOL
        analysis['rvol'] = calculate_rvol(c)

        # RS
        analysis['rs'] = get_relative_strength(c['ticker'])

        # News
        analysis['news'] = fetch_news(c['ticker'])

        # Sentiment
        analysis['sentiment'] = get_combined_sentiment(c['ticker'])

        # Trade plan (כבר יש)
        plan = build_trade_plan(c)
        c.update(plan)
        c['account_size'] = ACCOUNT_SIZE
        c['risk_pct'] = MAX_RISK_PER_TRADE_V31

        # ציון מורכב (לפי חשיבות) – נשתמש לצורך דירוג
        composite_score = c['opportunity_score'] * 0.5
        if analysis['rvol'] and analysis['rvol'] > 1.5:
            composite_score += 15
        elif analysis['rvol'] and analysis['rvol'] > 1.0:
            composite_score += 8
        if analysis['rs'] and analysis['rs'] > 1.2:
            composite_score += 10
        if analysis['sentiment'].get('combined', 0) > 0.2:
            composite_score += 10
        if len(analysis['news']) >= 2:
            composite_score += 7
        c['composite_score'] = round(min(100, composite_score), 1)

        # AI summary – נשמור את הניתוח להמשך
        c['analysis'] = analysis
        enriched.append(c)

    # 3. דירוג לפי composite_score
    enriched.sort(key=lambda x: x['composite_score'], reverse=True)
    top5 = enriched[:5]

    # 4. הוספת סיכום AI ל-5 המובילים
    for c in top5:
        c['ai_summary'] = summarize_candidate(c, c['analysis'])

    return top5
