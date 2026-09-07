"""
DAYS-BOT V4.3 – Catalyst Analyzer
- Tries Gemini first (if available)
- Falls back to heuristic based on news keywords
- Returns UNAVAILABLE if no news at all
"""
import google.generativeai as genai
from utils.config import GEMINI_API_KEY
import json
import re

# Configure Gemini if API key exists
GEMINI_AVAILABLE = False
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        GEMINI_AVAILABLE = True
    except:
        pass


def classify_catalyst(headlines: list) -> dict:
    """
    Classify catalyst quality.
    Returns: type, score (1-10), summary
    """
    if not headlines:
        return {
            "type": "UNAVAILABLE",
            "score": 0,
            "summary": "אין חדשות אחרונות."
        }

    text = " ".join(headlines[:3])

    # Try Gemini first
    if GEMINI_AVAILABLE:
        try:
            return _classify_with_gemini(text)
        except Exception as e:
            print(f"[Catalyst] Gemini error: {e}")

    # Fallback to heuristic
    return _fallback_classify(headlines)


def _classify_with_gemini(text: str) -> dict:
    """Use Gemini to classify catalyst"""
    prompt = f"""
    You are a financial news analyst. Given these headlines about a stock:
    "{text}"

    Classify the catalyst:
    1. Type: FDA_APPROVAL, EARNINGS, CONTRACT, PARTNERSHIP, M&A, GENERAL, WEAK, NO_NEWS
    2. Quality score: 1-10 (10 = most significant, 1 = insignificant)
    3. Summary in Hebrew: 1-2 sentences explaining the catalyst significance.

    Return EXACTLY this JSON format:
    {{"type": "...", "score": ..., "summary": "..."}}
    """

    response = model.generate_content(prompt)
    text_response = response.text.strip()

    # Extract JSON
    json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
    if json_match:
        result = json.loads(json_match.group())
        return {
            "type": result.get("type", "GENERAL"),
            "score": min(10, max(0, result.get("score", 5))),
            "summary": result.get("summary", "קטליזטור כללי.")
        }
    else:
        return {
            "type": "GENERAL",
            "score": 5,
            "summary": "לא ניתן לסווג את הקטליזטור."
        }


def _fallback_classify(headlines: list) -> dict:
    """Simple heuristic fallback when Gemini fails."""
    if not headlines:
        return {"type": "UNAVAILABLE", "score": 0, "summary": "אין חדשות."}

    text = " ".join(headlines[:3]).upper()
    important = ["FDA", "APPROVAL", "CONTRACT", "PARTNERSHIP", "EARNINGS", "BEAT", "RAISES", "GUIDANCE"]
    weak = ["ANALYST", "UPGRADE", "INITIATES", "COVERAGE", "REITERATES"]

    # Check for important keywords
    if any(kw in text for kw in important):
        if "FDA" in text or "APPROVAL" in text:
            return {
                "type": "FDA_APPROVAL",
                "score": 9,
                "summary": "אישור/התקדמות רגולטורית משמעותית."
            }
        elif "EARNINGS" in text or "BEAT" in text:
            return {
                "type": "EARNINGS",
                "score": 8,
                "summary": "תוצאות דוחות כספיים חיוביות."
            }
        elif "CONTRACT" in text or "PARTNERSHIP" in text:
            return {
                "type": "CONTRACT",
                "score": 8,
                "summary": "חוזה או שותפות אסטרטגית חדשה."
            }
        else:
            return {
                "type": "STRONG",
                "score": 7,
                "summary": "חדשות חיוביות משמעותיות."
            }

    if any(kw in text for kw in weak):
        return {
            "type": "WEAK",
            "score": 4,
            "summary": "חדשות קלות - אנליסט/כיסוי."
        }

    # Default: general news
    return {
        "type": "GENERAL",
        "score": 3,
        "summary": "חדשות כלליות ללא קטליזטור מובהק."
    }