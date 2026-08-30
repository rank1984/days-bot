"""
Catalyst Analyzer – משתמש ב-Gemini לסיווג איכות הקטליזטור
(אם Gemini לא זמין, משתמש בכללים פשוטים)
"""
import json
import re
from typing import List, Dict

# נסיון לטעון את Gemini
try:
    import google.generativeai as genai
    from utils.config import GEMINI_API_KEY
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    GEMINI_AVAILABLE = True
except (ImportError, AttributeError, Exception):
    GEMINI_AVAILABLE = False
    print("[Catalyst] Gemini not available – using rule-based classification.")


def classify_catalyst(headlines: List[str]) -> Dict[str, any]:
    """
    מקבל רשימת כותרות חדשות, מחזיר:
    - type: "FDA_APPROVAL", "EARNINGS", "CONTRACT", "PARTNERSHIP", "GENERAL", "WEAK", "NO_NEWS"
    - score: 1-10 (10 = חזק ביותר)
    - summary: הסבר קצר בעברית
    """
    if not headlines:
        return {"type": "NO_NEWS", "score": 0, "summary": "אין חדשות אחרונות."}

    # אם Gemini לא זמין, נשתמש בכללים פשוטים
    if not GEMINI_AVAILABLE:
        return classify_rule_based(headlines)

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
        text_response = response.text.strip()
        json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            return {"type": "GENERAL", "score": 5, "summary": "לא ניתן לסווג את הקטליזטור."}
    except Exception as e:
        print(f"[Catalyst] Gemini error: {e}")
        return classify_rule_based(headlines)


def classify_rule_based(headlines: List[str]) -> Dict[str, any]:
    """סיווג מבוסס מילות מפתח פשוטות"""
    text = " ".join(headlines).lower()
    score = 5
    cat_type = "GENERAL"
    summary = "חדשות כלליות ללא קטליזטור ברור."

    # מילות מפתח לקטליזטורים חזקים
    strong_keywords = ["fda approval", "fda clears", "phase 3", "breakthrough", "contract awarded", "government contract",
                       "acquisition", "merger", "buyout", "earnings beat", "profit", "revenue growth"]
    weak_keywords = ["mou", "letter of intent", "non-binding", "exploring", "evaluating", "potential", "may", "could"]

    # בדיקה אם יש מילת מפתח חזקה
    for kw in strong_keywords:
        if kw in text:
            if "fda" in kw:
                cat_type = "FDA_APPROVAL"
                summary = "אישור FDA – קטליזטור משמעותי מאוד."
                score = 9
                break
            elif "contract" in kw or "government" in kw:
                cat_type = "CONTRACT"
                summary = "חוזה ממשלתי – קטליזטור חזק."
                score = 8
                break
            elif "acquisition" in kw or "merger" in kw or "buyout" in kw:
                cat_type = "M&A"
                summary = "רכישה או מיזוג – קטליזטור חזק."
                score = 8
                break
            elif "earnings" in kw or "profit" in kw:
                cat_type = "EARNINGS"
                summary = "דוחות כספיים חיוביים – קטליזטור חזק."
                score = 7
                break

    # אם לא נמצאה מילת מפתח חזקה, נבדוק חלשה
    if cat_type == "GENERAL":
        for kw in weak_keywords:
            if kw in text:
                cat_type = "WEAK"
                summary = "קטליזטור חלש/לא מחייב – מומלץ להיזהר."
                score = 3
                break

    return {"type": cat_type, "score": score, "summary": summary}
