"""
Catalyst Analyzer – DISABLED (Gemini API 404 fix)
Returns default values without calling Gemini API.
"""
import json
import re


def classify_catalyst(headlines: list) -> dict:
    """
    Returns default catalyst classification without Gemini API call.
    Fixes 404 error (gemini-pro not available).
    """
    if not headlines:
        return {
            "type": "NO_NEWS",
            "score": 0,
            "summary": "אין חדשות אחרונות."
        }

    # Simple heuristic fallback
    text = " ".join(headlines[:3]).upper()
    important = ["FDA", "APPROVAL", "CONTRACT", "PARTNERSHIP", "EARNINGS", "BEAT", "RAISES", "GUIDANCE"]
    weak = ["ANALYST", "UPGRADE", "INITIATES", "COVERAGE", "REITERATES"]

    score = 5
    cat_type = "GENERAL"

    if any(kw in text for kw in important):
        score = 8
        if "FDA" in text or "APPROVAL" in text:
            cat_type = "FDA_APPROVAL"
            score = 9
        elif "EARNINGS" in text or "BEAT" in text:
            cat_type = "EARNINGS"
            score = 8
        elif "CONTRACT" in text or "PARTNERSHIP" in text:
            cat_type = "CONTRACT"
            score = 8
    elif any(kw in text for kw in weak):
        score = 4
        cat_type = "WEAK"

    return {
        "type": cat_type,
        "score": score,
        "summary": f"קטליזטור מסוג {cat_type} (ציון: {score}/10)"
    }
