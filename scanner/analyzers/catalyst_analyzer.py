"""
Catalyst Analyzer – Temporary disabled (Gemini 404 fix)
Returns default values without calling Gemini API.
"""
import json
import re


def classify_catalyst(headlines: list) -> dict:
    """
    Temporary fallback – returns default values without Gemini API call.
    Fixes 404 error: gemini-1.5-flash not available.
    """
    if not headlines:
        return {
            "type": "NO_NEWS",
            "score": 0,
            "summary": "אין חדשות אחרונות."
        }

    # Simple heuristic: check if headlines look important
    text = " ".join(headlines[:3]).upper()
    important_keywords = ["FDA", "APPROVAL", "CONTRACT", "PARTNERSHIP", "EARNINGS", "BEAT", "RAISES", "GUIDANCE"]
    weak_keywords = ["ANALYST", "UPGRADE", "INITIATES", "COVERAGE", "REITERATES"]

    score = 5  # default middle
    cat_type = "GENERAL"

    if any(kw in text for kw in important_keywords):
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
    elif any(kw in text for kw in weak_keywords):
        score = 4
        cat_type = "WEAK"

    # If no keywords, it's probably general news
    if score == 5 and not any(kw in text for kw in important_keywords + weak_keywords):
        cat_type = "GENERAL"
        score = 3

    return {
        "type": cat_type,
        "score": score,
        "summary": f"קטליזטור מסוג {cat_type} (ציון איכות: {score}/10)"
    }
