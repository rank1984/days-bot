"""
מסכם את כל הנתונים באמצעות Gemini API
"""
import google.generativeai as genai
from utils.config import GEMINI_API_KEY

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

def summarize_candidate(candidate: dict, analysis: dict) -> str:
    """מחזיר פסקת הסבר בעברית על המועמד"""
    if not model:
        return "AI summary not available (missing API key)."
    
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
        return f"שגיאה ביצירת סיכום AI: {str(e)}"
