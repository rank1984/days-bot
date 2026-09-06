"""
AI Summarizer – Uses Gemini Pro for candidate summary
"""
import google.generativeai as genai
from utils.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')


def summarize_candidate(candidate: dict, analysis: dict) -> str:
    """
    Generate a Hebrew summary for the candidate using Gemini Pro.
    """
    ticker = candidate.get('ticker', 'UNKNOWN')
    price = candidate.get('price', 0)
    gap = candidate.get('gap_pct', 0)
    score = candidate.get('composite_score', candidate.get('event_score', 0))
    volume = candidate.get('pm_volume', 0)

    catalyst = analysis.get('catalyst', {})
    catalyst_type = catalyst.get('type', 'GENERAL')
    catalyst_score = catalyst.get('score', 0)

    rvol = analysis.get('rvol', 0)
    float_val = analysis.get('float', 0)
    short = analysis.get('short_interest', 0)

    personality = analysis.get('personality', {}).get('personality', 'NEUTRAL')

    prompt = f"""
    You are a trading analyst. Summarize this stock in 2-3 Hebrew sentences:

    Ticker: {ticker}
    Price: ${price}
    Gap: {gap:+.1f}%
    Score: {score:.0f}/100
    PM Volume: {volume:,}
    RVOL: {rvol:.1f}x
    Float: {float_val:,.0f}
    Short Interest: {short*100:.1f}% if short else 'N/A'
    Catalyst: {catalyst_type} (Quality: {catalyst_score}/10)
    Personality: {personality}

    Summarize:
    1. What makes this interesting
    2. The main risk
    3. Recommended action (Wait/Consider/Pass)
    Keep it concise and practical.
    """

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[AI] Gemini error: {e}")
        return _fallback_summary(candidate, analysis)


def _fallback_summary(candidate: dict, analysis: dict) -> str:
    """Fallback summary without Gemini."""
    ticker = candidate.get('ticker', 'UNKNOWN')
    score = candidate.get('composite_score', candidate.get('event_score', 0))
    gap = candidate.get('gap_pct', 0)
    volume = candidate.get('pm_volume', 0)
    catalyst = analysis.get('catalyst', {}).get('type', 'GENERAL')

    if score >= 75 and gap > 10 and volume > 100000:
        return f"{ticker}: מניה חזקה עם גאפ {gap:.1f}% ונפח גבוה. קטליזטור: {catalyst}. מועמדת למסחר."
    elif score >= 60:
        return f"{ticker}: פוטנציאל בינוני. גאפ {gap:.1f}%, נפח {volume:,}. מומלץ מעקב."
    else:
        return f"{ticker}: ציון {score:.0f}/100. ללא איתות חזק למסחר."
