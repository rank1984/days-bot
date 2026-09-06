"""
AI Summarizer – DISABLED (Gemini API 404 fix)
Returns placeholder summary without Gemini API call.
"""

def summarize_candidate(candidate: dict, analysis: dict) -> str:
    """
    Returns placeholder summary without Gemini API call.
    """
    ticker = candidate.get('ticker', 'UNKNOWN')
    score = candidate.get('composite_score', candidate.get('event_score', 0))
    gap = candidate.get('gap_pct', 0)
    volume = candidate.get('pm_volume', 0)
    catalyst = analysis.get('catalyst', {}).get('type', 'GENERAL')

    if score >= 75 and gap > 10 and volume > 100000:
        return f"{ticker}: מניה חזקה עם גאפ {gap:.1f}% ונפח מסחר גבוה. קטליזטור: {catalyst}. מועמדת למסחר."
    elif score >= 60:
        return f"{ticker}: פוטנציאל בינוני. גאפ {gap:.1f}%, נפח {volume:,}. מומלץ מעקב."
    else:
        return f"{ticker}: ציון {score:.0f}/100. ללא איתות חזק למסחר."
