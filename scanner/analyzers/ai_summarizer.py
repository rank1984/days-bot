"""
AI Summarizer – מסכם את כל הנתונים באמצעות Gemini API
(אם Gemini לא זמין – מחזיר תשובה גנרית)
"""
from typing import Dict, Any

try:
    import google.generativeai as genai
    from utils.config import GEMINI_API_KEY
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    GEMINI_AVAILABLE = True
except (ImportError, AttributeError, Exception):
    GEMINI_AVAILABLE = False
    print("[AI Summarizer] Gemini not available – using generic summary.")


def summarize_candidate(candidate: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    """מחזיר פסקת הסבר בעברית על המועמד"""
    if not GEMINI_AVAILABLE:
        return generate_fallback_summary(candidate, analysis)

    prompt = f"""
    אתה אנליסט מניות מנוסה. נתונים על המניה {candidate['ticker']}:
    - מחיר נוכחי: ${candidate['price']:.2f}
    - Gap: {candidate['gap_pct']:.1f}%
    - PM High: ${candidate['pm_high']:.2f}
    - PM VWAP: ${candidate['pm_vwap']:.2f}
    - ציון הזדמנות: {candidate['opportunity_score']}/100
    - RVOL: {analysis.get('rvol', 'N/A')}
    - חוזק יחסי: {analysis.get('rs', 'N/A')}
    - סנטימנט StockTwits: {analysis.get('sentiment', {}).get('stocktwits', 'N/A')}
    - פופולריות גוגל: {analysis.get('sentiment', {}).get('google_trends', 'N/A')}
    - חדשות: {', '.join(analysis.get('news', [])[:3])}
    
    כתוב סיכום של 2-3 משפטים בעברית: מה היתרון, מה הסיכון, והמלצה לפעולה.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[AI Summarizer] Error: {e}")
        return generate_fallback_summary(candidate, analysis)


def generate_fallback_summary(candidate: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    """סיכום גנרי ללא AI"""
    gap = candidate.get('gap_pct', 0)
    score = candidate.get('opportunity_score', 0)
    rvol = analysis.get('rvol', 0)
    float_val = analysis.get('float', 0)
    short = analysis.get('short_interest', 0)

    summary = f"{candidate['ticker']} מציג גאפ של {gap:.1f}% וציון הזדמנות {score}/100. "
    if rvol and rvol > 3:
        summary += f"נפח יחסי גבוה ({rvol:.1f}x) מעיד על עניין משמעותי. "
    if float_val and float_val < 20_000_000:
        summary += f"צף נמוך ({float_val:,.0f}) עלול ליצור תנודתיות חדה. "
    if short and short > 0.15:
        summary += f"אחוז שורטים גבוה ({short*100:.1f}%) מהווה פוטנציאל לסחיטה. "
    summary += "מומלץ להמתין לאישור פריצה מעל PM High עם נפח. סיכון: דילול או כישלון פריצה."
    return summary
