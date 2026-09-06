"""
Catalyst Analyzer – Uses Gemini Pro for classification
"""
import google.generativeai as genai
from utils.config import GEMINI_API_KEY
import json
import re

# Configure Gemini with Pro model
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')


def classify_catalyst(headlines: list) -> dict:
    """
    Classify catalyst quality using Gemini Pro.
    Returns: type, score (1-10), summary
    """
    if not headlines:
        return {
            "type": "NO_NEWS",
            "score": 0,
            "summary": "אין חדשות אחרונות."
        }

    text = " ".join(headlines[:3])
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

    try:
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

    except Exception as e:
        print(f"[Catalyst] Gemini error: {e}")
        # Fallback to heuristic
        return _fallback_classify(headlines)


def _fallback_classify(headlines: list) -> dict:
    """Simple heuristic fallback when Gemini fails."""
    if not headlines:
        return {"type": "NO_NEWS", "score": 0, "summary": "אין חדשות."}

    text = " ".join(headlines[:3]).upper()
    important = ["FDA", "APPROVAL", "CONTRACT", "PARTNERSHIP", "EARNINGS", "BEAT", "RAISES", "GUIDANCE"]

    if any(kw in text for kw in important):
        score = 8
        cat_type = "STRONG"
        if "FDA" in text or "APPROVAL" in text:
            cat_type = "FDA_APPROVAL"
            score = 9
        elif "EARNINGS" in text or "BEAT" in text:
            cat_type = "EARNINGS"
            score = 8
        elif "CONTRACT" in text or "PARTNERSHIP" in text:
            cat_type = "CONTRACT"
            score = 8
    else:
        score = 3
        cat_type = "GENERAL"

    return {
        "type": cat_type,
        "score": score,
        "summary": f"קטליזטור מסוג {cat_type} (ציון: {score}/10)"
    }
