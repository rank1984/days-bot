"""
Catalyst Analyzer – משתמש ב-Gemini לסיווג איכות הקטליזטור
"""
import google.generativeai as genai
from utils.config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')


def classify_catalyst(headlines: list) -> dict:
    """
    מקבל רשימת כותרות חדשות, מחזיר:
    - type: "FDA_APPROVAL", "EARNINGS", "CONTRACT", "PARTNERSHIP", "GENERAL", "WEAK"
    - score: 1-10 (10 = חזק ביותר)
    - summary: הסבר קצר בעברית
    """
    if not headlines:
        return {"type": "NO_NEWS", "score": 0, "summary": "אין חדשות אחרונות."}

    # נבחר את הכותרת הראשונה או ניקח 3 כותרות
    text = " ".join(headlines[:3])
    prompt = f"""
    אתה אנליסט חדשות פיננסיות. נתן לך כותרות חדשות על מניה:
    "{text}"

    אנא סווג את הקטליזטור:
    1. סוג: FDA_APPROVAL, EARNINGS, CONTRACT, PARTNERSHIP, M&A, GENERAL, WEAK, NO_NEWS
    2. ציון איכות: 1-10 (10 = משמעותי ביותר, 1 = חסר חשיבות)
    3. הסבר בעברית: 1-2 משפטים על משמעות הקטליזטור.

    החזר JSON בדיוק בפורמט:
    {{"type": "...", "score": ..., "summary": "..."}}
    """
    try:
        response = model.generate_content(prompt)
        import json
        # ננסה לחלץ JSON מתוך התשובה
        text_response = response.text.strip()
        # נמצא את ה-JSON
        import re
        json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            return {"type": "GENERAL", "score": 5, "summary": "לא ניתן לסווג את הקטליזטור."}
    except Exception as e:
        print(f"[Catalyst] Error: {e}")
        return {"type": "ERROR", "score": 0, "summary": "שגיאה בסיווג קטליזטור."}
