"""
AI Summarizer – Temporary disabled (Gemini 404 fix)
Returns placeholder without Gemini API call.
"""

def summarize_candidate(candidate: dict, analysis: dict) -> str:
    """Returns placeholder summary without Gemini API call."""
    ticker = candidate.get('ticker', 'UNKNOWN')
    score = candidate.get('opportunity_score', candidate.get('event_score', 0))
    gap = candidate.get('gap_pct', 0)
    volume = candidate.get('pm_volume', 0)
    catalyst_type = analysis.get('catalyst', {}).get('type', 'GENERAL')

    # Simple summary
    if score >= 75 and gap > 10 and volume > 100000:
        summary = f"מניה חזקה עם גאפ של {gap:.1f}% ונפח מסחר גבוה. קטליזטור מסוג {catalyst_type}. מועמדת למסחר."
    elif score >= 60:
        summary = f"מניה עם פוטנציאל בינוני. גאפ של {gap:.1f}%, נפח {volume:,}. מומלץ מעקב."
    else:
        summary = f"מניה עם ציון {score:.0f}/100. ללא איתות חזק למסחר."

    return summary
